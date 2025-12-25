---
name: source-classify
version: "1.0.0"
description: Classify source type for node implementation. Determines if source is Type1 (existing TypeScript node in n8n repo) or Type2 (documentation-only). Returns confidence score and evidence.

# Contract
autonomy_level: READ
side_effects: [net]
timeout_seconds: 60
retry:
  policy: safe
  max_retries: 2
  backoff_seconds: 2.0
idempotency:
  required: true
  key_spec: "correlation_id"
max_fix_iterations: 1

input_schema:
  type: object
  required: [correlation_id, normalized_name]
  properties:
    correlation_id:
      type: string
    normalized_name:
      type: string
    source_refs:
      type: object
      properties:
        ts_path: { type: string }
        docs_url: { type: string }

output_schema:
  type: object
  required: [source_type, confidence, evidence]
  properties:
    source_type:
      type: string
      enum: [TYPE1, TYPE2, UNKNOWN]
    confidence:
      type: number
      minimum: 0
      maximum: 1
    evidence:
      type: array
      items:
        type: object
        properties:
          type: { type: string }
          path_or_url: { type: string }
          verified: { type: boolean }

required_artifacts:
  - name: classification.json
    type: json
    description: Classification result with evidence

failure_modes: [network_error, timeout, validation_error]
depends_on: [node-normalize]
---

# Source Classify

Classify source type to determine implementation approach.

## Source Types

| Type | Description | Implementation Approach |
|------|-------------|------------------------|
| TYPE1 | Existing n8n TypeScript node | Code conversion |
| TYPE2 | Documentation only | LLM implementation |
| UNKNOWN | Cannot determine | Requires human input |

## Classification Logic

1. Check if `source_refs.ts_path` points to valid TypeScript file
2. Search n8n repository for matching node patterns:
   - `packages/nodes-base/nodes/{NodeName}/{NodeName}.node.ts`
3. Check if `source_refs.docs_url` is provided
4. Calculate confidence based on evidence

## Confidence Thresholds

| Range | Action |
|-------|--------|
| 0.9-1.0 | Proceed automatically |
| 0.7-0.9 | Flag for verification |
| <0.7 | Require human input |

## Evidence Collection

Each evidence entry must include:
- `type`: "ts_file" | "docs_url" | "api_spec"
- `path_or_url`: Actual location
- `verified`: Whether existence was confirmed

## Artifacts Emitted

- `artifacts/{correlation_id}/classification.json`
