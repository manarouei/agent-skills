#!/usr/bin/env python3
"""
mine_fix_candidates.py - Script D: Deduplicate and consolidate fix candidates

Processes fix candidates emitted by code-fix skill during pipeline runs:
- Deduplicates by error signature
- Aggregates occurrence counts
- Ranks by frequency and success rate
- Outputs consolidated candidates for promotion review

Output: Promotion candidates in artifacts/<run_id>/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
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
# Fix Candidate Schema (from runtime/learning_loop.py)
# ---------------------------------------------------------------------------


def validate_fix_candidate(candidate: dict[str, Any]) -> bool:
    """Validate a fix candidate from learning loop."""
    required_fields = {"error_signature", "fix_pattern"}
    return all(f in candidate for f in required_fields)


def compute_error_signature(error: dict[str, Any]) -> str:
    """Compute deduplication signature for an error."""
    # Components: error type, normalized message pattern, file pattern
    error_type = error.get("type", "unknown")
    message = error.get("message", "")
    file_path = error.get("file", "")
    
    # Normalize message by removing line numbers and specific values
    import re
    normalized_message = re.sub(r'\d+', 'N', message)
    normalized_message = re.sub(r'"[^"]*"', '"..."', normalized_message)
    normalized_message = re.sub(r"'[^']*'", "'...'", normalized_message)
    
    # Normalize file path to pattern
    if file_path:
        file_pattern = Path(file_path).suffix or "unknown"
    else:
        file_pattern = "unknown"
    
    sig_input = f"{error_type}:{normalized_message}:{file_pattern}"
    return hashlib.sha256(sig_input.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Fix Candidate Processing
# ---------------------------------------------------------------------------


def load_fix_candidates(
    artifacts_dir: Path,
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """Load all fix candidates from artifacts directory."""
    candidates: list[dict[str, Any]] = []
    
    # Look for fix_candidate*.json files in artifact directories
    patterns = [
        "**/fix_candidate*.json",
        "**/promotion_candidates/*fix*.json",
        "**/code_fix_output.json",
    ]
    
    seen_files: set[str] = set()
    
    for pattern in patterns:
        for file_path in artifacts_dir.glob(pattern):
            if str(file_path) in seen_files:
                continue
            seen_files.add(str(file_path))
            
            if verbose:
                print(f"  Loading: {file_path}")
            
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                if verbose:
                    print(f"    Skipped: invalid JSON")
                continue
            except Exception as e:
                if verbose:
                    print(f"    Error: {e}")
                continue
            
            # Handle both single candidates and lists
            if isinstance(data, list):
                for item in data:
                    if validate_fix_candidate(item):
                        item["_source_file"] = str(file_path)
                        candidates.append(item)
            elif isinstance(data, dict):
                # Check if it's a wrapped format
                if "fix_candidates" in data:
                    for item in data["fix_candidates"]:
                        if validate_fix_candidate(item):
                            item["_source_file"] = str(file_path)
                            candidates.append(item)
                elif validate_fix_candidate(data):
                    data["_source_file"] = str(file_path)
                    candidates.append(data)
            
            if verbose:
                print(f"    Found {len(candidates)} candidates total")
    
    return candidates


def deduplicate_fixes(
    fix_candidates: list[dict[str, Any]],
    verbose: bool = False,
) -> list[dict[str, Any]]:
    """
    Deduplicate fix candidates by error signature.
    
    Groups identical fixes and tracks occurrence counts.
    """
    # Group by error signature
    by_signature: dict[str, list[dict[str, Any]]] = {}
    
    for candidate in fix_candidates:
        error = candidate.get("error", {})
        if not error:
            # Try to extract error from error_signature directly
            sig = candidate.get("error_signature", "")
        else:
            sig = compute_error_signature(error)
        
        if not sig:
            sig = compute_error_signature(candidate)
        
        by_signature.setdefault(sig, []).append(candidate)
    
    if verbose:
        print(f"Grouped into {len(by_signature)} unique signatures")
    
    # Create consolidated candidates
    consolidated: list[dict[str, Any]] = []
    
    for sig, group in by_signature.items():
        # Find the "best" representative (highest success rate or most recent)
        best = max(group, key=lambda c: (
            c.get("success_rate", 0),
            c.get("timestamp", ""),
        ))
        
        # Aggregate statistics
        total_occurrences = len(group)
        success_count = sum(1 for c in group if c.get("success", False))
        
        consolidated_candidate = {
            "error_signature": sig,
            "fix_pattern": best.get("fix_pattern", {}),
            "error": best.get("error", {}),
            "category": best.get("category", "service_quirk"),
            "description": best.get("description", f"Fix pattern for error signature {sig[:8]}"),
            "occurrences": total_occurrences,
            "success_count": success_count,
            "success_rate": success_count / total_occurrences if total_occurrences > 0 else 0,
            "source_files": list(set(c.get("_source_file", "") for c in group))[:5],
            "first_seen": min(c.get("timestamp", "") for c in group if c.get("timestamp")),
            "last_seen": max(c.get("timestamp", "") for c in group if c.get("timestamp")),
        }
        
        consolidated.append(consolidated_candidate)
    
    # Sort by occurrence count (most common first)
    consolidated.sort(key=lambda c: c.get("occurrences", 0), reverse=True)
    
    return consolidated


def fix_to_mining_candidate(
    fix: dict[str, Any],
    run_id: str,
) -> MiningCandidate:
    """Convert consolidated fix to MiningCandidate."""
    sig = fix.get("error_signature", "unknown")
    category = normalize_category(fix.get("category", "service_quirk"))
    
    source_refs = [
        SourceReference(
            kind=SourceKind.FIX_LOOP,
            path=sf,
        )
        for sf in fix.get("source_files", [])[:3]  # Limit refs
    ]
    
    # Calculate confidence from success rate
    success_rate = fix.get("success_rate", 0)
    if success_rate >= 0.8:
        confidence = 0.9
    elif success_rate >= 0.5:
        confidence = 0.6
    else:
        confidence = 0.3
    
    # Build stats
    stats = CandidateStats(
        occurrences=fix.get("occurrences", 1),
        success_rate=success_rate,
        last_seen=fix.get("last_seen"),
    )
    
    candidate = MiningCandidate(
        candidate_id=generate_candidate_id(category, f"fix-{sig}"),
        candidate_type=CandidateType.FIX,
        category=category,
        title=f"fix_{sig[:8]}",
        pattern={
            "error_signature": sig,
            "fix_pattern": fix.get("fix_pattern", {}),
            "error_sample": fix.get("error", {}),
        },
        provenance=source_refs,
        confidence=confidence,
        stats=stats,
        mining_run_id=run_id,
        review_notes=ReviewNotes(),
    )
    
    return candidate


# ---------------------------------------------------------------------------
# Main Mining Logic
# ---------------------------------------------------------------------------


def mine_fix_candidates(
    artifacts_dir: Path,
    output_dir: Path,
    run_id: str,
    min_occurrences: int = 1,
    min_success_rate: float = 0.0,
    verbose: bool = False,
) -> tuple[list[MiningCandidate], MiningRunManifest]:
    """
    Mine and consolidate fix candidates from artifacts.
    
    Args:
        artifacts_dir: Path to artifacts/ directory
        output_dir: Path to output artifacts directory
        run_id: Unique identifier for this mining run
        min_occurrences: Minimum occurrences to include (default: 1)
        min_success_rate: Minimum success rate to include (default: 0.0)
        verbose: Print verbose output
        
    Returns:
        Tuple of (candidates, manifest)
    """
    candidates: list[MiningCandidate] = []
    files_processed: list[str] = []
    errors: list[str] = []
    
    if not artifacts_dir.exists():
        errors.append(f"Artifacts directory not found: {artifacts_dir}")
        manifest = MiningRunManifest(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            script_name="mine_fix_candidates.py",
            inputs=[str(artifacts_dir)],
            candidate_count=0,
            git_commit=None,
        )
        return candidates, manifest

    if verbose:
        print(f"Scanning {artifacts_dir} for fix candidates...")

    # Load all fix candidates
    fix_candidates = load_fix_candidates(artifacts_dir, verbose)
    
    if verbose:
        print(f"\nLoaded {len(fix_candidates)} raw fix candidates")
    
    if not fix_candidates:
        errors.append("No fix candidates found in artifacts")
        manifest = MiningRunManifest(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            script_name="mine_fix_candidates.py",
            inputs=[str(artifacts_dir)],
            candidate_count=0,
            git_commit=None,
        )
        return candidates, manifest
    
    # Track processed files
    files_processed = list(set(c.get("_source_file", "") for c in fix_candidates))

    # Deduplicate and consolidate
    if verbose:
        print("\nDeduplicating fixes...")
    
    consolidated = deduplicate_fixes(fix_candidates, verbose)
    
    if verbose:
        print(f"Consolidated to {len(consolidated)} unique fix patterns")

    # Filter and convert to mining candidates
    if verbose:
        print(f"\nFiltering (min_occurrences={min_occurrences}, min_success_rate={min_success_rate})...")
    
    for fix in consolidated:
        # Apply filters
        if fix.get("occurrences", 0) < min_occurrences:
            continue
        if fix.get("success_rate", 0) < min_success_rate:
            continue
        
        candidate = fix_to_mining_candidate(fix, run_id)
        
        # Validate
        validation_errors = validate_candidate(candidate)
        if not validation_errors:
            candidates.append(candidate)
            if verbose:
                print(f"  Added: {candidate.title} (occ={fix.get('occurrences')}, success={fix.get('success_rate', 0):.1%})")
        else:
            errors.extend(validation_errors)

    # Create manifest
    manifest = MiningRunManifest(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        script_name="mine_fix_candidates.py",
        inputs=[str(artifacts_dir)],
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
        f.write(f"**Fix Candidates Generated:** {manifest.candidate_count}\n\n")
        
        f.write("## Fix Patterns by Confidence\n\n")
        by_confidence: dict[str, list[MiningCandidate]] = {}
        for c in candidates:
            conf_level = "high" if c.confidence >= 0.8 else "medium" if c.confidence >= 0.5 else "low"
            by_confidence.setdefault(conf_level, []).append(c)
        
        for confidence in ["high", "medium", "low"]:
            if confidence not in by_confidence:
                continue
            f.write(f"### {confidence.title()} Confidence\n\n")
            for c in by_confidence[confidence]:
                stats = c.stats
                occ = stats.occurrences if stats else 0
                rate = stats.success_rate if stats else 0
                f.write(f"- **{c.title}**\n")
                f.write(f"  - Occurrences: {occ}\n")
                f.write(f"  - Success rate: {rate:.1%}\n")
                if c.pattern.get("error_sample"):
                    err = c.pattern["error_sample"]
                    f.write(f"  - Error type: {err.get('type', 'unknown')}\n")
            f.write("\n")
        
        # Add recommendations
        f.write("## Promotion Recommendations\n\n")
        high_value = [c for c in candidates if c.confidence >= 0.8 and 
                     c.stats and c.stats.occurrences >= 3]
        if high_value:
            f.write("The following fixes are recommended for promotion:\n\n")
            for c in high_value[:5]:
                f.write(f"- `{c.candidate_id}` - {c.title}\n")
        else:
            f.write("No high-confidence fixes with sufficient occurrences found.\n")
    
    if verbose:
        print(f"Wrote summary: {summary_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Mine and consolidate fix candidates from artifacts"
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=Path("artifacts"),
        help="Path to artifacts/ directory (default: artifacts/)",
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
        "--min-occurrences",
        type=int,
        default=1,
        help="Minimum occurrences to include (default: 1)",
    )
    parser.add_argument(
        "--min-success-rate",
        type=float,
        default=0.0,
        help="Minimum success rate to include (default: 0.0)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Generate run ID if not provided
    run_id = args.run_id or f"mine-fixes-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    # Set output directory
    output_dir = args.output_dir or Path("artifacts") / run_id

    if args.verbose:
        print(f"Mining run: {run_id}")
        print(f"Artifacts dir: {args.artifacts_dir}")
        print(f"Output dir: {output_dir}")
        print(f"Min occurrences: {args.min_occurrences}")
        print(f"Min success rate: {args.min_success_rate}")
        print()

    # Run mining
    candidates, manifest = mine_fix_candidates(
        artifacts_dir=args.artifacts_dir,
        output_dir=output_dir,
        run_id=run_id,
        min_occurrences=args.min_occurrences,
        min_success_rate=args.min_success_rate,
        verbose=args.verbose,
    )

    # Write outputs
    write_outputs(candidates, manifest, output_dir, verbose=args.verbose)

    # Print summary
    print(f"\nMining complete: {manifest.candidates_generated} fix candidates")
    if manifest.errors:
        print(f"Errors: {len(manifest.errors)}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
