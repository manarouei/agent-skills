---
name: apply-changes
version: "1.0.0"
description: Apply packaged node to target repository. THE ONLY skill that writes to target_repo. Requires validation pass and explicit allowlist.

# Contract
autonomy_level: IMPLEMENT
side_effects: [fs, git]
timeout_seconds: 120
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id + node_type"
max_fix_iterations: 1

# Filesystem scope: TARGET_REPO - this is the CHOKEPOINT
# This skill writes to the target repository
# Requires allowlist.json and repo_facts.json
fs_scope: target_repo

# Sync Celery Constraints
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: false
  forbids_background_tasks: true

input_schema:
  type: object
  required: [correlation_id, target_repo_layout]
  properties:
    correlation_id:
      type: string
      description: Session correlation ID for artifact paths
    target_repo_layout:
      type: object
      required: [target_repo_root, node_output_base_dir, registry_file]
      description: Target repository layout from repo-ground
    dry_run:
      type: boolean
      default: false
      description: If true, preview changes without writing
    require_validation:
      type: boolean
      default: true
      description: Require validation/results.json to show valid=true

output_schema:
  type: object
  required: [applied, files_written]
  properties:
    applied:
      type: boolean
      description: True if changes were applied
    dry_run:
      type: boolean
      description: True if this was a dry run
    files_written:
      type: array
      items:
        type: object
        properties:
          source:
            type: string
          destination:
            type: string
          action:
            type: string
            enum: [create, update]
    registry_updated:
      type: boolean
    backup_created:
      type: boolean
    errors:
      type: array
      items:
        type: string

required_artifacts:
  - name: apply_log.json
    type: json
    description: Log of all changes made

failure_modes: [validation_error, permission_denied]
depends_on: [node-package, node-validate]
---

# Apply Changes

This skill is the **ONLY** chokepoint that writes to the target repository.

## Purpose

After node-package and node-validate succeed, this skill:
1. Verifies validation passed (unless require_validation=false)
2. Copies packaged files to target repo locations
3. Updates the registry file with import and dict entry
4. Creates backup of modified files
5. Logs all changes for audit

## Security Model

- **fs_scope: target_repo** - Triggers NoTargetRepoMutationGuard
- Requires allowlist.json to be present
- All file writes are logged and auditable
- Dry run mode for preview
- Backup created before any modifications

## Target Repo Layout

Uses TargetRepoLayout from repo-ground:
```json
{
  "target_repo_root": "/home/toni/n8n/back",
  "node_output_base_dir": "nodes",
  "registry_file": "nodes/__init__.py",
  "registry_strategy": "dict_import",
  "registry_dict_name": "node_definitions",
  "tests_dir": "tests"
}
```

## Registry Update

For dict_import strategy:
1. Adds import statement at top of file
2. Adds dict entry to node_definitions dict
3. Preserves existing imports and entries

## Usage in Pipeline

```
node-validate → apply-changes → node-smoke-test
                     ↑
             ONLY repo-writing
             chokepoint
```
