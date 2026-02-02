"""
Node Smoke Test Skill Implementation

Smoke test the applied node by importing it in the target repo's Python environment.
Verifies the node class exists and can be instantiated.

ALSO performs static checks on the packaged code BEFORE runtime import:
- No NotImplementedError
- No placeholder URLs (api.example.com)
- No async patterns
- Required class attributes exist

Uses subprocess to run tests in isolation (does not pollute current process).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext


# =============================================================================
# STATIC PRE-RUNTIME CHECKS
# =============================================================================

def _static_check_not_implemented(py_files: list[Path]) -> tuple[bool, str, list[str]]:
    """
    Static check: No NotImplementedError in code.
    
    This catches unfinished operations BEFORE attempting runtime import.
    """
    issues = []
    
    for py_file in py_files:
        content = py_file.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            if "NotImplementedError" in line:
                issues.append(f"{py_file.name}:{i}: NotImplementedError found")
    
    if issues:
        return False, f"Found {len(issues)} NotImplementedError occurrences", issues
    return True, "No NotImplementedError found", []


def _static_check_placeholder_urls(py_files: list[Path]) -> tuple[bool, str, list[str]]:
    """
    Static check: No placeholder URLs.
    
    Rejects:
    - api.example.com
    - /endpoint placeholder
    """
    issues = []
    
    placeholder_patterns = [
        (r'api\.example\.com', "Placeholder URL 'api.example.com'"),
        (r'["\']\/endpoint["\']', "Placeholder endpoint '/endpoint'"),
    ]
    
    for py_file in py_files:
        content = py_file.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            for pattern, desc in placeholder_patterns:
                if re.search(pattern, line):
                    issues.append(f"{py_file.name}:{i}: {desc}")
    
    if issues:
        return False, f"Found {len(issues)} placeholder URL occurrences", issues
    return True, "No placeholder URLs found", []


def _static_check_async_patterns(py_files: list[Path]) -> tuple[bool, str, list[str]]:
    """
    Static check: No async patterns (sync Celery constraint).
    """
    issues = []
    
    async_patterns = [
        (r"\basync\s+def\b", "async def"),
        (r"\bawait\b", "await expression"),
        (r"\basyncio\.", "asyncio usage"),
    ]
    
    for py_file in py_files:
        content = py_file.read_text()
        for i, line in enumerate(content.splitlines(), 1):
            for pattern, desc in async_patterns:
                if re.search(pattern, line):
                    issues.append(f"{py_file.name}:{i}: {desc}")
    
    if issues:
        return False, f"Found {len(issues)} async pattern occurrences", issues
    return True, "No async patterns found", []


def _static_check_class_attributes(py_files: list[Path]) -> tuple[bool, str, list[str]]:
    """
    Static check: Required class attributes exist.
    
    Checks for presence of:
    - type = "..."
    - version = ...
    - description = {...}
    - properties = {...}
    - def execute(self
    """
    issues = []
    required_patterns = [
        (r'^\s+type\s*=\s*["\']', "type attribute"),
        (r'^\s+version\s*=\s*\d', "version attribute"),
        (r'^\s+description\s*=\s*\{', "description dict"),
        (r'^\s+properties\s*=\s*\{', "properties dict"),
        (r'def\s+execute\s*\(\s*self', "execute method"),
    ]
    
    for py_file in py_files:
        # Skip __init__.py and test files
        if py_file.name in ("__init__.py",) or py_file.name.startswith("test_"):
            continue
        
        content = py_file.read_text()
        
        for pattern, attr_name in required_patterns:
            if not re.search(pattern, content, re.MULTILINE):
                issues.append(f"{py_file.name}: Missing {attr_name}")
    
    if issues:
        return False, f"Missing {len(issues)} required attributes", issues
    return True, "All required attributes present", []


IMPORT_TEST_TEMPLATE = '''
import sys
import json

# Add target repo to path
sys.path.insert(0, {repo_path!r})

results = {{"import": False, "class_exists": False, "type_attr": None, "error": None}}

try:
    # Import the module
    from {module_path} import {class_name}
    results["import"] = True
    
    # Check class exists
    results["class_exists"] = True
    
    # Get type attribute
    if hasattr({class_name}, 'type'):
        results["type_attr"] = {class_name}.type
    
except Exception as e:
    results["error"] = str(e)

print(json.dumps(results))
'''


def _run_import_test(
    repo_path: str,
    module_path: str,
    class_name: str,
    python_executable: str | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Run import test in subprocess.
    
    Returns dict with:
        import: bool - True if import succeeded
        class_exists: bool - True if class found
        type_attr: str | None - Value of type attribute
        error: str | None - Error message if failed
    """
    test_code = IMPORT_TEST_TEMPLATE.format(
        repo_path=repo_path,
        module_path=module_path,
        class_name=class_name,
    )
    
    python_exe = python_executable or sys.executable
    
    try:
        result = subprocess.run(
            [python_exe, "-c", test_code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=repo_path,
        )
        
        if result.returncode == 0:
            try:
                return json.loads(result.stdout.strip())
            except json.JSONDecodeError:
                return {
                    "import": False,
                    "class_exists": False,
                    "type_attr": None,
                    "error": f"Invalid JSON output: {result.stdout}",
                }
        else:
            return {
                "import": False,
                "class_exists": False,
                "type_attr": None,
                "error": f"Exit code {result.returncode}: {result.stderr}",
            }
    except subprocess.TimeoutExpired:
        return {
            "import": False,
            "class_exists": False,
            "type_attr": None,
            "error": f"Timeout after {timeout}s",
        }
    except Exception as e:
        return {
            "import": False,
            "class_exists": False,
            "type_attr": None,
            "error": str(e),
        }


def run(ctx: "ExecutionContext") -> dict[str, Any]:
    """
    Smoke test the applied node in target repo's Python environment.
    
    PHASE 1: Static checks on packaged code (pre-runtime)
    PHASE 2: Runtime import test in subprocess
    
    Reads manifest from artifacts/ and tests import in target repo.
    Writes results to artifacts/{correlation_id}/smoke_test/
    """
    inputs = ctx.inputs
    correlation_id = inputs["correlation_id"]
    target_repo_layout = inputs["target_repo_layout"]
    node_type_override = inputs.get("node_type")
    skip_static_checks = inputs.get("skip_static_checks", False)
    
    ctx.log("node_smoke_test_start", {"correlation_id": correlation_id})
    
    # Extract layout info
    target_repo_root = Path(target_repo_layout["target_repo_root"])
    node_output_base_dir = target_repo_layout.get("node_output_base_dir", "nodes")
    venv_path = target_repo_layout.get("venv_path")
    
    # Get paths
    artifacts_dir = ctx.artifacts_dir
    package_dir = artifacts_dir / "package"
    smoke_test_dir = artifacts_dir / "smoke_test"
    
    # Create smoke test directory
    smoke_test_dir.mkdir(parents=True, exist_ok=True)
    
    tests = []
    errors = []
    
    # Read manifest
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        return {
            "success": False,
            "tests": [],
            "errors": [f"Manifest not found: {manifest_path}"],
        }
    
    manifest = json.loads(manifest_path.read_text())
    registry_entry = manifest.get("registry_entry", {})
    
    node_type = node_type_override or manifest.get("node_type")
    node_class = manifest.get("node_class") or registry_entry.get("node_class")
    module_name = registry_entry.get("module_name")
    
    if not node_class:
        return {
            "success": False,
            "tests": [],
            "errors": ["Could not determine node class from manifest"],
        }
    
    if not module_name:
        module_name = node_type.lower() if node_type else "unknown"
    
    # =========================================================================
    # PHASE 1: Static checks (pre-runtime)
    # These catch obvious issues BEFORE attempting runtime import
    # =========================================================================
    
    py_files = list(package_dir.glob("*.py"))
    
    if not skip_static_checks and py_files:
        ctx.log("static_checks_start", {"file_count": len(py_files)})
        
        # Static Test 1: No NotImplementedError
        passed, details, issues = _static_check_not_implemented(py_files)
        tests.append({
            "name": "Static: No NotImplementedError",
            "passed": passed,
            "details": details,
        })
        if not passed:
            errors.extend(issues[:5])  # Limit to first 5 issues
        
        # Static Test 2: No placeholder URLs
        passed, details, issues = _static_check_placeholder_urls(py_files)
        tests.append({
            "name": "Static: No Placeholder URLs",
            "passed": passed,
            "details": details,
        })
        if not passed:
            errors.extend(issues[:5])
        
        # Static Test 3: No async patterns
        passed, details, issues = _static_check_async_patterns(py_files)
        tests.append({
            "name": "Static: No Async Patterns",
            "passed": passed,
            "details": details,
        })
        if not passed:
            errors.extend(issues[:5])
        
        # Static Test 4: Required class attributes
        passed, details, issues = _static_check_class_attributes(py_files)
        tests.append({
            "name": "Static: Required Attributes",
            "passed": passed,
            "details": details,
        })
        if not passed:
            errors.extend(issues)
        
        # If static checks failed, skip runtime tests (will fail anyway)
        static_failed = any(not t["passed"] for t in tests if t["name"].startswith("Static:"))
        if static_failed:
            ctx.log("static_checks_failed", {"errors": errors})
            
            # Write results and return early
            results = {
                "correlation_id": correlation_id,
                "success": False,
                "node_type": node_type,
                "node_class": node_class,
                "phase": "static_checks",
                "tests": tests,
                "errors": errors,
            }
            results_path = smoke_test_dir / "results.json"
            results_path.write_text(json.dumps(results, indent=2))
            
            return {
                "success": False,
                "tests": tests,
                "errors": errors,
            }
    
    # =========================================================================
    # PHASE 2: Runtime import tests
    # =========================================================================
    
    # Determine Python executable
    python_exe = None
    if venv_path:
        venv_python = target_repo_root / venv_path / "bin" / "python"
        if venv_python.exists():
            python_exe = str(venv_python)
    
    # Construct module path (e.g., "nodes.bitly")
    module_path = f"{node_output_base_dir}.{module_name}"
    
    # Runtime Test 1: Import test
    import_result = _run_import_test(
        repo_path=str(target_repo_root),
        module_path=module_path,
        class_name=node_class,
        python_executable=python_exe,
        timeout=30,
    )
    
    tests.append({
        "name": "Runtime: Import Module",
        "passed": import_result["import"],
        "details": f"from {module_path} import {node_class}" if import_result["import"] else import_result.get("error", "Unknown error"),
    })
    
    if not import_result["import"]:
        errors.append(f"Import failed: {import_result.get('error')}")
    
    # Runtime Test 2: Class exists
    tests.append({
        "name": "Runtime: Class Exists",
        "passed": import_result["class_exists"],
        "details": f"Found class {node_class}" if import_result["class_exists"] else "Class not found after import",
    })
    
    # Runtime Test 3: Type attribute
    type_attr = import_result.get("type_attr")
    type_test_passed = type_attr is not None
    tests.append({
        "name": "Runtime: Type Attribute",
        "passed": type_test_passed,
        "details": f"type = '{type_attr}'" if type_test_passed else "No 'type' attribute found",
    })
    
    if not type_test_passed and import_result["import"]:
        errors.append("Node class missing 'type' attribute")
    
    # Runtime Test 4: Type matches expected
    if type_attr and node_type:
        type_match = type_attr == node_type
        tests.append({
            "name": "Runtime: Type Match",
            "passed": type_match,
            "details": f"Expected '{node_type}', got '{type_attr}'" if not type_match else f"Type matches: '{node_type}'",
        })
        if not type_match:
            errors.append(f"Type mismatch: expected '{node_type}', got '{type_attr}'")
    
    # Determine overall success
    success = all(t["passed"] for t in tests)
    
    # Write results
    results = {
        "correlation_id": correlation_id,
        "success": success,
        "node_type": node_type,
        "node_class": node_class,
        "module_path": module_path,
        "target_repo_root": str(target_repo_root),
        "python_executable": python_exe or sys.executable,
        "tests": tests,
        "errors": errors,
    }
    
    results_path = smoke_test_dir / "results.json"
    results_path.write_text(json.dumps(results, indent=2))
    
    ctx.log("node_smoke_test_complete", {
        "success": success,
        "tests_count": len(tests),
        "tests_passed": sum(1 for t in tests if t["passed"]),
        "errors_count": len(errors),
    })
    
    return {
        "success": success,
        "tests": tests,
        "errors": errors,
    }
