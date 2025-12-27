---
name: node-scaffold
version: "1.0.0"
description: Generate node implementation scaffold from schema. Creates file structure matching our backend at /home/toni/n8n/back/nodes/.

# Contract
autonomy_level: IMPLEMENT
side_effects: [fs]
timeout_seconds: 60
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id + node_type"
max_fix_iterations: 1

# Sync Celery Constraints (MANDATORY)
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: true
  forbids_background_tasks: true

input_schema:
  type: object
  required: [correlation_id, node_schema, normalized_name]
  properties:
    correlation_id:
      type: string
    node_schema:
      type: object
    normalized_name:
      type: string

output_schema:
  type: object
  required: [files_created, allowlist]
  properties:
    files_created:
      type: array
      items: { type: string }
    allowlist:
      type: object
      properties:
        node_name: { type: string }
        patterns: { type: array }

required_artifacts:
  - name: scaffold_manifest.json
    type: json
    description: List of created files
  - name: allowlist.json
    type: json
    description: Scope allowlist for this node

failure_modes: [validation_error, permission_denied]
depends_on: [schema-build]
---

# Node Scaffold

Generate implementation scaffold matching our backend structure.

## Target Structure

Files are created in `/home/toni/n8n/back/nodes/`:

```
nodes/
├── {node_name}.py          # Main node class
└── (optional subdirs for complex nodes)
```

## Scaffold Template

```python
from typing import Dict, List, Any
from models import NodeExecutionData, Node, WorkflowModel
from .base import BaseNode, NodeParameterType

class {ClassName}Node(BaseNode):
    """
    {DisplayName} node for {description}
    """
    
    type = "{node_type}"
    version = {version}
    
    description = {
        "displayName": "{DisplayName}",
        "name": "{node_type}",
        "icon": "file:{node_type}.svg",
        "group": ["input", "output"],
        "description": "{description}",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
    }
    
    properties = {
        "parameters": [
            # TODO: Generated from schema
        ],
        "credentials": [
            # TODO: Generated from schema
        ]
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute node functionality."""
        # TODO: Implement operations
        raise NotImplementedError("execute() not implemented")
```

## Scope Allowlist

Generates `allowlist.json` with patterns:
- `nodes/{node_name}*`
- `tests/*{node_name}*`
- `credentials/*{node_name}*`

## Artifacts Emitted

- `artifacts/{correlation_id}/scaffold_manifest.json`
- `artifacts/{correlation_id}/allowlist.json`
