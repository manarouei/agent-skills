---
name: node-package
version: "1.0.0"
description: Package converted node artifacts into a deterministic package structure ready for apply-changes. Reads from converted/ and writes to package/.

# Contract
autonomy_level: IMPLEMENT
side_effects: [fs]
timeout_seconds: 60
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id"
max_fix_iterations: 1

# Filesystem scope: ARTIFACTS means this skill only writes to artifacts/
# Reads from artifacts/{correlation_id}/converted/
# Writes to artifacts/{correlation_id}/package/
fs_scope: artifacts

# Sync Celery Constraints
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: false
  forbids_background_tasks: true

input_schema:
  type: object
  required: [correlation_id]
  properties:
    correlation_id:
      type: string
      description: Session correlation ID for artifact paths
    target_repo_layout:
      type: object
      description: Target repo layout from repo-ground (optional, used for registry entry)

output_schema:
  type: object
  required: [package_dir, files]
  properties:
    package_dir:
      type: string
      description: Path to the package directory
    files:
      type: array
      items:
        type: object
        properties:
          filename:
            type: string
          source_path:
            type: string
          target_path:
            type: string
            description: Relative path for apply-changes
    registry_entry:
      type: object
      description: Registry entry metadata for apply-changes
      properties:
        import_statement:
          type: string
        dict_entry:
          type: string
        node_type:
          type: string
        node_class:
          type: string
    manifest:
      type: object
      description: Package manifest with checksums and metadata

required_artifacts:
  - name: package/manifest.json
    type: json
    description: Package manifest with file checksums

failure_modes: [validation_error]
depends_on: [code-convert, code-implement]
---

# Node Package

This skill packages converted node artifacts into a deterministic structure ready for apply-changes.

## Purpose

After code-convert or code-implement produces files in `converted/`, this skill:
1. Validates the converted files exist
2. Normalizes filenames to target repo conventions
3. Creates registry entry metadata (import statement, dict entry)
4. Generates a manifest with checksums for validation
5. Writes everything to `package/`

## Input Structure

Expects:
- `artifacts/{correlation_id}/converted/` with node files (.py)
- Optional `target_repo_layout.json` for naming conventions

## Output Structure

Creates:
```
artifacts/{correlation_id}/package/
  ├── manifest.json       # Package manifest with checksums
  ├── bitly.py           # Node implementation (normalized name)
  ├── test_bitly.py      # Test file (if exists)
  └── registry_entry.json # Import/dict entry for registry update
```

## Registry Entry

For dict_import strategy (n8n/back):
```json
{
  "import_statement": "from .bitly import BitlyNode",
  "dict_entry": "'bitly': {'node_class': BitlyNode, 'type': 'regular'}",
  "node_type": "bitly",
  "node_class": "BitlyNode"
}
```

## Usage in Pipeline

```
code-convert → node-package → node-validate → apply-changes → node-smoke-test
                    ↑
            Normalizes and packages
            converted node artifacts
```
