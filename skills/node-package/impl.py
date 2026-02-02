"""
Node Package Skill Implementation

Packages converted node artifacts into a deterministic structure ready for apply-changes.
Reads from converted/ and writes to package/.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext


def _compute_sha256(content: str | bytes) -> str:
    """Compute SHA256 hash of content."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:16]


def _extract_class_name(content: str) -> str | None:
    """Extract node class name from Python file content."""
    # Look for class definition inheriting from BaseNode
    match = re.search(r"class\s+(\w+Node)\s*\(\s*BaseNode\s*\)", content)
    if match:
        return match.group(1)
    
    # Fallback: any class ending in Node
    match = re.search(r"class\s+(\w+Node)\s*\(", content)
    if match:
        return match.group(1)
    
    return None


def _extract_node_type(content: str) -> str | None:
    """Extract node type from Python file content."""
    # Look for type = "..." assignment
    match = re.search(r'^\s*type\s*=\s*["\'](\w+)["\']', content, re.MULTILINE)
    if match:
        return match.group(1)
    return None


def _normalize_filename(original: str, node_type: str | None) -> str:
    """Normalize filename to snake_case convention."""
    if node_type:
        # Use node_type as base
        return f"{node_type.lower()}.py"
    
    # Extract from original filename
    base = Path(original).stem
    # Convert CamelCase to snake_case
    normalized = re.sub(r"(?<!^)(?=[A-Z])", "_", base).lower()
    # Remove common suffixes like _node
    normalized = re.sub(r"_node$", "", normalized)
    return f"{normalized}.py"


def _generate_registry_entry(
    node_class: str,
    node_type: str,
    registry_strategy: str = "dict_import",
    node_filename: str = "",
) -> dict[str, str]:
    """Generate registry entry metadata."""
    # Module name from filename (without .py)
    module_name = Path(node_filename).stem if node_filename else node_type.lower()
    
    if registry_strategy == "dict_import":
        return {
            "import_statement": f"from .{module_name} import {node_class}",
            "dict_entry": f"'{node_type}': {{'node_class': {node_class}, 'type': 'regular'}}",
            "node_type": node_type,
            "node_class": node_class,
            "module_name": module_name,
        }
    elif registry_strategy == "auto_discover":
        return {
            "import_statement": "",
            "dict_entry": "",
            "node_type": node_type,
            "node_class": node_class,
            "module_name": module_name,
        }
    else:
        return {
            "import_statement": f"from .{module_name} import {node_class}",
            "dict_entry": f"register('{node_type}', {node_class})",
            "node_type": node_type,
            "node_class": node_class,
            "module_name": module_name,
        }


def run(ctx: "ExecutionContext") -> dict[str, Any]:
    """
    Package converted node artifacts into a deterministic structure.
    
    Reads from artifacts/{correlation_id}/converted/
    Writes to artifacts/{correlation_id}/package/
    """
    inputs = ctx.inputs
    correlation_id = inputs["correlation_id"]
    target_repo_layout = inputs.get("target_repo_layout", {})
    
    ctx.log("node_package_start", {"correlation_id": correlation_id})
    
    # Get paths
    artifacts_dir = ctx.artifacts_dir
    converted_dir = artifacts_dir / "converted"
    package_dir = artifacts_dir / "package"
    
    # Validate converted directory exists
    if not converted_dir.exists():
        ctx.log("missing_converted_dir", {"path": str(converted_dir)})
        return {
            "error": f"Converted directory not found: {converted_dir}",
            "package_dir": None,
            "files": [],
        }
    
    # Find converted Python files
    converted_files = list(converted_dir.glob("*.py"))
    if not converted_files:
        ctx.log("no_converted_files", {"path": str(converted_dir)})
        return {
            "error": f"No Python files found in: {converted_dir}",
            "package_dir": None,
            "files": [],
        }
    
    # Create package directory
    package_dir.mkdir(parents=True, exist_ok=True)
    
    # Get registry strategy from target_repo_layout
    registry_strategy = target_repo_layout.get("registry_strategy", "dict_import")
    node_output_base_dir = target_repo_layout.get("node_output_base_dir", "nodes")
    tests_dir = target_repo_layout.get("tests_dir", "tests")
    
    # Process files
    packaged_files = []
    manifest_entries = []
    node_class = None
    node_type = None
    main_node_file = None
    
    for converted_file in converted_files:
        content = converted_file.read_text()
        filename = converted_file.name
        
        # Check if this is a test file
        is_test = filename.startswith("test_") or "_test" in filename
        
        if not is_test:
            # Try to extract class name and type
            extracted_class = _extract_class_name(content)
            extracted_type = _extract_node_type(content)
            
            if extracted_class and not node_class:
                node_class = extracted_class
            if extracted_type and not node_type:
                node_type = extracted_type
            
            main_node_file = converted_file
    
    # Determine normalized filename
    if node_type:
        normalized_node_name = f"{node_type.lower()}.py"
    elif node_class:
        # Convert BitlyNode -> bitly.py
        base_name = re.sub(r"Node$", "", node_class)
        normalized_node_name = f"{base_name.lower()}.py"
    else:
        # Fallback to first non-test file
        for f in converted_files:
            if not f.name.startswith("test_"):
                normalized_node_name = f.name.lower()
                break
        else:
            normalized_node_name = converted_files[0].name.lower()
    
    # Derive node_type from normalized name if not found
    if not node_type:
        node_type = Path(normalized_node_name).stem
    
    # Process and copy files to package
    for converted_file in converted_files:
        content = converted_file.read_text()
        filename = converted_file.name
        is_test = filename.startswith("test_") or "_test" in filename
        
        if is_test:
            # Normalize test filename
            target_filename = f"test_{Path(normalized_node_name).stem}.py"
            target_rel_path = f"{tests_dir}/{target_filename}"
        else:
            target_filename = normalized_node_name
            target_rel_path = f"{node_output_base_dir}/{target_filename}"
        
        # Write to package
        dest_path = package_dir / target_filename
        dest_path.write_text(content)
        
        # Calculate checksum
        checksum = _compute_sha256(content)
        
        packaged_files.append({
            "filename": target_filename,
            "source_path": str(converted_file),
            "target_path": target_rel_path,
            "is_test": is_test,
        })
        
        manifest_entries.append({
            "filename": target_filename,
            "target_path": target_rel_path,
            "checksum": checksum,
            "size_bytes": len(content.encode("utf-8")),
        })
    
    # Generate registry entry
    if node_class:
        registry_entry = _generate_registry_entry(
            node_class=node_class,
            node_type=node_type,
            registry_strategy=registry_strategy,
            node_filename=normalized_node_name,
        )
    else:
        registry_entry = {
            "import_statement": "",
            "dict_entry": "",
            "node_type": node_type,
            "node_class": "",
            "module_name": Path(normalized_node_name).stem,
        }
    
    # Write registry entry
    registry_entry_path = package_dir / "registry_entry.json"
    registry_entry_path.write_text(json.dumps(registry_entry, indent=2))
    
    # Create manifest
    manifest = {
        "correlation_id": correlation_id,
        "node_type": node_type,
        "node_class": node_class or "",
        "registry_strategy": registry_strategy,
        "files": manifest_entries,
        "registry_entry": registry_entry,
    }
    
    manifest_path = package_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    
    ctx.log("node_package_complete", {
        "package_dir": str(package_dir),
        "files_count": len(packaged_files),
        "node_type": node_type,
        "node_class": node_class,
    })
    
    return {
        "package_dir": str(package_dir),
        "files": packaged_files,
        "registry_entry": registry_entry,
        "manifest": manifest,
    }
