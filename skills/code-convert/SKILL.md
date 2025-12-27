---
name: code-convert
version: "1.0.0"
description: Convert TypeScript n8n node to Python BaseNode implementation. For TYPE1 sources only. Preserves logic while adapting to our backend patterns.

# Contract
autonomy_level: IMPLEMENT
side_effects: [fs]
timeout_seconds: 300
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id"
max_fix_iterations: 3

# Sync Celery Constraints (MANDATORY)
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: true
  forbids_background_tasks: true

input_schema:
  type: object
  required: [correlation_id, source_type, parsed_sections, node_schema, allowlist]
  properties:
    correlation_id:
      type: string
    source_type:
      type: string
      const: TYPE1
    parsed_sections:
      type: object
    node_schema:
      type: object
    allowlist:
      type: object

output_schema:
  type: object
  required: [files_modified, conversion_notes]
  properties:
    files_modified:
      type: array
      items: { type: string }
    conversion_notes:
      type: array
      items: { type: string }

required_artifacts:
  - name: conversion_log.json
    type: json
    description: Conversion decisions and mappings
  - name: files.diff
    type: diff
    description: Git diff of changes

failure_modes: [parse_error, scope_violation, validation_error]
depends_on: [node-scaffold]
---

# Code Convert

Convert TypeScript n8n node code to Python BaseNode implementation.

## SCOPE ENFORCEMENT

**ALL file modifications MUST be within allowlist patterns.**
Run `scripts/enforce_scope.py` before committing.

## Conversion Mappings

### Language Constructs

| TypeScript | Python |
|------------|--------|
| `interface` | `TypedDict` or Pydantic model |
| `async/await` | `async/await` |
| `this.helpers.request()` | `requests` / `httpx` |
| `this.getNodeParameter()` | `self.get_node_parameter()` |
| `this.getCredentials()` | `self.get_credentials()` |

### n8n Patterns → BaseNode

| n8n TypeScript | Our BaseNode |
|----------------|--------------|
| `execute()` returns `INodeExecutionData[][]` | `execute()` returns `List[List[NodeExecutionData]]` |
| `description.properties` | `properties["parameters"]` |
| `credentials` array | `properties["credentials"]` |

## Conversion Process

1. Parse TypeScript `execute()` method
2. Map operation routing logic
3. Convert API call patterns
4. Preserve error handling
5. Keep pagination/retry logic

## DO NOT

- Optimize during conversion
- Add parameters not in source
- Change operation names
- Skip credential handling

## Artifacts Emitted

- `artifacts/{correlation_id}/conversion_log.json`
- `artifacts/{correlation_id}/files.diff`
