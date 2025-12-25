---
name: node-normalize
version: "1.0.0"
description: Normalize incoming node implementation requests. Generates a correlation ID, converts node names to kebab-case, and creates an immutable request snapshot. Use when starting a new node implementation pipeline.

# Contract
autonomy_level: READ
side_effects: []
timeout_seconds: 30
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "raw_node_name"
max_fix_iterations: 1

input_schema:
  type: object
  required: [raw_node_name]
  properties:
    raw_node_name:
      type: string
      description: Raw node name from user input
    source_refs:
      type: object
      properties:
        ts_path: { type: string }
        docs_url: { type: string }

output_schema:
  type: object
  required: [correlation_id, normalized_name, snapshot]
  properties:
    correlation_id:
      type: string
      pattern: "^node-[a-f0-9-]{36}$"
    normalized_name:
      type: string
      pattern: "^[a-z][a-z0-9-]*[a-z0-9]$"
    snapshot:
      type: object

required_artifacts:
  - name: request_snapshot.json
    type: json
    description: Immutable snapshot of the normalization request

failure_modes: [validation_error]
depends_on: []
---

# Node Normalize

Normalize incoming node implementation requests before processing.

## Input

- `raw_node_name`: The raw node name from user input (e.g., "Telegram Bot", "shopify_api")
- `source_refs` (optional): Object with `ts_path` and/or `docs_url`

## Output

- `correlation_id`: UUID v4 prefixed with "node-" for pipeline tracking
- `normalized_name`: Kebab-case name for filesystem compatibility
- `snapshot`: Immutable request snapshot with timestamp

## Normalization Rules

1. Convert to lowercase
2. Replace spaces and underscores with hyphens
3. Remove special characters (keep only alphanumeric and hyphens)
4. Remove consecutive hyphens
5. Trim leading/trailing hyphens

## Examples

| Input | Output |
|-------|--------|
| "Telegram Bot" | telegram-bot |
| "shopify_api" | shopify-api |
| "AWS S3" | aws-s3 |

## Artifacts Emitted

- `artifacts/{correlation_id}/request_snapshot.json`

## Failure Modes

- `validation_error`: Empty or whitespace-only input
