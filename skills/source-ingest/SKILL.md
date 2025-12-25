---
name: source-ingest
version: "1.0.0"
description: Fetch and parse source materials for node implementation. Retrieves TypeScript source or API documentation based on classified source type.

# Contract
autonomy_level: READ
side_effects: [net]
timeout_seconds: 120
retry:
  policy: safe
  max_retries: 3
  backoff_seconds: 5.0
idempotency:
  required: true
  key_spec: "correlation_id"
max_fix_iterations: 1

input_schema:
  type: object
  required: [correlation_id, source_type, evidence]
  properties:
    correlation_id:
      type: string
    source_type:
      type: string
      enum: [TYPE1, TYPE2]
    evidence:
      type: array

output_schema:
  type: object
  required: [raw_content, parsed_sections, metadata]
  properties:
    raw_content:
      type: string
    parsed_sections:
      type: object
    metadata:
      type: object
      properties:
        fetch_time: { type: string, format: date-time }
        source_url: { type: string }
        content_hash: { type: string }

required_artifacts:
  - name: raw_source.txt
    type: txt
    description: Raw fetched content
  - name: parsed_source.json
    type: json
    description: Parsed and structured source content

failure_modes: [network_error, timeout, parse_error]
depends_on: [source-classify]
---

# Source Ingest

Fetch and parse source materials based on classified source type.

## TYPE1: TypeScript Source

1. Fetch TypeScript file from GitHub/local path
2. Parse and extract:
   - Node class definition
   - `description` object
   - `properties` array (parameters)
   - `execute()` / `trigger()` methods
   - Credential references
3. Store parsed content

## TYPE2: Documentation

1. Fetch documentation from URLs
2. Parse format (HTML, Markdown, OpenAPI)
3. Extract:
   - Endpoints and operations
   - Parameters and schemas
   - Authentication requirements
   - Example requests/responses

## Parsed Sections Structure

```json
{
  "class_name": "TelegramNode",
  "type": "telegram",
  "version": 2.0,
  "description": { ... },
  "properties": { ... },
  "methods": ["execute"],
  "credentials": ["telegramApi"]
}
```

## Artifacts Emitted

- `artifacts/{correlation_id}/raw_source.txt`
- `artifacts/{correlation_id}/parsed_source.json`
