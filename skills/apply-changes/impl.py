"""
Apply Changes Skill Implementation

Apply packaged node to target repository.
THE ONLY skill that writes to target_repo. All other skills must write to artifacts/.

This skill is the chokepoint for repository mutations.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext


def _create_backup(file_path: Path, backup_dir: Path) -> str | None:
    """Create backup of existing file."""
    if not file_path.exists():
        return None
    
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{file_path.name}.{timestamp}.bak"
    backup_path = backup_dir / backup_name
    
    shutil.copy2(file_path, backup_path)
    return str(backup_path)


def _update_registry_dict_import(
    registry_path: Path,
    import_statement: str,
    dict_entry: str,
    dict_name: str = "node_definitions",
) -> tuple[bool, str]:
    """
    Update registry file using dict_import strategy.
    
    1. Add import statement after existing imports
    2. Add dict entry to the node_definitions dict
    """
    if not registry_path.exists():
        return False, f"Registry file not found: {registry_path}"
    
    content = registry_path.read_text()
    original_content = content
    
    # Check if import already exists
    if import_statement.strip() in content:
        import_added = False
    else:
        # Find last import statement and add after it
        # Pattern matches: from .xxx import Yyy or from .xxx.yyy import Zzz
        import_pattern = r"^from \.\w+(?:\.\w+)* import \w+.*$"
        matches = list(re.finditer(import_pattern, content, re.MULTILINE))
        
        if matches:
            last_import = matches[-1]
            insert_pos = last_import.end()
            content = content[:insert_pos] + "\n" + import_statement + content[insert_pos:]
            import_added = True
        else:
            # No imports found, add at top after any comments/docstrings
            content = import_statement + "\n" + content
            import_added = True
    
    # Check if dict entry already exists (by node_type key)
    # Extract the key from dict_entry like "'bitly': {...}"
    key_match = re.search(r"'(\w+)':", dict_entry)
    if key_match:
        node_key = key_match.group(1)
        if f"'{node_key}':" in content:
            entry_added = False
        else:
            # Find the dict and add entry
            # Look for pattern like: node_definitions = {
            dict_pattern = rf"({dict_name}\s*=\s*\{{)"
            match = re.search(dict_pattern, content)
            
            if match:
                # Find a good place to insert (before closing brace or after last entry)
                # Simple approach: find the dict and add after opening brace
                dict_start = match.end()
                
                # Add entry with proper indentation (4 spaces)
                entry_line = f"\n    {dict_entry},"
                content = content[:dict_start] + entry_line + content[dict_start:]
                entry_added = True
            else:
                return False, f"Could not find {dict_name} dict in registry"
    else:
        return False, f"Invalid dict_entry format: {dict_entry}"
    
    if content == original_content:
        return True, "No changes needed (already up to date)"
    
    # Write updated content
    registry_path.write_text(content)
    
    changes = []
    if import_added:
        changes.append("import added")
    if entry_added:
        changes.append("dict entry added")
    
    return True, f"Registry updated: {', '.join(changes)}"


def run(ctx: "ExecutionContext") -> dict[str, Any]:
    """
    Apply packaged node to target repository.
    
    This is the ONLY chokepoint that writes to target_repo.
    
    Reads from:
    - artifacts/{correlation_id}/package/
    - artifacts/{correlation_id}/validation/results.json
    
    Writes to:
    - target_repo as specified by target_repo_layout
    - artifacts/{correlation_id}/apply_log.json
    """
    inputs = ctx.inputs
    correlation_id = inputs["correlation_id"]
    target_repo_layout = inputs["target_repo_layout"]
    dry_run = inputs.get("dry_run", False)
    require_validation = inputs.get("require_validation", True)
    
    ctx.log("apply_changes_start", {
        "correlation_id": correlation_id,
        "dry_run": dry_run,
        "require_validation": require_validation,
    })
    
    # Extract layout info
    target_repo_root = Path(target_repo_layout["target_repo_root"])
    node_output_base_dir = target_repo_layout.get("node_output_base_dir", "nodes")
    registry_file = target_repo_layout.get("registry_file", "nodes/__init__.py")
    registry_strategy = target_repo_layout.get("registry_strategy", "dict_import")
    registry_dict_name = target_repo_layout.get("registry_dict_name", "node_definitions")
    tests_dir = target_repo_layout.get("tests_dir", "tests")
    
    # Get paths
    artifacts_dir = ctx.artifacts_dir
    package_dir = artifacts_dir / "package"
    validation_dir = artifacts_dir / "validation"
    backup_dir = artifacts_dir / "backups"
    
    errors = []
    files_written = []
    backups_created = []
    
    # Validate package exists
    if not package_dir.exists():
        return {
            "applied": False,
            "dry_run": dry_run,
            "files_written": [],
            "registry_updated": False,
            "backup_created": False,
            "errors": [f"Package directory not found: {package_dir}"],
        }
    
    # Check validation results if required
    if require_validation:
        validation_results_path = validation_dir / "results.json"
        if not validation_results_path.exists():
            return {
                "applied": False,
                "dry_run": dry_run,
                "files_written": [],
                "registry_updated": False,
                "backup_created": False,
                "errors": ["Validation results not found. Run node-validate first."],
            }
        
        validation_results = json.loads(validation_results_path.read_text())
        if not validation_results.get("valid", False):
            return {
                "applied": False,
                "dry_run": dry_run,
                "files_written": [],
                "registry_updated": False,
                "backup_created": False,
                "errors": ["Validation failed. Fix errors before applying."],
            }
    
    # Read manifest
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        return {
            "applied": False,
            "dry_run": dry_run,
            "files_written": [],
            "registry_updated": False,
            "backup_created": False,
            "errors": [f"Manifest not found: {manifest_path}"],
        }
    
    manifest = json.loads(manifest_path.read_text())
    registry_entry = manifest.get("registry_entry", {})
    
    # Copy files to target repo
    for file_info in manifest.get("files", []):
        source_filename = file_info["filename"]
        target_path = file_info["target_path"]
        
        source_path = package_dir / source_filename
        dest_path = target_repo_root / target_path
        
        if not source_path.exists():
            errors.append(f"Source file not found: {source_path}")
            continue
        
        # Determine action
        action = "update" if dest_path.exists() else "create"
        
        if dry_run:
            files_written.append({
                "source": str(source_path),
                "destination": str(dest_path),
                "action": action,
                "dry_run": True,
            })
        else:
            # Create backup if updating
            if action == "update":
                backup_path = _create_backup(dest_path, backup_dir)
                if backup_path:
                    backups_created.append(backup_path)
            
            # Ensure parent directory exists
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            
            files_written.append({
                "source": str(source_path),
                "destination": str(dest_path),
                "action": action,
            })
    
    # Update registry
    registry_updated = False
    if registry_strategy == "dict_import" and registry_entry.get("import_statement"):
        registry_path = target_repo_root / registry_file
        
        if dry_run:
            registry_updated = True  # Would be updated
        else:
            # Create backup
            backup_path = _create_backup(registry_path, backup_dir)
            if backup_path:
                backups_created.append(backup_path)
            
            success, message = _update_registry_dict_import(
                registry_path=registry_path,
                import_statement=registry_entry["import_statement"],
                dict_entry=registry_entry["dict_entry"],
                dict_name=registry_dict_name,
            )
            
            if success:
                registry_updated = True
                ctx.log("registry_updated", {"message": message})
            else:
                errors.append(f"Registry update failed: {message}")
    
    # Write apply log
    apply_log = {
        "correlation_id": correlation_id,
        "timestamp": datetime.now().isoformat(),
        "dry_run": dry_run,
        "target_repo_root": str(target_repo_root),
        "files_written": files_written,
        "registry_updated": registry_updated,
        "backups_created": backups_created,
        "errors": errors,
    }
    
    apply_log_path = artifacts_dir / "apply_log.json"
    apply_log_path.write_text(json.dumps(apply_log, indent=2))
    
    applied = len(errors) == 0 and len(files_written) > 0 and not dry_run
    
    ctx.log("apply_changes_complete", {
        "applied": applied,
        "dry_run": dry_run,
        "files_written_count": len(files_written),
        "registry_updated": registry_updated,
        "errors_count": len(errors),
    })
    
    return {
        "applied": applied,
        "dry_run": dry_run,
        "files_written": files_written,
        "registry_updated": registry_updated,
        "backup_created": len(backups_created) > 0,
        "errors": errors,
    }
