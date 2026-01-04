#!/usr/bin/env python3
"""
mine_back_credentials.py - Script B: Mine patterns from back/credentials/*.py

Parses credential implementations using AST to extract:
- Required credential fields (name, type)
- Auth placement (header, query, body)
- URL templates
- Token refresh patterns

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
from runtime.kb.loader import normalize_category


# ---------------------------------------------------------------------------
# AST Pattern Extractors for Credentials
# ---------------------------------------------------------------------------


class CredentialPatternExtractor(ast.NodeVisitor):
    """Extract patterns from a credential file."""

    def __init__(self, file_path: Path, source_code: str) -> None:
        self.file_path = file_path
        self.source_code = source_code
        self.lines = source_code.splitlines()
        self.patterns: list[dict[str, Any]] = []
        self.current_class: str | None = None

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
        """Extract credential class patterns."""
        self.current_class = node.name
        
        # Check if this looks like a credential class
        is_credential_class = any(
            "credential" in base_name.lower()
            for base_name in self._get_base_class_names(node)
        ) or "credential" in node.name.lower()

        if is_credential_class:
            self._extract_credential_class_pattern(node)

        self.generic_visit(node)
        self.current_class = None

    def _get_base_class_names(self, node: ast.ClassDef) -> list[str]:
        """Get names of base classes."""
        names = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                names.append(base.id)
            elif isinstance(base, ast.Attribute):
                names.append(base.attr)
        return names

    def _extract_credential_class_pattern(self, node: ast.ClassDef) -> None:
        """Extract authentication pattern from a credential class."""
        excerpt = self._get_source_excerpt(node)
        
        cred_info: dict[str, Any] = {
            "class_name": node.name,
            "fields": [],
            "auth_placement": "unknown",
            "auth_type": "unknown",
            "has_refresh": False,
            "url_template": None,
        }

        # Find class attributes and assignments
        for child in node.body:
            # Class-level assignments (field definitions)
            if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                field_name = child.target.id
                field_type = self._get_annotation_type(child.annotation)
                cred_info["fields"].append({
                    "name": field_name,
                    "type": field_type,
                    "required": child.value is None,
                })
            
            # Simple assignments
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        self._analyze_assignment(target.id, child.value, cred_info)

            # Method definitions
            elif isinstance(child, ast.FunctionDef):
                self._analyze_method(child, cred_info)

        # Determine auth type from class name or fields
        cred_info["auth_type"] = self._infer_auth_type(node.name, cred_info["fields"])

        if cred_info["fields"] or cred_info["auth_type"] != "unknown":
            self.patterns.append({
                "type": "pattern",
                "category": "auth",
                "name": f"{node.name}_auth",
                "description": f"Authentication pattern for {node.name}",
                "pattern_data": cred_info,
                "line_range": self._get_line_range(node),
                "excerpt": excerpt,
                "excerpt_hash": self._hash_excerpt(excerpt),
            })

    def _get_annotation_type(self, annotation: ast.expr | None) -> str:
        """Convert type annotation to string."""
        if annotation is None:
            return "Any"
        if isinstance(annotation, ast.Name):
            return annotation.id
        if isinstance(annotation, ast.Constant):
            return str(annotation.value)
        if isinstance(annotation, ast.Subscript):
            if isinstance(annotation.value, ast.Name):
                return f"{annotation.value.id}[...]"
        return "complex"

    def _analyze_assignment(
        self,
        name: str,
        value: ast.expr,
        cred_info: dict[str, Any],
    ) -> None:
        """Analyze class-level assignment for patterns."""
        name_lower = name.lower()
        
        # Look for auth placement hints
        if "header" in name_lower:
            cred_info["auth_placement"] = "header"
        elif "query" in name_lower or "param" in name_lower:
            cred_info["auth_placement"] = "query"
        elif "body" in name_lower:
            cred_info["auth_placement"] = "body"

        # Look for URL templates
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            if "{" in value.value and ("url" in name_lower or "endpoint" in name_lower):
                cred_info["url_template"] = value.value

    def _analyze_method(
        self,
        node: ast.FunctionDef,
        cred_info: dict[str, Any],
    ) -> None:
        """Analyze method for auth patterns."""
        method_name = node.name.lower()
        
        # Check for refresh token method
        if "refresh" in method_name:
            cred_info["has_refresh"] = True
        
        # Check for auth header building
        if "header" in method_name or "auth" in method_name:
            cred_info["auth_placement"] = "header"
            
            # Try to extract header format
            for child in ast.walk(node):
                if isinstance(child, ast.Dict):
                    for key in child.keys:
                        if isinstance(key, ast.Constant) and isinstance(key.value, str):
                            key_lower = key.value.lower()
                            if "authorization" in key_lower:
                                cred_info["auth_placement"] = "header:authorization"
                            elif "x-api-key" in key_lower:
                                cred_info["auth_placement"] = "header:x-api-key"

    def _infer_auth_type(self, class_name: str, fields: list[dict[str, Any]]) -> str:
        """Infer authentication type from class name and fields."""
        name_lower = class_name.lower()
        field_names = [f["name"].lower() for f in fields]
        
        # OAuth patterns
        if "oauth" in name_lower or "oauth2" in name_lower:
            return "oauth2"
        if "access_token" in field_names or "refresh_token" in field_names:
            return "oauth2"
        
        # API key patterns
        if "apikey" in name_lower or "api_key" in field_names:
            return "api_key"
        
        # Bearer token
        if "bearer" in name_lower or "token" in field_names:
            return "bearer"
        
        # Basic auth
        if "basic" in name_lower:
            return "basic"
        if "username" in field_names and "password" in field_names:
            return "basic"
        
        return "unknown"


def extract_patterns_from_file(file_path: Path) -> list[dict[str, Any]]:
    """Extract all patterns from a single Python file."""
    try:
        source_code = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code, filename=str(file_path))
        
        extractor = CredentialPatternExtractor(file_path, source_code)
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

    category = normalize_category(pattern.get("category", "auth"))
    name = pattern.get("name", "unknown_pattern")

    source_ref = SourceReference(
        kind=SourceKind.CREDENTIAL_FILE,
        path=str(source_file),
        line_range=pattern.get("line_range"),
        excerpt_hash=pattern.get("excerpt_hash"),
    )

    # Hash the pattern data for deduplication
    pattern_json = json.dumps(pattern.get("pattern_data", {}), sort_keys=True)
    content_hash = hashlib.sha256(pattern_json.encode()).hexdigest()[:16]

    candidate = MiningCandidate(
        candidate_id=generate_candidate_id(category, f"{name}-{content_hash}"),
        candidate_type=CandidateType.PATTERN,
        category=category,
        title=name,
        pattern=pattern.get("pattern_data", {}),
        provenance=[source_ref],
        confidence=0.8,  # Credential patterns are well-structured
        mining_run_id=run_id,
        stats=CandidateStats(),
        review_notes=ReviewNotes(),
    )

    return candidate


# ---------------------------------------------------------------------------
# Main Mining Logic
# ---------------------------------------------------------------------------


def mine_back_credentials(
    credentials_dir: Path,
    output_dir: Path,
    run_id: str,
    verbose: bool = False,
) -> tuple[list[MiningCandidate], MiningRunManifest]:
    """
    Mine patterns from back/credentials/ directory.
    
    Args:
        credentials_dir: Path to back/credentials/ directory
        output_dir: Path to output artifacts directory
        run_id: Unique identifier for this mining run
        verbose: Print verbose output
        
    Returns:
        Tuple of (candidates, manifest)
    """
    candidates: list[MiningCandidate] = []
    files_processed: list[str] = []
    errors: list[str] = []
    
    if not credentials_dir.exists():
        errors.append(f"Credentials directory not found: {credentials_dir}")
        manifest = MiningRunManifest(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            script_name="mine_back_credentials.py",
            inputs=[str(credentials_dir)],
            candidate_count=0,
            git_commit=None,
        )
        return candidates, manifest

    # Find all Python files in credentials directory
    cred_files = sorted(credentials_dir.glob("*.py"))
    
    if verbose:
        print(f"Found {len(cred_files)} Python files in {credentials_dir}")

    for file_path in cred_files:
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

    # Deduplicate by auth_type + class_name
    seen_keys: set[str] = set()
    unique_candidates: list[MiningCandidate] = []
    for c in candidates:
        pattern_data = c.pattern
        dedup_key = f"{pattern_data.get('auth_type', '')}-{pattern_data.get('class_name', '')}"
        if dedup_key not in seen_keys:
            seen_keys.add(dedup_key)
            unique_candidates.append(c)
        elif verbose:
            print(f"    Dedup: {c.title}")

    candidates = unique_candidates

    # Create manifest
    manifest = MiningRunManifest(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        script_name="mine_back_credentials.py",
        inputs=[str(credentials_dir)],
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
        
        f.write("## Auth Patterns by Type\n\n")
        by_auth_type: dict[str, list[MiningCandidate]] = {}
        for c in candidates:
            auth_type = c.pattern.get("auth_type", "unknown")
            by_auth_type.setdefault(auth_type, []).append(c)
        
        for auth_type in sorted(by_auth_type.keys()):
            f.write(f"### {auth_type}\n\n")
            for c in by_auth_type[auth_type]:
                f.write(f"- **{c.title}**\n")
                pd = c.pattern
                if pd.get("fields"):
                    f.write(f"  - Fields: {', '.join(fld['name'] for fld in pd['fields'])}\n")
                if pd.get("auth_placement") != "unknown":
                    f.write(f"  - Placement: {pd['auth_placement']}\n")
                if pd.get("has_refresh"):
                    f.write(f"  - Has refresh: Yes\n")
            f.write("\n")
    
    if verbose:
        print(f"Wrote summary: {summary_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Mine auth patterns from back/credentials/ Python files"
    )
    parser.add_argument(
        "--credentials-dir",
        type=Path,
        required=True,
        help="Path to back/credentials/ directory",
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
    run_id = args.run_id or f"mine-creds-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    # Set output directory
    output_dir = args.output_dir or Path("artifacts") / run_id

    if args.verbose:
        print(f"Mining run: {run_id}")
        print(f"Credentials dir: {args.credentials_dir}")
        print(f"Output dir: {output_dir}")
        print()

    # Run mining
    candidates, manifest = mine_back_credentials(
        credentials_dir=args.credentials_dir,
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
