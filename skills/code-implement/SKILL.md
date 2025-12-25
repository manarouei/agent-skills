---
name: code-implement
version: "1.0.0"
description: Implement node from API documentation using LLM. For TYPE2 sources only. Generates implementation based on trace-mapped schema.

# Contract
autonomy_level: IMPLEMENT
side_effects: [fs, net]
timeout_seconds: 600
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id"
max_fix_iterations: 3

input_schema:
  type: object
  required: [correlation_id, source_type, node_schema, trace_map, allowlist]
  properties:
    correlation_id:
      type: string
    source_type:
      type: string
      const: TYPE2
    node_schema:
      type: object
    trace_map:
      type: object
    allowlist:
      type: object

output_schema:
  type: object
  required: [files_modified, implementation_notes, assumptions_used]
  properties:
    files_modified:
      type: array
      items: { type: string }
    implementation_notes:
      type: array
    assumptions_used:
      type: array
      description: List of trace_map ASSUMPTION entries used

required_artifacts:
  - name: implementation_log.json
    type: json
    description: Implementation decisions
  - name: files.diff
    type: diff
    description: Git diff of changes

failure_modes: [parse_error, scope_violation, validation_error, trace_incomplete]
depends_on: [node-scaffold]
---

# Code Implement

Generate implementation from API documentation (TYPE2 only).

## SCOPE ENFORCEMENT

**ALL file modifications MUST be within allowlist patterns.**

## TRACE MAP REQUIREMENT

**Every implemented operation MUST reference trace_map entries.**

If an operation requires an ASSUMPTION from trace_map:
1. Document in `assumptions_used` output
2. Add TODO comment in code
3. Flag for human verification

## Implementation Process

For each operation in schema:

1. Read trace_map for operation parameters
2. Construct API request from documented patterns
3. Add authentication from credentials
4. Handle response parsing
5. Add error handling

## BaseNode Method Template

```python
def execute(self) -> List[List[NodeExecutionData]]:
    input_data = self.get_input_data()
    results = []
    
    for item in input_data:
        operation = self.get_node_parameter("operation", 0)
        
        if operation == "create":
            result = self._execute_create(item)
        elif operation == "get":
            result = self._execute_get(item)
        # ... more operations
        
        results.append(result)
    
    return [results]

def _execute_create(self, item: NodeExecutionData) -> NodeExecutionData:
    credentials = self.get_credentials("apiCredential")
    # Implementation based on trace_map evidence
    ...
```

## DO NOT

- Invent parameters without trace_map evidence
- Skip ASSUMPTION verification
- Implement undocumented endpoints

## Artifacts Emitted

- `artifacts/{correlation_id}/implementation_log.json`
- `artifacts/{correlation_id}/files.diff`
