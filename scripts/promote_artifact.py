#!/usr/bin/env python3
"""Promote Golden Artifacts to Knowledge Base.

This script promotes validated patterns from golden artifacts, promotion
candidates, or mining run candidates to the Knowledge Base. All promotions 
require human review.

Usage:
    python3 scripts/promote_artifact.py golden <correlation_id> --category <category>
    python3 scripts/promote_artifact.py candidate <candidate_file> [--category <category>]
    python3 scripts/promote_artifact.py mining-run <run_id> [--category <category>] [--all]
    python3 scripts/promote_artifact.py list golden
    python3 scripts/promote_artifact.py list candidates
    python3 scripts/promote_artifact.py list mining-runs

Examples:
    # Promote a golden artifact as an auth pattern
    python3 scripts/promote_artifact.py golden test-123 --category auth

    # Promote a promotion candidate (uses suggested category by default)
    python3 scripts/promote_artifact.py candidate artifacts/promotion_candidates/fix-456.json

    # List mining run candidates
    python3 scripts/promote_artifact.py list mining-runs

    # Promote all candidates from a mining run
    python3 scripts/promote_artifact.py mining-run mine-nodes-20250109-123456 --all

    # Promote specific category from mining run
    python3 scripts/promote_artifact.py mining-run mine-nodes-20250109-123456 --category auth

    # List all golden artifacts
    python3 scripts/promote_artifact.py list golden

    # List all promotion candidates
    python3 scripts/promote_artifact.py list candidates
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from runtime.learning_loop import (
    LearningLoopEmitter,
    GoldenArtifactPackage,
    PromotionCandidate,
)
from runtime.kb import KnowledgeBase, CANONICAL_CATEGORIES
from runtime.kb.candidates import (
    MiningCandidate,
    MiningRunManifest,
    load_candidates_from_dir,
    validate_candidate,
)


def list_golden_artifacts(emitter: LearningLoopEmitter) -> None:
    """List all golden artifacts."""
    artifacts = emitter.list_golden_artifacts()
    if not artifacts:
        print("No golden artifacts found.")
        return
    
    print(f"Found {len(artifacts)} golden artifact(s):\n")
    for artifact_dir in sorted(artifacts):
        manifest_path = artifact_dir / "manifest.json"
        if manifest_path.exists():
            try:
                manifest = json.loads(manifest_path.read_text())
                print(f"  [{artifact_dir.name}]")
                print(f"    Node Type: {manifest.get('node_type', 'unknown')}")
                print(f"    Skill: {manifest.get('skill_name', 'unknown')}")
                print(f"    Created: {manifest.get('created_at', 'unknown')}")
                print(f"    Tests Passed: {manifest.get('tests_passed', False)}")
                print(f"    Fix Iterations: {manifest.get('fix_iterations', 0)}")
                code_files = list(manifest.get('generated_code', {}).keys())
                print(f"    Code Files: {code_files}")
                print()
            except json.JSONDecodeError:
                print(f"  [{artifact_dir.name}] - Invalid manifest")


def list_promotion_candidates(emitter: LearningLoopEmitter) -> None:
    """List all promotion candidates."""
    candidates = emitter.list_promotion_candidates()
    if not candidates:
        print("No promotion candidates found.")
        return
    
    print(f"Found {len(candidates)} promotion candidate(s):\n")
    for candidate_path in sorted(candidates):
        try:
            data = json.loads(candidate_path.read_text())
            print(f"  [{candidate_path.name}]")
            print(f"    Correlation ID: {data.get('correlation_id', 'unknown')}")
            print(f"    Error Category: {data.get('error_category', 'unknown')}")
            print(f"    Suggested Category: {data.get('suggested_category', 'none')}")
            print(f"    Fix Iteration: {data.get('fix_iteration', 1)}")
            print(f"    Created: {data.get('created_at', 'unknown')}")
            error_msg = data.get('error_message', '')[:60]
            print(f"    Error: {error_msg}...")
            print()
        except json.JSONDecodeError:
            print(f"  [{candidate_path.name}] - Invalid JSON")


def promote_golden_artifact(
    emitter: LearningLoopEmitter,
    kb: KnowledgeBase,
    correlation_id: str,
    category: str,
    dry_run: bool = False,
) -> bool:
    """Promote a golden artifact to the KB."""
    # Load the artifact
    package = emitter.load_golden_artifact(correlation_id)
    if package is None:
        print(f"Error: Golden artifact not found: {correlation_id}")
        return False
    
    # Validate category
    if category not in CANONICAL_CATEGORIES:
        print(f"Error: Invalid category '{category}'")
        print(f"Valid categories: {sorted(CANONICAL_CATEGORIES)}")
        return False
    
    # Generate pattern ID
    pattern_id = f"{category}-{uuid.uuid4().hex[:8]}"
    
    # Build pattern from golden artifact
    pattern_data = {
        "id": pattern_id,
        "version": "1.0.0",
        "name": f"Pattern from {package.node_type} node",
        "category": category,
        "description": f"Pattern extracted from golden artifact {correlation_id}",
        "pattern": {
            "node_type": package.node_type,
            "generated_code": package.generated_code,
            "fix_iterations": package.fix_iterations,
        },
        "applicability": {
            "node_types": [package.node_type] if package.node_type != "unknown" else [],
            "services": [],
        },
        "examples": [],
        "confidence": "medium",  # Promoted patterns start at medium until validated
        "sources": [f"golden_artifact:{correlation_id}"],
        "promoted_from": correlation_id,
    }
    
    if dry_run:
        print("\n[DRY RUN] Would create pattern:")
        print(json.dumps(pattern_data, indent=2))
        return True
    
    # Determine target pattern file
    pattern_files = {
        "auth": "auth_patterns.json",
        "pagination": "pagination_patterns.json",
        "ts_to_python": "ts_python_idioms.json",
        "service_quirk": "service_quirk_patterns.json",
    }
    
    target_file = kb.kb_dir / "patterns" / pattern_files.get(category, f"{category}_patterns.json")
    
    # Load existing patterns
    if target_file.exists():
        existing = json.loads(target_file.read_text())
    else:
        existing = {"patterns": []}
    
    # Add new pattern
    existing["patterns"].append(pattern_data)
    
    # Write back
    target_file.write_text(json.dumps(existing, indent=2))
    
    print(f"✓ Promoted golden artifact to pattern '{pattern_id}'")
    print(f"  Target file: {target_file}")
    print(f"  Category: {category}")
    print("\n⚠️  Remember to review and validate the pattern before use.")
    
    return True


def promote_candidate(
    emitter: LearningLoopEmitter,
    kb: KnowledgeBase,
    candidate_path: Path,
    category: str | None = None,
    dry_run: bool = False,
) -> bool:
    """Promote a promotion candidate to the KB."""
    # Load the candidate
    candidate = emitter.load_promotion_candidate(candidate_path)
    if candidate is None:
        print(f"Error: Candidate not found: {candidate_path}")
        return False
    
    # Use suggested category if not provided
    target_category = category or candidate.suggested_category
    if not target_category:
        print("Error: No category specified and candidate has no suggested_category")
        print(f"Valid categories: {sorted(CANONICAL_CATEGORIES)}")
        return False
    
    # Validate category
    if target_category not in CANONICAL_CATEGORIES:
        print(f"Error: Invalid category '{target_category}'")
        print(f"Valid categories: {sorted(CANONICAL_CATEGORIES)}")
        return False
    
    # Generate pattern ID
    pattern_id = f"{target_category}-fix-{uuid.uuid4().hex[:8]}"
    
    # Build pattern from fix
    pattern_data = {
        "id": pattern_id,
        "version": "1.0.0",
        "name": f"Fix pattern: {candidate.error_category}",
        "category": target_category,
        "description": f"{candidate.fix_description}\n\nOriginal error: {candidate.error_message[:200]}",
        "pattern": {
            "error_category": candidate.error_category,
            "error_pattern": candidate.error_message[:200],
            "fix_approach": candidate.fix_description,
            "code_before": candidate.original_code[:500] if len(candidate.original_code) > 500 else candidate.original_code,
            "code_after": candidate.fixed_code[:500] if len(candidate.fixed_code) > 500 else candidate.fixed_code,
        },
        "applicability": {
            "error_categories": [candidate.error_category],
        },
        "examples": [
            {
                "before": candidate.original_code[:300],
                "after": candidate.fixed_code[:300],
            }
        ],
        "confidence": "medium",
        "sources": [f"promotion_candidate:{candidate.correlation_id}"],
        "promoted_from": candidate.correlation_id,
    }
    
    if dry_run:
        print("\n[DRY RUN] Would create pattern:")
        print(json.dumps(pattern_data, indent=2))
        return True
    
    # Determine target pattern file
    pattern_files = {
        "auth": "auth_patterns.json",
        "pagination": "pagination_patterns.json",
        "ts_to_python": "ts_python_idioms.json",
        "service_quirk": "service_quirk_patterns.json",
    }
    
    target_file = kb.kb_dir / "patterns" / pattern_files.get(target_category, f"{target_category}_patterns.json")
    
    # Load existing patterns
    if target_file.exists():
        existing = json.loads(target_file.read_text())
    else:
        existing = {"patterns": []}
    
    # Add new pattern
    existing["patterns"].append(pattern_data)
    
    # Write back
    target_file.write_text(json.dumps(existing, indent=2))
    
    print(f"✓ Promoted candidate to pattern '{pattern_id}'")
    print(f"  Target file: {target_file}")
    print(f"  Category: {target_category}")
    print(f"  Error category: {candidate.error_category}")
    print("\n⚠️  Remember to review and validate the pattern before use.")
    
    return True


def list_mining_runs(artifacts_dir: Path) -> None:
    """List all mining run outputs."""
    # Find directories with manifest.json that look like mining runs
    mining_runs: list[tuple[Path, dict]] = []
    
    for manifest_path in artifacts_dir.glob("*/manifest.json"):
        try:
            manifest = json.loads(manifest_path.read_text())
            script_name = manifest.get("script_name", "")
            # Check if this is a mining run (from our scripts)
            if script_name.startswith("mine_") or script_name == "report_gaps.py":
                mining_runs.append((manifest_path.parent, manifest))
        except (json.JSONDecodeError, IOError):
            continue
    
    if not mining_runs:
        print("No mining runs found.")
        print("\nTo create mining runs, use:")
        print("  python scripts/kb/mine_back_nodes.py --nodes-dir <path>")
        print("  python scripts/kb/mine_back_credentials.py --credentials-dir <path>")
        print("  python scripts/kb/mine_trace_maps.py --artifacts-dir <path>")
        print("  python scripts/kb/mine_fix_candidates.py --artifacts-dir <path>")
        print("  python scripts/kb/report_gaps.py --skills-dir skills/")
        return
    
    print(f"Found {len(mining_runs)} mining run(s):\n")
    for run_dir, manifest in sorted(mining_runs, key=lambda x: x[1].get("timestamp", ""), reverse=True):
        print(f"  [{run_dir.name}]")
        print(f"    Script: {manifest.get('script_name', 'unknown')}")
        print(f"    Timestamp: {manifest.get('timestamp', 'unknown')}")
        print(f"    Candidates: {manifest.get('candidates_generated', 0)}")
        print(f"    Files Processed: {len(manifest.get('files_processed', []))}")
        errors = manifest.get("errors", [])
        if errors:
            print(f"    Errors: {len(errors)}")
        print()


def promote_mining_run(
    artifacts_dir: Path,
    kb: KnowledgeBase,
    run_id: str,
    category: str | None = None,
    promote_all: bool = False,
    dry_run: bool = False,
) -> bool:
    """Promote candidates from a mining run to the KB."""
    run_dir = artifacts_dir / run_id
    
    if not run_dir.exists():
        print(f"Error: Mining run not found: {run_dir}")
        return False
    
    # Load manifest
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"Error: No manifest found in {run_dir}")
        return False
    
    try:
        manifest_data = json.loads(manifest_path.read_text())
        manifest = MiningRunManifest(**{
            k: v for k, v in manifest_data.items()
            if k in MiningRunManifest.__dataclass_fields__
        })
    except (json.JSONDecodeError, TypeError) as e:
        print(f"Error loading manifest: {e}")
        return False
    
    print(f"Mining Run: {manifest.run_id}")
    print(f"Script: {manifest.script_name}")
    print(f"Candidates: {manifest.candidates_generated}")
    print()
    
    # Load candidates
    candidates_dir = run_dir / "promotion_candidates"
    candidates = load_candidates_from_dir(candidates_dir)
    
    if not candidates:
        print("No candidates found in mining run.")
        return False
    
    # Filter by category if specified
    if category:
        if category not in CANONICAL_CATEGORIES:
            print(f"Error: Invalid category '{category}'")
            print(f"Valid categories: {sorted(CANONICAL_CATEGORIES)}")
            return False
        candidates = [c for c in candidates if c.category == category]
        if not candidates:
            print(f"No candidates found for category '{category}'")
            return False
    
    print(f"Found {len(candidates)} candidate(s) to promote:\n")
    for c in candidates:
        print(f"  - {c.candidate_id}: {c.name} ({c.category}) [{c.confidence}]")
    print()
    
    if not promote_all:
        print("Use --all to promote all candidates, or promote individually:")
        for c in candidates:
            print(f"  python scripts/promote_artifact.py candidate {candidates_dir / f'{c.candidate_id}.json'}")
        return True
    
    # Promote all candidates
    promoted = 0
    failed = 0
    
    for candidate in candidates:
        target_category = category or candidate.category
        
        # Generate pattern ID
        pattern_id = f"{target_category}-{candidate.candidate_id[:8]}"
        
        # Build pattern from mining candidate
        pattern_data = {
            "id": pattern_id,
            "version": "1.0.0",
            "name": candidate.name,
            "category": target_category,
            "description": candidate.description,
            "pattern": candidate.pattern_data,
            "applicability": {},
            "examples": [],
            "confidence": candidate.confidence,
            "sources": [f"mining_run:{run_id}:{candidate.candidate_id}"],
            "promoted_from": candidate.candidate_id,
            "mining_run_id": candidate.mining_run_id,
        }
        
        if candidate.source_refs:
            pattern_data["source_refs"] = [
                {"kind": sr.kind.value, "file_path": sr.file_path}
                for sr in candidate.source_refs[:3]
            ]
        
        if dry_run:
            print(f"\n[DRY RUN] Would create pattern: {pattern_id}")
            print(f"  Category: {target_category}")
            print(f"  Name: {candidate.name}")
            promoted += 1
            continue
        
        # Write to KB
        pattern_files = {
            "auth": "auth_patterns.json",
            "pagination": "pagination_patterns.json",
            "ts_to_python": "ts_python_idioms.json",
            "service_quirk": "service_quirk_patterns.json",
        }
        
        target_file = kb.kb_dir / "patterns" / pattern_files.get(target_category, f"{target_category}_patterns.json")
        
        # Load existing patterns
        if target_file.exists():
            try:
                existing = json.loads(target_file.read_text())
            except json.JSONDecodeError:
                existing = {"patterns": []}
        else:
            target_file.parent.mkdir(parents=True, exist_ok=True)
            existing = {"patterns": []}
        
        # Check for duplicates
        existing_ids = {p.get("id") for p in existing.get("patterns", [])}
        if pattern_id in existing_ids:
            print(f"  Skipped (duplicate): {pattern_id}")
            continue
        
        # Add new pattern
        existing["patterns"].append(pattern_data)
        
        # Write back
        target_file.write_text(json.dumps(existing, indent=2))
        print(f"  ✓ Promoted: {pattern_id} -> {target_file.name}")
        promoted += 1
    
    print(f"\n✓ Promoted {promoted} patterns")
    if failed > 0:
        print(f"⚠️  Failed: {failed}")
    
    if not dry_run and promoted > 0:
        print("\n⚠️  Remember to review and validate the patterns before use.")
    
    return failed == 0


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Promote golden artifacts or candidates to Knowledge Base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Golden artifact command
    golden_parser = subparsers.add_parser("golden", help="Promote a golden artifact")
    golden_parser.add_argument("correlation_id", help="Correlation ID of the golden artifact")
    golden_parser.add_argument("--category", required=True, help="Target KB category")
    golden_parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    # Candidate command
    candidate_parser = subparsers.add_parser("candidate", help="Promote a promotion candidate")
    candidate_parser.add_argument("candidate_file", help="Path to candidate JSON file")
    candidate_parser.add_argument("--category", help="Override suggested category")
    candidate_parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    # Mining run command
    mining_parser = subparsers.add_parser("mining-run", help="Promote candidates from a mining run")
    mining_parser.add_argument("run_id", help="Mining run ID (directory name in artifacts/)")
    mining_parser.add_argument("--category", help="Only promote candidates of this category")
    mining_parser.add_argument("--all", action="store_true", dest="promote_all", help="Promote all candidates")
    mining_parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List artifacts or candidates")
    list_parser.add_argument("type", choices=["golden", "candidates", "mining-runs"], help="What to list")
    
    args = parser.parse_args()
    
    # Initialize emitter and KB
    artifacts_dir = PROJECT_ROOT / "artifacts"
    kb_dir = PROJECT_ROOT / "runtime" / "kb"
    
    emitter = LearningLoopEmitter(artifacts_dir)
    kb = KnowledgeBase(kb_dir)
    
    if args.command == "list":
        if args.type == "golden":
            list_golden_artifacts(emitter)
        elif args.type == "candidates":
            list_promotion_candidates(emitter)
        elif args.type == "mining-runs":
            list_mining_runs(artifacts_dir)
        return 0
    
    elif args.command == "golden":
        success = promote_golden_artifact(
            emitter, kb, args.correlation_id, args.category, args.dry_run
        )
        return 0 if success else 1
    
    elif args.command == "candidate":
        success = promote_candidate(
            emitter, kb, Path(args.candidate_file), args.category, args.dry_run
        )
        return 0 if success else 1
    
    elif args.command == "mining-run":
        success = promote_mining_run(
            artifacts_dir, kb, args.run_id, args.category, args.promote_all, args.dry_run
        )
        return 0 if success else 1
    
    return 1


if __name__ == "__main__":
    sys.exit(main())
