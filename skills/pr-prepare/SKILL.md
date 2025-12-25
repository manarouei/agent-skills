---
name: pr-prepare
version: "1.0.0"
description: Prepare PR artifacts for submission. Generates PR description, changelog entry, and node_definitions update.

# Contract
autonomy_level: SUGGEST
side_effects: [fs]
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
  required: [correlation_id, node_schema, validation_report, files_modified]
  properties:
    correlation_id:
      type: string
    node_schema:
      type: object
    validation_report:
      type: object
    files_modified:
      type: array

output_schema:
  type: object
  required: [pr_artifacts, node_definitions_entry]
  properties:
    pr_artifacts:
      type: object
      properties:
        description: { type: string }
        title: { type: string }
        labels: { type: array }
    node_definitions_entry:
      type: string
      description: Code to add to nodes/__init__.py

required_artifacts:
  - name: pr_description.md
    type: md
    description: PR description template
  - name: node_definitions_update.py
    type: py
    description: Code snippet for nodes/__init__.py

failure_modes: [validation_error]
depends_on: [code-validate]
---

# PR Prepare

Generate PR artifacts for human review and submission.

## Preconditions

PR preparation requires:
- `validation_report.passed == true`
- No escalation reports
- All scope checks passed

## PR Description Template

```markdown
## Summary

Adds `{node_type}` node implementation.

**Source type:** TYPE1 (converted) / TYPE2 (implemented from docs)

## Changes

- `nodes/{node_name}.py` - Node implementation
- `tests/test_{node_name}.py` - Unit tests
- `nodes/__init__.py` - Registry update

## Operations Implemented

| Operation | Description |
|-----------|-------------|
{operations_table}

## Credentials

- Type: `{credential_type}`
- Required: Yes/No

## Testing

- [ ] Unit tests pass
- [ ] Ruff check passes  
- [ ] Mypy check passes
- [ ] Manual testing with real credentials

## Trace Map Coverage

- Total fields: {total}
- Traced: {traced}
- Assumptions: {assumptions}

## Checklist

- [ ] Code follows BaseNode contract
- [ ] All parameters have trace_map evidence
- [ ] Error handling implemented
- [ ] Documentation updated
```

## node_definitions Update

```python
# Add to nodes/__init__.py

from .{node_name} import {ClassName}Node

# Add to node_definitions dict:
'{node_type}': {{'node_class': {ClassName}Node, 'type': 'regular'}},
```

## Artifacts Emitted

- `artifacts/{correlation_id}/pr_description.md`
- `artifacts/{correlation_id}/node_definitions_update.py`
