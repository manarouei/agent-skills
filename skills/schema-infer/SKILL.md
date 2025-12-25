---
name: schema-infer
version: "1.0.0"
description: Infer node schema from ingested source with MANDATORY trace map. Every field must have evidence linking to source. No hallucination allowed.

# Contract
autonomy_level: SUGGEST
side_effects: []
timeout_seconds: 180
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id"
max_fix_iterations: 1

input_schema:
  type: object
  required: [correlation_id, parsed_sections, source_type]
  properties:
    correlation_id:
      type: string
    parsed_sections:
      type: object
    source_type:
      type: string
      enum: [TYPE1, TYPE2]

output_schema:
  type: object
  required: [inferred_schema, trace_map, assumptions]
  properties:
    inferred_schema:
      type: object
      required: [type, version, operations, credentials]
      properties:
        type: { type: string }
        version: { type: number }
        operations: { type: array }
        credentials: { type: array }
        parameters: { type: array }
    trace_map:
      type: object
      description: "MANDATORY: Every field must map to source evidence"
      additionalProperties:
        type: object
        required: [source_type, source_ref, locator, excerpt_hash]
        properties:
          source_type: { type: string, enum: [TS, DOC, ASSUMPTION] }
          source_ref: { type: string }
          locator: { type: string }
          excerpt_hash: { type: string }
    assumptions:
      type: array
      items:
        type: string
      description: "Explicit assumptions requiring verification"

required_artifacts:
  - name: inferred_schema.json
    type: json
    description: Inferred schema structure
  - name: trace_map.json
    type: json
    description: Field-to-evidence trace map

failure_modes: [parse_error, trace_incomplete, validation_error]
depends_on: [source-ingest]
---

# Schema Infer

Analyze ingested source to infer node schema with **MANDATORY TRACE MAP**.

## CRITICAL: Trace Map Requirement

**Every field in the inferred schema MUST have a trace_map entry.**

If evidence cannot be found:
1. Mark field as `ASSUMPTION` in trace_map
2. Add to `assumptions` list with verification instructions
3. DO NOT invent parameters without evidence

## Trace Map Format

```json
{
  "operations.0.name": {
    "source_type": "TS",
    "source_ref": "packages/nodes-base/nodes/Telegram/Telegram.node.ts",
    "locator": "L45-L52",
    "excerpt_hash": "a1b2c3d4e5f6"
  },
  "credentials.0.type": {
    "source_type": "ASSUMPTION",
    "source_ref": "inferred from operation pattern",
    "locator": "N/A",
    "excerpt_hash": "N/A"
  }
}
```

## BaseNode-Compatible Schema Structure

Output must conform to our backend's BaseNode contract:

```json
{
  "type": "telegram",
  "version": 2,
  "description": {
    "displayName": "Telegram",
    "name": "telegram",
    "inputs": [{"name": "main", "type": "main"}],
    "outputs": [{"name": "main", "type": "main"}]
  },
  "properties": {
    "parameters": [
      {
        "name": "resource",
        "type": "options",
        "options": [...],
        "default": "message"
      }
    ]
  },
  "credentials": ["telegramApi"]
}
```

## Validation Gates

Schema inference FAILS if:
- trace_map coverage < 80% of fields
- Any required field has no trace entry AND no ASSUMPTION marker
- Output doesn't match BaseNode contract structure

## Artifacts Emitted

- `artifacts/{correlation_id}/inferred_schema.json`
- `artifacts/{correlation_id}/trace_map.json`
