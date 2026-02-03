---
name: golden-extract
version: "1.0.0"
description: |
  Extract working implementations from avidflow-back/nodes/ as behavioral ground truth.
  For TYPE1 conversions, golden implementations MUST be used when available.
  
  This skill establishes the source-of-truth hierarchy:
  1. Golden implementations (existing Python) - highest priority
  2. TypeScript source extraction - if no golden exists
  3. Schema/contract - validation only, NEVER code generation

autonomy_level: READ
side_effects: [fs]
timeout_seconds: 60
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id"

# Sync Celery Constraints (MANDATORY)
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: true
  forbids_background_tasks: true

input_schema:
  type: object
  required: [correlation_id, node_name]
  properties:
    correlation_id:
      type: string
    node_name:
      type: string
      description: Node name (e.g., "github", "gitlab", "hunter")
    golden_path:
      type: string
      description: Optional path to golden nodes directory (default avidflow-back/nodes)

output_schema:
  type: object
  required: [golden_found, golden_impl]
  properties:
    golden_found:
      type: boolean
      description: Whether a golden implementation was found
    golden_impl:
      type: object
      description: Dict of method_name -> code_body (if found)
    golden_operations:
      type: array
      description: List of detected operations (resource/operation pairs)
    golden_snapshot_path:
      type: string
      description: Path to verbatim copy of golden node

required_artifacts:
  - name: golden_impl.json
    type: json
    description: Extracted method bodies and operation list
  - name: golden_node_snapshot.py
    type: file
    description: Verbatim copy of golden node for diffing

failure_modes: [file_not_found, parse_error]
depends_on: []
---

# Golden Extract

Extracts working implementations from `avidflow-back/nodes/` as behavioral ground truth.

## Purpose

When we already have a working node (e.g., `avidflow-back/nodes/github.py`), we must:

1. Extract/serialize the operation method bodies + helper bodies ("golden_impl")
2. Pass them into code-convert as source-of-truth implementation
3. Validate schema/contracts against golden behavior (not vice versa)

## Source of Truth Hierarchy

```
1. BEHAVIORAL GROUND TRUTH: Existing Python implementations
   (avidflow-back/nodes/*.py)
   
2. SOURCE TRUTH: TypeScript source code
   (input_sources/*/node.ts)
   
3. SCHEMA (constraints only): Contract YAML
   - Declares expected operations (validation)
   - Does NOT generate implementations
```

## Usage

```python
from skills.golden_extract import execute_golden_extract

result = execute_golden_extract(ctx)

if result.outputs["golden_found"]:
    golden_impl = result.outputs["golden_impl"]
    # Use golden_impl method bodies in code-convert
else:
    # Proceed with TS extraction
```

## Extracted Data

For each golden node, we extract:

- All `_resource_operation` methods (e.g., `_issue_create`, `_file_delete`)
- Helper methods (`_api_request`, `_api_request_all_items`, `_get_auth_headers`)
- Class attributes (`type`, `version`, `description`, `properties`)
- Detected operations list with resource/operation pairs

## SYNC-CELERY SAFE

All operations are synchronous file reads. No async patterns.
