"""Source Classify skill implementation.

Classify source type for node implementation. Determines if source is
Type1 (existing TypeScript node in n8n repo) or Type2 (documentation-only).
Returns confidence score and evidence.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

from contracts.skill_contract import ExecutionStatus

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext

# Paths
ARTIFACTS_ROOT = Path(os.environ.get("ARTIFACTS_ROOT", "artifacts"))
INPUT_SOURCES_ROOT = Path(os.environ.get("INPUT_SOURCES_ROOT", "input_sources"))


def _check_local_source(normalized_name: str) -> tuple[bool, list[dict[str, Any]]]:
    """Check if TypeScript source exists in input_sources directory.
    
    Returns:
        Tuple of (exists, evidence_list)
    """
    evidence = []
    source_dir = INPUT_SOURCES_ROOT / normalized_name
    
    if not source_dir.exists():
        return False, evidence
    
    # Look for TypeScript files
    ts_files = list(source_dir.rglob("*.ts"))
    
    if not ts_files:
        return False, evidence
    
    # Look for main node file patterns
    for ts_file in ts_files:
        if ts_file.name.endswith(".node.ts"):
            evidence.append({
                "type": "ts_file",
                "path_or_url": str(ts_file),
                "verified": True,
                "description": f"Found node file: {ts_file.name}",
            })
    
    # Check for v2 structure (router + actions)
    has_router = any(f.name == "router.ts" for f in ts_files)
    has_actions = (source_dir / "actions").exists() if source_dir.exists() else False
    has_v2_dir = any(p.name == "v2" for p in source_dir.iterdir() if p.is_dir())
    
    if has_router:
        evidence.append({
            "type": "v2_router",
            "path_or_url": str(source_dir),
            "verified": True,
            "description": "Found router.ts - indicates v2 node structure",
        })
    
    if has_actions or has_v2_dir:
        evidence.append({
            "type": "v2_structure",
            "path_or_url": str(source_dir),
            "verified": True,
            "description": "Found v2 directory structure with actions",
        })
    
    # Count total files
    evidence.append({
        "type": "file_count",
        "path_or_url": str(source_dir),
        "verified": True,
        "description": f"Found {len(ts_files)} TypeScript files in source directory",
    })
    
    return len(ts_files) > 0, evidence


def _calculate_confidence(evidence: list[dict[str, Any]]) -> float:
    """Calculate confidence score based on evidence.
    
    Returns:
        Confidence score between 0 and 1
    """
    if not evidence:
        return 0.0
    
    score = 0.0
    
    for item in evidence:
        evidence_type = item.get("type", "")
        verified = item.get("verified", False)
        
        if not verified:
            continue
            
        if evidence_type == "ts_file":
            score += 0.4  # Strong evidence
        elif evidence_type == "v2_router":
            score += 0.3  # Good evidence
        elif evidence_type == "v2_structure":
            score += 0.2  # Supporting evidence
        elif evidence_type == "file_count":
            score += 0.1  # Weak evidence
        elif evidence_type == "docs_url":
            score += 0.2  # Documentation
    
    return min(score, 1.0)


def _determine_source_type(
    has_local_source: bool,
    source_refs: dict[str, Any] | None,
    confidence: float,
) -> str:
    """Determine source type based on evidence.
    
    Returns:
        TYPE1 (existing TS), TYPE2 (docs only), or UNKNOWN
    """
    if has_local_source and confidence >= 0.5:
        return "TYPE1"
    
    if source_refs and source_refs.get("docs_url"):
        return "TYPE2"
    
    if confidence >= 0.7:
        return "TYPE1"
    elif confidence >= 0.3:
        return "TYPE2"
    
    return "UNKNOWN"


def run(ctx: "ExecutionContext") -> dict[str, Any]:
    """Execute the source-classify skill.
    
    Args:
        ctx: ExecutionContext with inputs containing correlation_id and normalized_name
        
    Returns:
        Dict with source_type, confidence, evidence, and status
    """
    # Extract inputs from context
    correlation_id = ctx.inputs.get("correlation_id", ctx.correlation_id)
    normalized_name = ctx.inputs.get("normalized_name", "")
    source_refs = ctx.inputs.get("source_refs")
    
    # Validate input
    if not correlation_id:
        return {
            "status": ExecutionStatus.FAILED,
            "error": "validation_error",
            "error_message": "correlation_id is required",
        }
    
    if not normalized_name:
        return {
            "status": ExecutionStatus.FAILED,
            "error": "validation_error", 
            "error_message": "normalized_name is required",
        }
    
    evidence: list[dict[str, Any]] = []
    
    # Check for local TypeScript source
    has_local_source, ts_evidence = _check_local_source(normalized_name)
    evidence.extend(ts_evidence)
    
    # Check source_refs
    if source_refs:
        if source_refs.get("ts_path"):
            ts_path = Path(source_refs["ts_path"])
            if ts_path.exists():
                evidence.append({
                    "type": "ts_file",
                    "path_or_url": str(ts_path),
                    "verified": True,
                    "description": f"Provided TypeScript path exists: {ts_path}",
                })
                has_local_source = True
        
        if source_refs.get("docs_url"):
            evidence.append({
                "type": "docs_url",
                "path_or_url": source_refs["docs_url"],
                "verified": False,  # Not verified yet
                "description": f"Documentation URL provided: {source_refs['docs_url']}",
            })
    
    # Calculate confidence
    confidence = _calculate_confidence(evidence)
    
    # Determine source type
    source_type = _determine_source_type(has_local_source, source_refs, confidence)
    
    # Create artifact directory
    artifact_dir = ctx.artifacts_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    # Write classification.json artifact
    classification = {
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "normalized_name": normalized_name,
        "source_type": source_type,
        "confidence": confidence,
        "evidence": evidence,
    }
    
    classification_path = artifact_dir / "classification.json"
    classification_path.write_text(json.dumps(classification, indent=2))
    
    return {
        "source_type": source_type,
        "confidence": confidence,
        "evidence": evidence,
        "artifacts": {
            "classification": str(classification_path),
        },
    }
