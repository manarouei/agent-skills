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

# Sync Celery Constraints (MANDATORY)
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: true
  forbids_background_tasks: true

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
      description: "MANDATORY: Every field must map to source evidence. See .copilot/schemas/trace_map.schema.json"
      required: [correlation_id, node_type, trace_entries]
      properties:
        correlation_id: { type: string }
        node_type: { type: string }
        trace_entries:
          type: array
          minItems: 1
          items:
            type: object
            required: [field_path, source, evidence, confidence]
            properties:
              field_path: { type: string }
              source: { type: string, enum: [SOURCE_CODE, API_DOCS, ASSUMPTION] }
              evidence: { type: string, minLength: 10 }
              confidence: { type: string, enum: [high, medium, low] }
              assumption_rationale: { type: string }
              source_file: { type: string }
              line_range: { type: string }
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

## Trace Map Format (Canonical)

Matches `.copilot/schemas/trace_map.schema.json` and `contracts/skill_contract.py`:

```json
{
  "correlation_id": "abc-123",
  "node_type": "telegram",
  "trace_entries": [
    {
      "field_path": "operations[0].name",
      "source": "SOURCE_CODE",
      "evidence": "Function 'sendMessage' found in Telegram.node.ts",
      "confidence": "high",
      "source_file": "packages/nodes-base/nodes/Telegram/Telegram.node.ts",
      "line_range": "L45-L52",
      "excerpt_hash": "a1b2c3d4e5f6"
    },
    {
      "field_path": "credentials[0].type",
      "source": "ASSUMPTION",
      "evidence": "Inferred from operation pattern requiring API key",
      "confidence": "medium",
      "assumption_rationale": "Standard Telegram Bot API requires token auth"
    }
  ]
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
