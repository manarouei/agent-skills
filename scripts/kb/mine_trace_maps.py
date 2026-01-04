#!/usr/bin/env python3
"""
mine_trace_maps.py - Script C: Mine patterns from trace_map.json files

Aggregates trace map entries from pipeline artifacts to extract:
- TypeScript to Python conversion patterns
- Common field naming conventions
- Source evidence patterns

Output: Promotion candidates in artifacts/<run_id>/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
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
# Trace Map Entry Schema (from .copilot/schemas/trace_map.schema.json)
# ---------------------------------------------------------------------------

VALID_SOURCES = {"SOURCE_CODE", "API_DOCS", "ASSUMPTION"}


def validate_trace_entry(entry: dict[str, Any]) -> bool:
    """Validate a single trace entry."""
    required_fields = {"field_path", "source", "evidence"}
    if not all(f in entry for f in required_fields):
        return False
    if entry.get("source") not in VALID_SOURCES:
        return False
    return True


# ---------------------------------------------------------------------------
# Pattern Extraction from Trace Maps
# ---------------------------------------------------------------------------


def extract_ts_to_python_patterns(
    trace_entries: list[dict[str, Any]],
    source_file: str,
) -> list[dict[str, Any]]:
    """
    Extract TypeScript to Python conversion patterns from trace entries.
    
    Looks for evidence strings that indicate:
    - Type conversions (string -> str, number -> int/float)
    - Naming conventions (camelCase -> snake_case)
    - Interface to dataclass mappings
    """
    patterns: list[dict[str, Any]] = []
    
    # Track naming conversions
    naming_conversions: list[dict[str, str]] = []
    type_mappings: list[dict[str, str]] = []
    
    for entry in trace_entries:
        if not validate_trace_entry(entry):
            continue
            
        evidence = entry.get("evidence", "")
        field_path = entry.get("field_path", "")
        source = entry.get("source", "")
        
        # Skip assumption-only entries for pattern extraction
        if source == "ASSUMPTION":
            continue
        
        # Detect camelCase to snake_case conversions
        # Look for patterns like "getName -> get_name" or "myField -> my_field"
        camel_match = re.search(
            r'(\b[a-z]+[A-Z][a-zA-Z]*\b)\s*(?:->|→|becomes?|converts?\s+to)\s*(\b[a-z_]+\b)',
            evidence,
            re.IGNORECASE,
        )
        if camel_match:
            naming_conversions.append({
                "from": camel_match.group(1),
                "to": camel_match.group(2),
                "context": field_path,
            })
        
        # Detect TypeScript type to Python type mappings
        type_patterns = [
            (r'string\s*(?:->|→|to)\s*str', "string", "str"),
            (r'number\s*(?:->|→|to)\s*(?:int|float)', "number", "int|float"),
            (r'boolean\s*(?:->|→|to)\s*bool', "boolean", "bool"),
            (r'Array<[^>]+>\s*(?:->|→|to)\s*(?:list|List)', "Array", "list"),
            (r'Record<[^>]+>\s*(?:->|→|to)\s*(?:dict|Dict)', "Record", "dict"),
            (r'Promise<[^>]+>\s*(?:->|→|to)\s*', "Promise", "sync"),
            (r'interface\s+(\w+)\s*(?:->|→|becomes?)\s*(?:class|dataclass)', "interface", "dataclass"),
        ]
        
        for pattern, ts_type, py_type in type_patterns:
            if re.search(pattern, evidence, re.IGNORECASE):
                type_mappings.append({
                    "ts_type": ts_type,
                    "py_type": py_type,
                    "evidence": evidence[:200],  # Truncate long evidence
                })

    # Aggregate naming conversions into patterns
    if naming_conversions:
        # Group by conversion style
        conversion_styles: dict[str, list[dict[str, str]]] = {}
        for conv in naming_conversions:
            # Determine style (camelCase, PascalCase, etc.)
            from_name = conv["from"]
            if from_name[0].isupper():
                style = "PascalCase_to_snake"
            else:
                style = "camelCase_to_snake"
            conversion_styles.setdefault(style, []).append(conv)
        
        for style, conversions in conversion_styles.items():
            patterns.append({
                "type": "pattern",
                "category": "ts_to_python",
                "name": f"naming_{style}",
                "description": f"Naming conversion pattern: {style}",
                "pattern_data": {
                    "style": style,
                    "examples": conversions[:10],  # Limit examples
                    "count": len(conversions),
                },
                "source_file": source_file,
            })

    # Aggregate type mappings into patterns
    if type_mappings:
        # Group by ts_type
        by_ts_type: dict[str, list[dict[str, str]]] = {}
        for mapping in type_mappings:
            by_ts_type.setdefault(mapping["ts_type"], []).append(mapping)
        
        for ts_type, mappings in by_ts_type.items():
            patterns.append({
                "type": "pattern",
                "category": "ts_to_python",
                "name": f"type_{ts_type}_conversion",
                "description": f"Type conversion: TypeScript {ts_type} to Python",
                "pattern_data": {
                    "ts_type": ts_type,
                    "py_types": list(set(m["py_type"] for m in mappings)),
                    "example_evidence": mappings[0].get("evidence", "")[:200],
                    "count": len(mappings),
                },
                "source_file": source_file,
            })

    return patterns


def extract_field_evidence_patterns(
    trace_entries: list[dict[str, Any]],
    source_file: str,
) -> list[dict[str, Any]]:
    """Extract patterns about how evidence is structured."""
    patterns: list[dict[str, Any]] = []
    
    # Count source types
    source_counts: Counter[str] = Counter()
    high_confidence: list[dict[str, Any]] = []
    
    for entry in trace_entries:
        if not validate_trace_entry(entry):
            continue
        
        source = entry.get("source", "")
        source_counts[source] += 1
        
        # Track high-confidence SOURCE_CODE entries
        if source == "SOURCE_CODE" and entry.get("confidence") == "high":
            high_confidence.append({
                "field_path": entry.get("field_path"),
                "source_file": entry.get("source_file"),
                "line_range": entry.get("line_range"),
            })

    # Only create pattern if we have meaningful data
    total_entries = sum(source_counts.values())
    if total_entries >= 3:  # Minimum threshold
        assumption_pct = source_counts.get("ASSUMPTION", 0) / total_entries * 100
        
        patterns.append({
            "type": "pattern",
            "category": "service_quirk",
            "name": f"evidence_quality_{Path(source_file).stem}",
            "description": f"Evidence quality statistics for trace map",
            "pattern_data": {
                "total_entries": total_entries,
                "source_code_count": source_counts.get("SOURCE_CODE", 0),
                "api_docs_count": source_counts.get("API_DOCS", 0),
                "assumption_count": source_counts.get("ASSUMPTION", 0),
                "assumption_percentage": round(assumption_pct, 1),
                "high_confidence_examples": high_confidence[:5],
            },
            "source_file": source_file,
        })

    return patterns


# ---------------------------------------------------------------------------
# Candidate Generation
# ---------------------------------------------------------------------------


def pattern_to_candidate(
    pattern: dict[str, Any],
    run_id: str,
) -> MiningCandidate | None:
    """Convert extracted pattern to MiningCandidate."""
    if pattern.get("type") != "pattern":
        return None

    category = normalize_category(pattern.get("category", "ts_to_python"))
    name = pattern.get("name", "unknown_pattern")

    source_ref = SourceReference(
        kind=SourceKind.TRACE_MAP,
        path=pattern.get("source_file", ""),
    )

    # Hash the pattern data for deduplication
    pattern_data = pattern.get("pattern_data", {})
    pattern_json = json.dumps(pattern_data, sort_keys=True)
    content_hash = hashlib.sha256(pattern_json.encode()).hexdigest()[:16]

    candidate = MiningCandidate(
        candidate_id=generate_candidate_id(category, f"{name}-{content_hash}"),
        candidate_type=CandidateType.PATTERN,
        category=category,
        title=name,
        pattern=pattern_data,
        provenance=[source_ref],
        confidence=0.6,
        mining_run_id=run_id,
        stats=CandidateStats(),
        review_notes=ReviewNotes(),
    )

    return candidate


# ---------------------------------------------------------------------------
# Main Mining Logic
# ---------------------------------------------------------------------------


def mine_trace_maps(
    artifacts_dir: Path,
    output_dir: Path,
    run_id: str,
    verbose: bool = False,
) -> tuple[list[MiningCandidate], MiningRunManifest]:
    """
    Mine patterns from trace_map.json files in artifacts.
    
    Args:
        artifacts_dir: Path to artifacts/ directory
        output_dir: Path to output artifacts directory
        run_id: Unique identifier for this mining run
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
            script_name="mine_trace_maps.py",
            inputs=[str(artifacts_dir)],
            candidate_count=0,
            git_commit=None,
        )
        return candidates, manifest

    # Find all trace_map.json files
    trace_map_files = sorted(artifacts_dir.glob("**/trace_map.json"))
    
    if verbose:
        print(f"Found {len(trace_map_files)} trace_map.json files in {artifacts_dir}")

    all_ts_patterns: list[dict[str, Any]] = []
    all_evidence_patterns: list[dict[str, Any]] = []

    for file_path in trace_map_files:
        files_processed.append(str(file_path))
        
        if verbose:
            print(f"  Processing: {file_path}")
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                trace_map = json.load(f)
        except json.JSONDecodeError as e:
            errors.append(f"JSON error in {file_path}: {e}")
            continue
        except Exception as e:
            errors.append(f"Error reading {file_path}: {e}")
            continue

        # Get trace entries
        trace_entries = trace_map.get("trace_entries", [])
        if not trace_entries:
            if verbose:
                print(f"    No trace entries found")
            continue

        if verbose:
            print(f"    Found {len(trace_entries)} trace entries")

        # Extract patterns
        ts_patterns = extract_ts_to_python_patterns(trace_entries, str(file_path))
        evidence_patterns = extract_field_evidence_patterns(trace_entries, str(file_path))
        
        all_ts_patterns.extend(ts_patterns)
        all_evidence_patterns.extend(evidence_patterns)
        
        if verbose:
            print(f"    Extracted {len(ts_patterns)} ts_to_python patterns")
            print(f"    Extracted {len(evidence_patterns)} evidence patterns")

    # Aggregate similar patterns across files
    aggregated_patterns = aggregate_patterns(all_ts_patterns + all_evidence_patterns)
    
    if verbose:
        print(f"\nAggregated to {len(aggregated_patterns)} unique patterns")

    # Convert to candidates
    for pattern in aggregated_patterns:
        candidate = pattern_to_candidate(pattern, run_id)
        if candidate:
            validation_errors = validate_candidate(candidate)
            if not validation_errors:
                candidates.append(candidate)
                if verbose:
                    print(f"  Created candidate: {candidate.title}")
            else:
                errors.extend(validation_errors)

    # Create manifest
    manifest = MiningRunManifest(
        run_id=run_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        script_name="mine_trace_maps.py",
        inputs=[str(artifacts_dir)],
        candidate_count=len(candidates),
        git_commit=None,
    )

    return candidates, manifest


def aggregate_patterns(patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate similar patterns from multiple trace maps."""
    # Group by name
    by_name: dict[str, list[dict[str, Any]]] = {}
    for p in patterns:
        name = p.get("name", "unknown")
        by_name.setdefault(name, []).append(p)
    
    aggregated: list[dict[str, Any]] = []
    
    for name, group in by_name.items():
        if len(group) == 1:
            aggregated.append(group[0])
        else:
            # Merge pattern data
            merged = group[0].copy()
            merged_data = merged.get("pattern_data", {}).copy()
            
            # Aggregate counts
            if "count" in merged_data:
                merged_data["count"] = sum(
                    p.get("pattern_data", {}).get("count", 0)
                    for p in group
                )
            
            # Merge examples (limit to 10)
            if "examples" in merged_data:
                all_examples = []
                for p in group:
                    all_examples.extend(
                        p.get("pattern_data", {}).get("examples", [])
                    )
                merged_data["examples"] = all_examples[:10]
            
            # Track source files
            merged_data["source_files"] = [
                p.get("source_file", "") for p in group
            ][:5]  # Limit
            
            merged["pattern_data"] = merged_data
            merged["description"] = f"{merged['description']} (aggregated from {len(group)} sources)"
            aggregated.append(merged)
    
    return aggregated


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
        
        f.write("## Pattern Categories\n\n")
        by_category: dict[str, list[MiningCandidate]] = {}
        for c in candidates:
            by_category.setdefault(c.category, []).append(c)
        
        for category in sorted(by_category.keys()):
            f.write(f"### {category}\n\n")
            for c in by_category[category]:
                f.write(f"- **{c.title}**\n")
                pd = c.pattern
                if "count" in pd:
                    f.write(f"  - Occurrences: {pd['count']}\n")
                if "examples" in pd and pd["examples"]:
                    f.write(f"  - Example: `{pd['examples'][0]}`\n")
            f.write("\n")
    
    if verbose:
        print(f"Wrote summary: {summary_path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Mine patterns from trace_map.json files in artifacts"
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
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Generate run ID if not provided
    run_id = args.run_id or f"mine-traces-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

    # Set output directory
    output_dir = args.output_dir or Path("artifacts") / run_id

    if args.verbose:
        print(f"Mining run: {run_id}")
        print(f"Artifacts dir: {args.artifacts_dir}")
        print(f"Output dir: {output_dir}")
        print()

    # Run mining
    candidates, manifest = mine_trace_maps(
        artifacts_dir=args.artifacts_dir,
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
