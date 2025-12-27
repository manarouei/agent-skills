#!/usr/bin/env python3
"""
Sync Celery Compatibility Validator

Static analysis tool to detect async/sync-incompatible patterns in Python code.
Enforces the "Sync Celery Execution Constraint" from bounded autonomy rules.

Runtime Reality:
- All skills execute within a single synchronous Celery task
- async def / await blocks the worker
- Background threads can orphan or deadlock
- HTTP calls without timeout block indefinitely

Run: python scripts/validate_sync_celery_compat.py [file_or_dir]
"""

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from contracts import BoundedAutonomyConstraints, SyncCeleryConstraints


@dataclass
class Violation:
    """A sync-celery compatibility violation."""
    file: str
    line: int
    column: int
    pattern: str
    description: str
    code_snippet: str = ""
    severity: str = "error"


@dataclass
class ValidationResult:
    """Result of sync-celery validation."""
    passed: bool
    violations: list[Violation] = field(default_factory=list)
    files_checked: int = 0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": [
                {
                    "file": v.file,
                    "line": v.line,
                    "column": v.column,
                    "pattern": v.pattern,
                    "description": v.description,
                    "code_snippet": v.code_snippet,
                    "severity": v.severity,
                }
                for v in self.violations
            ],
            "files_checked": self.files_checked,
        }


class AsyncDefVisitor(ast.NodeVisitor):
    """AST visitor to detect async def and await patterns."""
    
    def __init__(self, file_path: str, source_lines: list[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.violations: list[Violation] = []
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Detect async def functions."""
        snippet = self.source_lines[node.lineno - 1].strip() if node.lineno <= len(self.source_lines) else ""
        self.violations.append(Violation(
            file=self.file_path,
            line=node.lineno,
            column=node.col_offset,
            pattern="async_def",
            description=f"async def '{node.name}' will block Celery worker - use sync function",
            code_snippet=snippet,
        ))
        self.generic_visit(node)
    
    def visit_Await(self, node: ast.Await) -> None:
        """Detect await expressions."""
        snippet = self.source_lines[node.lineno - 1].strip() if node.lineno <= len(self.source_lines) else ""
        self.violations.append(Violation(
            file=self.file_path,
            line=node.lineno,
            column=node.col_offset,
            pattern="await",
            description="await requires async context - remove or use sync equivalent",
            code_snippet=snippet,
        ))
        self.generic_visit(node)


class SyncCeleryValidator:
    """
    Validates Python code for sync-Celery compatibility.
    
    Checks:
    1. No async def (blocks worker)
    2. No await expressions
    3. No async-only imports (asyncio, aiohttp)
    4. Threading.Thread must have .join()
    5. HTTP calls should have timeout=
    """
    
    # Import patterns that indicate async-only dependencies
    ASYNC_IMPORTS = [
        (r"^\s*import\s+asyncio\b", "asyncio import (async-only library)"),
        (r"^\s*from\s+asyncio\b", "asyncio import (async-only library)"),
        (r"^\s*import\s+aiohttp\b", "aiohttp import (async-only HTTP client)"),
        (r"^\s*from\s+aiohttp\b", "aiohttp import (async-only HTTP client)"),
        (r"^\s*import\s+aiofiles\b", "aiofiles import (async-only file I/O)"),
        (r"^\s*from\s+aiofiles\b", "aiofiles import (async-only file I/O)"),
        (r"^\s*import\s+aiomysql\b", "aiomysql import (async-only database)"),
        (r"^\s*from\s+aiomysql\b", "aiomysql import (async-only database)"),
        (r"^\s*import\s+aiopg\b", "aiopg import (async-only database)"),
        (r"^\s*from\s+aiopg\b", "aiopg import (async-only database)"),
    ]
    
    # Thread patterns that may orphan
    THREAD_PATTERNS = [
        # Thread() without subsequent .join() on same object is suspicious
        (r"threading\.Thread\s*\(", "Thread creation - ensure .join() is called"),
    ]
    
    # HTTP calls that should have timeout
    HTTP_PATTERNS = [
        (r"requests\.(get|post|put|delete|patch|head|options)\s*\([^)]*\)", "requests call"),
        (r"httpx\.(get|post|put|delete|patch|head|options)\s*\([^)]*\)", "httpx call"),
        (r"urllib\.request\.urlopen\s*\([^)]*\)", "urllib call"),
    ]
    
    def __init__(self, constraints: SyncCeleryConstraints | None = None):
        self.constraints = constraints or SyncCeleryConstraints()
    
    def validate_file(self, file_path: Path) -> list[Violation]:
        """Validate a single Python file."""
        if not file_path.exists():
            return [Violation(
                file=str(file_path),
                line=0,
                column=0,
                pattern="file_not_found",
                description=f"File not found: {file_path}",
            )]
        
        if file_path.suffix != ".py":
            return []  # Skip non-Python files
        
        try:
            source = file_path.read_text()
        except Exception as e:
            return [Violation(
                file=str(file_path),
                line=0,
                column=0,
                pattern="read_error",
                description=f"Could not read file: {e}",
            )]
        
        return self.validate_code(source, str(file_path))
    
    def validate_code(self, source: str, file_path: str = "<string>") -> list[Violation]:
        """Validate Python source code."""
        violations: list[Violation] = []
        source_lines = source.split("\n")
        
        # 1. AST-based checks (async def, await)
        if self.constraints.requires_sync_execution:
            try:
                tree = ast.parse(source)
                visitor = AsyncDefVisitor(file_path, source_lines)
                visitor.visit(tree)
                violations.extend(visitor.violations)
            except SyntaxError as e:
                violations.append(Violation(
                    file=file_path,
                    line=e.lineno or 0,
                    column=e.offset or 0,
                    pattern="syntax_error",
                    description=f"Syntax error: {e.msg}",
                    severity="warning",
                ))
        
        # 2. Regex-based checks (imports, patterns)
        for line_num, line in enumerate(source_lines, 1):
            # Check async-only imports
            if self.constraints.forbids_async_dependencies:
                for pattern, description in self.ASYNC_IMPORTS:
                    if re.search(pattern, line):
                        violations.append(Violation(
                            file=file_path,
                            line=line_num,
                            column=0,
                            pattern="async_import",
                            description=description,
                            code_snippet=line.strip(),
                        ))
            
            # Check thread patterns
            if self.constraints.forbids_background_tasks:
                for pattern, description in self.THREAD_PATTERNS:
                    if re.search(pattern, line):
                        violations.append(Violation(
                            file=file_path,
                            line=line_num,
                            column=0,
                            pattern="thread_usage",
                            description=f"{description} - ensure .join() before return",
                            code_snippet=line.strip(),
                            severity="warning",
                        ))
            
            # Check HTTP calls for timeout
            if self.constraints.requires_timeouts_on_external_calls:
                for pattern, description in self.HTTP_PATTERNS:
                    match = re.search(pattern, line)
                    if match:
                        call_text = match.group(0)
                        if "timeout" not in call_text.lower():
                            violations.append(Violation(
                                file=file_path,
                                line=line_num,
                                column=0,
                                pattern="http_no_timeout",
                                description=f"{description} missing timeout= argument",
                                code_snippet=line.strip(),
                                severity="warning",
                            ))
        
        return violations
    
    def validate_directory(self, dir_path: Path, recursive: bool = True) -> ValidationResult:
        """Validate all Python files in a directory."""
        all_violations: list[Violation] = []
        files_checked = 0
        
        pattern = "**/*.py" if recursive else "*.py"
        for py_file in dir_path.glob(pattern):
            # Skip common non-source directories
            if any(part.startswith(".") or part in ("__pycache__", "venv", ".venv", "node_modules") 
                   for part in py_file.parts):
                continue
            
            violations = self.validate_file(py_file)
            all_violations.extend(violations)
            files_checked += 1
        
        return ValidationResult(
            passed=len([v for v in all_violations if v.severity == "error"]) == 0,
            violations=all_violations,
            files_checked=files_checked,
        )


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Python code for sync-Celery compatibility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s file.py                    # Check single file
  %(prog)s src/                        # Check all .py in src/
  %(prog)s --strict src/              # Treat warnings as errors
  %(prog)s --json results.json src/   # Output JSON report
        """,
    )
    parser.add_argument("path", nargs="?", default=".", help="File or directory to check")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    parser.add_argument("--json", metavar="FILE", help="Output JSON report to file")
    parser.add_argument("--quiet", "-q", action="store_true", help="Only output errors")
    
    args = parser.parse_args()
    
    path = Path(args.path)
    validator = SyncCeleryValidator()
    
    if path.is_file():
        violations = validator.validate_file(path)
        result = ValidationResult(
            passed=len([v for v in violations if v.severity == "error"]) == 0,
            violations=violations,
            files_checked=1,
        )
    elif path.is_dir():
        result = validator.validate_directory(path)
    else:
        print(f"Error: {path} does not exist", file=sys.stderr)
        return 1
    
    # Apply strict mode
    if args.strict:
        error_count = len(result.violations)
        result.passed = error_count == 0
    else:
        error_count = len([v for v in result.violations if v.severity == "error"])
    
    # Output results
    if args.json:
        import json
        Path(args.json).write_text(json.dumps(result.to_dict(), indent=2))
        if not args.quiet:
            print(f"Report written to {args.json}")
    
    if not args.quiet or not result.passed:
        print(f"\n{'='*60}")
        print(f"Sync-Celery Compatibility Check")
        print(f"{'='*60}")
        print(f"Files checked: {result.files_checked}")
        print(f"Violations: {len(result.violations)} ({error_count} errors)")
        print(f"Status: {'PASS' if result.passed else 'FAIL'}")
        
        if result.violations:
            print(f"\n{'Violations':}")
            for v in result.violations:
                severity_marker = "ERROR" if v.severity == "error" else "WARN"
                print(f"  [{severity_marker}] {v.file}:{v.line} - {v.pattern}")
                print(f"          {v.description}")
                if v.code_snippet:
                    print(f"          > {v.code_snippet[:60]}...")
    
    # Return appropriate exit code
    if result.passed:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
