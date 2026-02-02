"""Node Normalize skill implementation.

Normalize incoming node implementation requests. Generates a correlation ID,
converts node names to kebab-case, and creates an immutable request snapshot.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

from contracts.skill_contract import ExecutionStatus

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext

# Artifact root (from ENGINE_ROOT env or default)
import os
ARTIFACTS_ROOT = Path(os.environ.get("ARTIFACTS_ROOT", "artifacts"))


def _normalize_name(raw_name: str) -> str:
    """Convert raw node name to kebab-case.
    
    Normalization rules:
    1. Convert to lowercase
    2. Replace spaces and underscores with hyphens
    3. Remove special characters (keep only alphanumeric and hyphens)
    4. Remove consecutive hyphens
    5. Trim leading/trailing hyphens
    """
    name = raw_name.lower()
    # Replace spaces and underscores with hyphens
    name = re.sub(r'[\s_]+', '-', name)
    # Remove special characters (keep only alphanumeric and hyphens)
    name = re.sub(r'[^a-z0-9-]', '', name)
    # Remove consecutive hyphens
    name = re.sub(r'-+', '-', name)
    # Trim leading/trailing hyphens
    name = name.strip('-')
    return name


def _generate_correlation_id(normalized_name: str) -> str:
    """Generate a deterministic but unique correlation ID.
    
    Format: node-{normalized_name}-{short_uuid}
    """
    short_uuid = uuid.uuid4().hex[:8]
    return f"node-{normalized_name}-{short_uuid}"


def _create_snapshot(
    raw_node_name: str,
    normalized_name: str,
    correlation_id: str,
    source_refs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create immutable request snapshot."""
    return {
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "request": {
            "raw_node_name": raw_node_name,
            "normalized_name": normalized_name,
            "source_refs": source_refs or {},
        },
        "checksum": hashlib.sha256(
            f"{raw_node_name}:{normalized_name}:{correlation_id}".encode()
        ).hexdigest()[:16],
    }


def run(ctx: "ExecutionContext") -> dict[str, Any]:
    """Execute the node-normalize skill.
    
    Args:
        ctx: ExecutionContext with inputs containing raw_node_name
        
    Returns:
        Dict with correlation_id, normalized_name, snapshot, and status
    """
    # Extract inputs from context
    raw_node_name = ctx.inputs.get("raw_node_name", "")
    source_refs = ctx.inputs.get("source_refs")
    
    # Use artifacts_dir from context
    artifacts_root = ctx.artifacts_dir.parent if hasattr(ctx, 'artifacts_dir') else ARTIFACTS_ROOT
    
    # Validate input
    if not raw_node_name or not raw_node_name.strip():
        return {
            "status": ExecutionStatus.FAILED,
            "error": "validation_error",
            "error_message": "raw_node_name cannot be empty or whitespace-only",
        }
    
    # Normalize the name
    normalized_name = _normalize_name(raw_node_name)
    
    if not normalized_name:
        return {
            "status": ExecutionStatus.FAILED,
            "error": "validation_error",
            "error_message": f"Could not normalize name from input: {raw_node_name!r}",
        }
    
    # Generate correlation ID
    correlation_id = _generate_correlation_id(normalized_name)
    
    # Create artifact directory
    artifact_dir = artifacts_root / correlation_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    # Create snapshot
    snapshot = _create_snapshot(
        raw_node_name=raw_node_name,
        normalized_name=normalized_name,
        correlation_id=correlation_id,
        source_refs=source_refs,
    )
    
    # Write request_snapshot.json artifact
    snapshot_path = artifact_dir / "request_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2))
    
    return {
        "correlation_id": correlation_id,
        "normalized_name": normalized_name,
        "snapshot": snapshot,
        "artifacts": {
            "request_snapshot": str(snapshot_path),
        },
    }
