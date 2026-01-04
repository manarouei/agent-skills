#!/usr/bin/env python3
"""
mine_back_nodes.py - Script A: Mine patterns from back/nodes/*.py

Parses node implementations using AST to extract:
- get_credentials() patterns (field names, types)
- HTTP request shapes (method, headers, params, body)
- Pagination idioms (cursor, offset, page-based)
- Error handling patterns

Output: Promotion candidates in artifacts/<run_id>/
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from runtime.kb.candidates import (
    CandidateStats,
    CandidateType,
    MiningCandidate,
    MiningRunManifest,
    ReviewNotes,
    SourceKind,
    SourceReference,
    generate_candidate_id,
    validate_candidate,
)
from runtime.kb.loader import CANONICAL_CATEGORIES, normalize_category


# ---------------------------------------------------------------------------
# AST Pattern Extractors
# ---------------------------------------------------------------------------


class NodePatternExtractor(ast.NodeVisitor):
    """Extract patterns from a single node file."""

    def __init__(self, file_path: Path, source_code: str) -> None:
        self.file_path = file_path
        self.source_code = source_code
        self.lines = source_code.splitlines()
        self.patterns: list[dict[str, Any]] = []
        self.current_class: str | None = None
        self.current_method: str | None = None

    def _get_line_range(self, node: ast.AST) -> str:
        """Get line range string for a node."""
        start = node.lineno
        end = getattr(node, "end_lineno", start) or start
        return f"L{start}-L{end}"

    def _get_source_excerpt(self, node: ast.AST) -> str:
        """Get source code excerpt for a node."""
        start = node.lineno - 1
        end = getattr(node, "end_lineno", start + 1) or (start + 1)
        return "\n".join(self.lines[start:end])

    def _hash_excerpt(self, excerpt: str) -> str:
        """Generate SHA256 hash of excerpt."""
        return f"sha256:{hashlib.sha256(excerpt.encode()).hexdigest()[:16]}"

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Track current class for context."""
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extract patterns from function definitions."""
        self.current_method = node.name

        # Pattern: get_credentials method
        if node.name == "get_credentials":
            self._extract_credentials_pattern(node)

        # Pattern: HTTP request methods
        if node.name in ("execute", "run", "fetch", "_make_request"):
            self._extract_http_pattern(node)

        # Pattern: pagination methods
        if "page" in node.name.lower() or "paginate" in node.name.lower():
            self._extract_pagination_pattern(node)

        self.generic_visit(node)
        self.current_method = None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Track async functions (shouldn't exist but note if found)."""
        # We don't extract patterns from async functions but note them
        self.patterns.append({
            "type": "warning",
            "category": "service_quirk",
            "message": f"Async function found: {node.name}",
            "class_name": self.current_class,
            "line_range": self._get_line_range(node),
        })
        self.generic_visit(node)

    def _extract_credentials_pattern(self, node: ast.FunctionDef) -> None:
        """Extract get_credentials pattern."""
        excerpt = self._get_source_excerpt(node)
        
        # Find credential field accesses
        fields: list[str] = []
        for child in ast.walk(node):
            # Look for self.credentials.field or credentials['field']
            if isinstance(child, ast.Attribute):
                if (
                    isinstance(child.value, ast.Attribute)
                    and child.value.attr == "credentials"
                ):
                    fields.append(child.attr)
            elif isinstance(child, ast.Subscript):
                if (
                    isinstance(child.value, ast.Attribute)
                    and child.value.attr == "credentials"
                    and isinstance(child.slice, ast.Constant)
                ):
                    fields.append(str(child.slice.value))

        if fields:
            self.patterns.append({
                "type": "pattern",
                "category": "auth",
                "name": f"{self.current_class}_credentials",
                "description": f"Credential access pattern for {self.current_class}",
                "pattern_data": {
                    "fields": list(set(fields)),
                    "class_name": self.current_class,
                    "method": "get_credentials",
                },
                "line_range": self._get_line_range(node),
                "excerpt": excerpt,
                "excerpt_hash": self._hash_excerpt(excerpt),
            })

    def _extract_http_pattern(self, node: ast.FunctionDef) -> None:
        """Extract HTTP request patterns."""
        excerpt = self._get_source_excerpt(node)
        
        # Find requests.get/post/etc or httpx calls
        http_info: dict[str, Any] = {
            "methods": [],
            "headers": [],
            "has_timeout": False,
            "has_retry": False,
        }

        for child in ast.walk(node):
            # Look for method calls like requests.get, self.session.post, etc
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Attribute):
                    method = func.attr.lower()
                    if method in ("get", "post", "put", "patch", "delete", "request"):
                        http_info["methods"].append(method.upper())
                    
                    # Check for timeout in keywords
                    for kw in child.keywords:
                        if kw.arg == "timeout":
                            http_info["has_timeout"] = True
                        if kw.arg == "headers":
                            http_info["headers"].append("custom_headers")
                        if kw.arg == "retry" or kw.arg == "retries":
                            http_info["has_retry"] = True

        if http_info["methods"]:
            http_info["methods"] = list(set(http_info["methods"]))
            self.patterns.append({
                "type": "pattern",
                "category": "service_quirk",
                "name": f"{self.current_class}_http",
                "description": f"HTTP request pattern for {self.current_class}",
                "pattern_data": http_info,
                "line_range": self._get_line_range(node),
                "excerpt": excerpt,
                "excerpt_hash": self._hash_excerpt(excerpt),
            })

    def _extract_pagination_pattern(self, node: ast.FunctionDef) -> None:
        """Extract pagination patterns."""
        excerpt = self._get_source_excerpt(node)
        
        pagination_info: dict[str, Any] = {
            "style": "unknown",
            "params": [],
        }

        # Detect pagination style from code patterns
        code_lower = excerpt.lower()
        
        if "cursor" in code_lower or "next_cursor" in code_lower:
            pagination_info["style"] = "cursor"
        elif "offset" in code_lower and "limit" in code_lower:
            pagination_info["style"] = "offset"
        elif "page" in code_lower and ("per_page" in code_lower or "page_size" in code_lower):
            pagination_info["style"] = "page_number"
        elif "next_page_token" in code_lower or "page_token" in code_lower:
            pagination_info["style"] = "token"

        # Find pagination parameter names
        for child in ast.walk(node):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                val = child.value.lower()
                if any(p in val for p in ("cursor", "offset", "limit", "page", "next")):
                    pagination_info["params"].append(child.value)

        pagination_info["params"] = list(set(pagination_info["params"]))[:10]

        if pagination_info["style"] != "unknown" or pagination_info["params"]:
            self.patterns.append({
                "type": "pattern",
                "category": "pagination",
                "name": f"{self.current_class}_pagination",
                "description": f"Pagination pattern for {self.current_class}",
                "pattern_data": pagination_info,
                "line_range": self._get_line_range(node),
                "excerpt": excerpt,
                "excerpt_hash": self._hash_excerpt(excerpt),
            })


def extract_patterns_from_file(file_path: Path) -> list[dict[str, Any]]:
    """Extract all patterns from a single Python file."""
    try:
        source_code = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code, filename=str(file_path))
        
        extractor = NodePatternExtractor(file_path, source_code)
        extractor.visit(tree)
        
        return extractor.patterns
    except SyntaxError as e:
        return [{
            "type": "error",
            "message": f"Syntax error in {file_path}: {e}",
        }]
    except Exception as e:
        return [{
            "type": "error",
            "message": f"Error parsing {file_path}: {e}",
        }]


# ---------------------------------------------------------------------------
# Candidate Generation
# ---------------------------------------------------------------------------


def pattern_to_candidate(
    pattern: dict[str, Any],
    source_file: Path,
    run_id: str,
) -> MiningCandidate | None:
    """Convert extracted pattern to MiningCandidate."""
    if pattern.get("type") != "pattern":
        return None

    category = normalize_category(pattern.get("category", "service_quirk"))
    name = pattern.get("name", "unknown_pattern")

    source_ref = SourceReference(
        kind=SourceKind.NODE_FILE,
        path=str(source_file),
        line_range=pattern.get("line_range"),
        excerpt_hash=pattern.get("excerpt_hash"),
    )

    # Hash the pattern data for deduplication
    pattern_data = pattern.get("pattern_data", {})
    pattern_json = json.dumps(pattern_data, sort_keys=True)
    content_hash = hashlib.sha256(pattern_json.encode()).hexdigest()[:16]

    # Build the pattern payload matching KB schema
    kb_pattern = {
        "type": category,  # e.g., "auth", "pagination"
        **pattern_data,
    }
    
    from runtime.kb.candidates import CandidateStats, ReviewNotes
    
    candidate = MiningCandidate(
        candidate_id=generate_candidate_id(category, f"{name}-{content_hash}"),
        candidate_type=CandidateType.PATTERN,
        category=category,
        title=name,
        confidence=0.6,  # AST extraction is reasonably confident
        stats=CandidateStats(frequency=1, distinct_sources=1),
        provenance=[source_ref],
        pattern=kb_pattern,
        review_notes=ReviewNotes(),
        mining_run_id=run_id,
    )

    return candidate


# ---------------------------------------------------------------------------
# Main Mining Logic
# ---------------------------------------------------------------------------


def mine_back_nodes(
    nodes_dir: Path,
    output_dir: Path,
    run_id: str,
    verbose: bool = False,
) -> tuple[list[MiningCandidate], MiningRunManifest]:
    """
    Mine patterns from back/nodes/ directory.
    
    Args:
        nodes_dir: Path to back/nodes/ directory
        output_dir: Path to output artifacts directory
        run_id: Unique identifier for this mining run
        verbose: Print verbose output
        
    Returns:
        Tuple of (candidates, manifest)
    """
    candidates: list[MiningCandidate] = []
    files_processed: list[str] = []
    errors: list[str] = []
    
    if not nodes_dir.exists():
        errors.append(f"Nodes directory not found: {nodes_dir}")
        manifest = MiningRunManifest(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            script_name="mine_back_nodes.py",
            inputs=[str(nodes_dir)],
            candidate_count=0,
            git_commit=None,
        )
        return candidates, manifest

    # Find all Python files in nodes directory
    node_files = sorted(nodes_dir.glob("*.py"))
    
    if verbose:
        print(f"Found {len(node_files)} Python files in {nodes_dir}")

    for file_path in node_files:
        if file_path.name.startswith("_"):
            continue  # Skip __init__.py and similar
            
        files_processed.append(str(file_path))
        
        if verbose:
            print(f"  Processing: {file_path.name}")
        
        patterns = extract_patterns_from_file(file_path)
        
        for pattern in patterns:
            if pattern.get("type") == "error":
                errors.append(pattern.get("message", "Unknown error"))
                continue
            elif pattern.get("type") == "warning":
                if verbose:
                    print(f"    Warning: {pattern.get('message')}")
                continue
            
            candidate = pattern_to_candidate(pattern, file_path, run_id)
            if candidate:
                # Validate before adding
                validation_errors = validate_candidate(candidate)
                if not validation_errors:
                    candidates.append(candidate)
                    if verbose:
                        print(f"    Found: {candidate.title} ({candidate.category})")
                else:
                    errors.extend(validation_errors)

    # Deduplicate by pattern hash
    seen_hashes: set[str] = set()
    unique_candidates: list[MiningCandidate] = []
    for c in candidates:
        pattern_hash = hashlib.sha256(
            json.dumps(c.pattern, sort_keys=True).encode()
        ).hexdigest()[:16]
        if pattern_hash not in seen_hashes:
            seen_hashes.add(pattern_hash)
            unique_candidates.append(c)
        elif verbose:
            print(f"    Dedup: {c.title}")

    candidates = unique_candidates

    # Create manifest
    manifest = MiningRunManifest(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        script_name="mine_back_nodes.py",
        inputs=[str(nodes_dir)],
        candidate_count=len(candidates),
        git_commit=None,
    )

    return candidates, manifest


def write_outputs(
    candidates: list[MiningCandidate],
    manifest: MiningRunManifest,
    output_dir: Path,
    verbose: bool = False,
) -> None:
    """Write candidates and manifest to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Write manifest
    manifest_path = output_dir / "manifest.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(manifest.to_json())
    if verbose:
        print(f"Wrote manifest: {manifest_path}")

    # Write candidates
    candidates_dir = output_dir / "promotion_candidates"
    candidates_dir.mkdir(exist_ok=True)
    
    for candidate in candidates:
        candidate_path = candidates_dir / f"{candidate.candidate_id}.json"
        with open(candidate_path, "w", encoding="utf-8") as f:
            f.write(candidate.to_json())
    
    if verbose:
        print(f"Wrote {len(candidates)} candidates to {candidates_dir}")

    # Write summary
    summary_path = output_dir / "summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write(f"# Mining Run: {manifest.run_id}\n\n")
        f.write(f"**Script:** {manifest.script_name}\n")
        f.write(f"**Timestamp:** {manifest.timestamp}\n")
        f.write(f"**Inputs:** {len(manifest.inputs)}\n")
        f.write(f"**Candidates Generated:** {manifest.candidate_count}\n\n")
        
        f.write("## Candidates by Category\n\n")
        by_category: dict[str, list[MiningCandidate]] = {}
        for c in candidates:
            by_category.setdefault(c.category, []).append(c)
        
        for category in sorted(by_category.keys()):
            f.write(f"### {category}\n\n")
            for c in by_category[category]:
                f.write(f"- **{c.title}**\n")
                f.write(f"  - Confidence: {c.confidence:.1%}\n")
                if c.provenance:
                    f.write(f"  - Source: `{c.provenance[0].path}`\n")
            f.write("\n")
    
    if verbose:
        print(f"Wrote summary: {summary_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Mine patterns from back/nodes/ Python files"
    )
    parser.add_argument(
        "--nodes-dir",
        type=Path,
        required=True,
        help="Path to back/nodes/ directory",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory (default: artifacts/<run_id>/)",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        help="Mining run ID (auto-generated if not provided)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Generate run ID if not provided
    run_id = args.run_id or f"mine-nodes-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    # Set output directory
    output_dir = args.output_dir or Path("artifacts") / run_id

    if args.verbose:
        print(f"Mining run: {run_id}")
        print(f"Nodes dir: {args.nodes_dir}")
        print(f"Output dir: {output_dir}")
        print()

    # Run mining
    candidates, manifest = mine_back_nodes(
        nodes_dir=args.nodes_dir,
        output_dir=output_dir,
        run_id=run_id,
        verbose=args.verbose,
    )

    # Write outputs
    write_outputs(candidates, manifest, output_dir, verbose=args.verbose)

    # Print summary
    print(f"\nMining complete: {manifest.candidates_generated} candidates")
    if manifest.errors:
        print(f"Errors: {len(manifest.errors)}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
