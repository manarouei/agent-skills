---
name: schema-build
version: "1.0.0"
description: Build formal BaseNode-compliant schema from inferred data. Validates against our backend's BaseNode contract at /home/toni/n8n/back/nodes/base.py.

# Contract
autonomy_level: SUGGEST
side_effects: []
timeout_seconds: 60
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id"
max_fix_iterations: 1

input_schema:
  type: object
  required: [correlation_id, inferred_schema, trace_map]
  properties:
    correlation_id:
      type: string
    inferred_schema:
      type: object
    trace_map:
      type: object

output_schema:
  type: object
  required: [node_schema, validation_result]
  properties:
    node_schema:
      type: object
      required: [type, version, description, properties]
      properties:
        type: { type: string }
        version: { type: number }
        description: { type: object }
        properties: { type: object }
    validation_result:
      type: object
      properties:
        valid: { type: boolean }
        errors: { type: array }
        warnings: { type: array }

required_artifacts:
  - name: node_schema.json
    type: json
    description: Final BaseNode-compliant schema

failure_modes: [validation_error]
depends_on: [schema-infer]
---

# Schema Build

Build formal BaseNode-compliant schema from inferred structure.

## BaseNode Contract (from /home/toni/n8n/back/nodes/base.py)

### Required Class Attributes

```python
class BaseNode(ABC):
    type: str           # e.g., "telegram"
    version: int        # e.g., 2
    description: Dict   # Node metadata
    properties: Dict    # Parameters configuration
```

### Description Structure

```json
{
  "displayName": "Telegram",
  "name": "telegram",
  "icon": "file:telegram.svg",
  "group": ["input", "output"],
  "description": "Send messages via Telegram",
  "inputs": [{"name": "main", "type": "main", "required": true}],
  "outputs": [{"name": "main", "type": "main", "required": true}],
  "usableAsTool": true
}
```

### Properties Structure

```json
{
  "parameters": [
    {
      "name": "resource",
      "type": "options",
      "display_name": "Resource",
      "options": [{"name": "Message", "value": "message"}],
      "default": "message",
      "required": true,
      "display_options": {"show": {"resource": ["message"]}}
    }
  ],
  "credentials": [
    {"name": "telegramApi", "type": "telegramApi", "required": true}
  ]
}
```

### NodeParameterType Enum

Valid parameter types (from base.py):
- `string`, `number`, `boolean`, `options`, `multiOptions`
- `color`, `json`, `collection`, `dateTime`, `node`
- `resourceLocator`, `notice`, `array`, `code`

## Validation Rules

Schema is INVALID if:
- Missing `type`, `version`, `description`, or `properties`
- `type` doesn't match kebab-case pattern
- Parameters use invalid `NodeParameterType`
- `display_options` references non-existent parameters

## Artifacts Emitted

- `artifacts/{correlation_id}/node_schema.json`
