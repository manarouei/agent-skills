"""Source Ingest skill implementation.

Fetch and parse source materials for node implementation. Retrieves TypeScript
source or API documentation based on classified source type.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

from contracts.skill_contract import ExecutionStatus

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext

# Paths
ARTIFACTS_ROOT = Path(os.environ.get("ARTIFACTS_ROOT", "artifacts"))
INPUT_SOURCES_ROOT = Path(os.environ.get("INPUT_SOURCES_ROOT", "input_sources"))


def _copy_source_bundle(
    source_dir: Path,
    target_dir: Path,
) -> tuple[list[str], str]:
    """Copy source files to artifact bundle directory.
    
    Returns:
        Tuple of (list of copied files, combined content)
    """
    copied_files = []
    combined_content = []
    
    if not source_dir.exists():
        return copied_files, ""
    
    # Copy all TypeScript files
    for ts_file in sorted(source_dir.rglob("*.ts")):
        # Compute relative path within source dir
        rel_path = ts_file.relative_to(source_dir)
        target_path = target_dir / rel_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        shutil.copy2(ts_file, target_path)
        copied_files.append(str(rel_path))
        
        # Add to combined content
        content = ts_file.read_text()
        combined_content.append(f"// === File: {rel_path} ===\n{content}")
    
    return copied_files, "\n\n".join(combined_content)


def _parse_typescript_node(content: str) -> dict[str, Any]:
    """Parse TypeScript node source and extract key sections.
    
    Returns:
        Dict with parsed sections (class_name, type, properties, methods, etc.)
    """
    parsed = {
        "class_name": None,
        "node_type": None,
        "version": None,
        "description": None,
        "properties": [],
        "methods": [],
        "credentials": [],
        "resources": [],
    }
    
    # Extract class name
    class_match = re.search(
        r'export\s+class\s+(\w+)\s+implements\s+INode(?:Type)?',
        content,
    )
    if class_match:
        parsed["class_name"] = class_match.group(1)
    
    # Alternative class pattern
    if not parsed["class_name"]:
        class_match = re.search(r'class\s+(\w+Node)\s*{', content)
        if class_match:
            parsed["class_name"] = class_match.group(1)
    
    # Extract description block
    desc_match = re.search(
        r'description:\s*INodeTypeDescription\s*=\s*({[\s\S]*?});',
        content,
    )
    if desc_match:
        parsed["description"] = desc_match.group(1)[:500] + "..."  # Truncate
    
    # Extract node type from description
    type_match = re.search(r"name:\s*['\"]([^'\"]+)['\"]", content)
    if type_match:
        parsed["node_type"] = type_match.group(1)
    
    # Extract version
    version_match = re.search(r"version:\s*(\d+(?:\.\d+)?)", content)
    if version_match:
        parsed["version"] = float(version_match.group(1))
    
    # Extract methods
    method_pattern = r'async\s+(\w+)\s*\([^)]*\)\s*(?::\s*Promise)?'
    for match in re.finditer(method_pattern, content):
        method = match.group(1)
        if method not in parsed["methods"]:
            parsed["methods"].append(method)
    
    # Extract credentials
    cred_pattern = r"testedBy:\s*['\"]([^'\"]+)['\"]|name:\s*['\"](\w+(?:Api|OAuth\d*|Credentials?))['\"]"
    for match in re.finditer(cred_pattern, content):
        cred = match.group(1) or match.group(2)
        if cred and cred not in parsed["credentials"]:
            parsed["credentials"].append(cred)
    
    # Check for router pattern (v2 nodes)
    if "router.ts" in content or "router(" in content:
        parsed["has_router"] = True
    
    # Extract resources for v2 nodes
    resource_pattern = r"resource:\s*\[\s*['\"](\w+)['\"]"
    for match in re.finditer(resource_pattern, content):
        resource = match.group(1)
        if resource not in parsed["resources"]:
            parsed["resources"].append(resource)
    
    return parsed


def run(ctx: "ExecutionContext") -> dict[str, Any]:
    """Execute the source-ingest skill.
    
    Args:
        ctx: ExecutionContext with inputs containing correlation_id, source_type, evidence
        
    Returns:
        Dict with raw_content, parsed_sections, metadata, and status
    """
    # Extract inputs from context
    correlation_id = ctx.inputs.get("correlation_id", ctx.correlation_id)
    source_type = ctx.inputs.get("source_type", "")
    evidence = ctx.inputs.get("evidence", [])
    normalized_name = ctx.inputs.get("normalized_name", "")
    
    # Validate input
    if not correlation_id:
        return {
            "status": ExecutionStatus.FAILED,
            "error": "validation_error",
            "error_message": "correlation_id is required",
        }
    
    if source_type not in ("TYPE1", "TYPE2"):
        return {
            "status": ExecutionStatus.FAILED,
            "error": "validation_error",
            "error_message": f"Invalid source_type: {source_type}. Must be TYPE1 or TYPE2.",
        }
    
    # Try to extract normalized_name from evidence if not provided
    if not normalized_name:
        for item in evidence:
            path = item.get("path_or_url", "")
            if "input_sources/" in path:
                parts = path.split("input_sources/")
                if len(parts) > 1:
                    normalized_name = parts[1].split("/")[0]
                    break
    
    if not normalized_name:
        return {
            "status": ExecutionStatus.FAILED,
            "error": "validation_error",
            "error_message": "Could not determine normalized_name from evidence",
        }
    
    # Create artifact directories
    artifact_dir = ctx.artifacts_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    
    source_bundle_dir = artifact_dir / "source_bundle"
    source_bundle_dir.mkdir(parents=True, exist_ok=True)
    
    raw_content = ""
    parsed_sections: dict[str, Any] = {}
    metadata: dict[str, Any] = {
        "fetch_time": datetime.now(timezone.utc).isoformat(),
        "source_type": source_type,
    }
    
    if source_type == "TYPE1":
        # TYPE1: Copy and parse TypeScript source
        source_dir = INPUT_SOURCES_ROOT / normalized_name
        
        if not source_dir.exists():
            return {
                "status": ExecutionStatus.FAILED,
                "error": "validation_error",
                "error_message": f"Source directory not found: {source_dir}",
            }
        
        # Copy source bundle
        copied_files, combined_content = _copy_source_bundle(source_dir, source_bundle_dir)
        raw_content = combined_content
        
        # Parse the content
        parsed_sections = _parse_typescript_node(raw_content)
        parsed_sections["files"] = copied_files
        
        # Add code sections for schema-infer compatibility
        # schema-infer expects parsed_sections["code"] to be a list of {content, file} dicts
        code_sections = []
        for ts_file in sorted(source_dir.rglob("*.ts")):
            rel_path = ts_file.relative_to(source_dir)
            try:
                content = ts_file.read_text()
                code_sections.append({
                    "file": str(rel_path),
                    "content": content,
                })
            except Exception:
                pass
        parsed_sections["code"] = code_sections
        
        metadata["source_path"] = str(source_dir)
        metadata["file_count"] = len(copied_files)
        metadata["content_hash"] = hashlib.sha256(raw_content.encode()).hexdigest()[:16]
        
    elif source_type == "TYPE2":
        # TYPE2: Documentation-only (not fully implemented yet)
        parsed_sections = {
            "source_type": "documentation",
            "note": "TYPE2 ingestion requires documentation URL parsing (not implemented)",
        }
        metadata["note"] = "TYPE2 source not fully implemented"
    
    # Write artifacts
    raw_source_path = artifact_dir / "raw_source.txt"
    raw_source_path.write_text(raw_content)
    
    parsed_source_path = artifact_dir / "parsed_source.json"
    parsed_source_path.write_text(json.dumps({
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "sections": parsed_sections,
        "metadata": metadata,
    }, indent=2))
    
    return {
        "raw_content": raw_content[:10000] if len(raw_content) > 10000 else raw_content,  # Truncate for output
        "parsed_sections": parsed_sections,
        "metadata": metadata,
        "artifacts": {
            "raw_source": str(raw_source_path),
            "parsed_source": str(parsed_source_path),
            "source_bundle": str(source_bundle_dir),
        },
    }
