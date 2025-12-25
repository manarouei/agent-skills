# BaseNode Contract

> Source: `/home/toni/n8n/back/nodes/base.py`  
> Last verified: 2025-01-XX

This document captures the **actual** BaseNode contract from the n8n backend codebase. All node implementations **must** adhere to this contract.

## Required Class Attributes

| Attribute | Type | Required | Description |
|-----------|------|----------|-------------|
| `type` | `str` | ✓ | Unique node type identifier (e.g., `"n8n-nodes-base.telegram"`) |
| `version` | `int` | ✓ | Node version number (start at 1) |
| `description` | `Dict` | ✓ | Node metadata (displayName, name, description, properties) |
| `properties` | `Dict` | ✓ | Node configuration including parameters and credentials |

## Description Structure

```python
description = {
    "displayName": str,           # Human-readable name
    "name": str,                  # Internal name (lowercase, no spaces)
    "description": str,           # Brief description of what node does
    "icon": str,                  # Optional: "file:icon.png" or "fa:icon-name"
    "group": List[str],          # Categories: ["input", "output", "transform"]
    "version": int,               # Same as class version
    "defaults": {
        "name": str,              # Default node instance name
        "color": str,             # Hex color for UI
    },
    "inputs": List[str],          # Input types: ["main"]
    "outputs": List[str],         # Output types: ["main"]
    "credentials": List[Dict],    # Credential definitions
}
```

## Properties Structure

```python
properties = {
    "parameters": [
        {
            "displayName": str,       # Parameter label
            "name": str,              # Parameter key
            "type": str,              # "string", "number", "options", "boolean", "collection"
            "default": Any,           # Default value
            "required": bool,         # Is parameter required?
            "description": str,       # Help text
            "displayOptions": {       # Conditional visibility
                "show": {"operation": ["value1", "value2"]},
                "hide": {...}
            },
            "options": [...],         # For type="options"
        },
        ...
    ]
}
```

## Required Methods

### `execute(self) -> List[List[NodeExecutionData]]`

Main execution method. Must return nested list where:
- Outer list = output branches
- Inner list = items in that branch

```python
async def execute(self) -> List[List[NodeExecutionData]]:
    """
    Execute the node operation.
    
    Returns:
        List[List[NodeExecutionData]]: Nested list of execution results.
        - Outer list represents output branches (usually 1)
        - Inner list represents items in that branch
    """
    items = self.get_input_data()
    return_items = []
    
    for item in items:
        # Process item
        result = await self._process_item(item)
        return_items.append(result)
    
    return [return_items]  # Single output branch
```

### `get_node_parameter(self, name: str, item_index: int = 0) -> Any`

Retrieve a parameter value.

```python
# Get string parameter
operation = self.get_node_parameter("operation", 0)

# Get with default
limit = self.get_node_parameter("limit", 0) or 100
```

### `get_credentials(self, name: str) -> Dict`

Retrieve credentials for external services.

```python
credentials = self.get_credentials("telegramApi")
token = credentials.get("accessToken")
```

### `get_input_data(self) -> List[Dict]`

Get input items from previous node.

```python
items = self.get_input_data()
for i, item in enumerate(items):
    data = item.get("json", {})
```

## NodeExecutionData Format

```python
NodeExecutionData = {
    "json": Dict[str, Any],      # Main data payload
    "binary": Optional[Dict],     # Binary data (files, images)
    "pairedItem": {
        "item": int,              # Index of input item that produced this
    }
}
```

## Error Handling

```python
from n8n.errors import NodeApiError, NodeOperationError

class MyNode(BaseNode):
    async def execute(self):
        try:
            response = await self._make_request()
        except HttpError as e:
            raise NodeApiError(
                self,
                error=e,
                message="API request failed",
            )
```

## Node Registration

Nodes are registered in `nodes/__init__.py`:

```python
from .my_node import MyNode

node_definitions = {
    'n8n-nodes-base.myNode': {
        'node_class': MyNode,
        'type': 'regular',  # or 'trigger'
    },
}
```

## Golden Example: TelegramNode

Reference implementation at `/home/toni/n8n/back/nodes/telegram.py`:

```python
class TelegramNode(BaseNode):
    type = "n8n-nodes-base.telegram"
    version = 1
    
    description = {
        "displayName": "Telegram",
        "name": "telegram",
        "description": "Send messages via Telegram",
        "group": ["output"],
        "version": 1,
        "inputs": ["main"],
        "outputs": ["main"],
        "credentials": [
            {
                "name": "telegramApi",
                "required": True,
            }
        ],
    }
    
    properties = {
        "parameters": [
            {
                "displayName": "Operation",
                "name": "operation",
                "type": "options",
                "default": "sendMessage",
                "options": [
                    {"name": "Send Message", "value": "sendMessage"},
                    # ...
                ],
            },
            # ... more parameters
        ]
    }
    
    async def execute(self):
        credentials = self.get_credentials("telegramApi")
        operation = self.get_node_parameter("operation", 0)
        
        # ... implementation
        
        return [[{"json": result}]]
```

## Validation Checklist

- [ ] Class has `type`, `version`, `description`, `properties` attributes
- [ ] `type` follows format: `n8n-nodes-base.{nodeName}`
- [ ] `execute()` returns `List[List[NodeExecutionData]]`
- [ ] All parameters in `properties["parameters"]` have required fields
- [ ] Credentials are properly declared and retrieved
- [ ] Errors are wrapped in `NodeApiError` or `NodeOperationError`
- [ ] Node is registered in `nodes/__init__.py`

## Testing Requirements

```bash
# Unit tests
pytest tests/test_my_node.py -v

# Lint
ruff check nodes/my_node.py

# Type check
mypy nodes/my_node.py
```

## Schema Inference Implications

When inferring schemas from source code or API docs:

1. **Parameters** → Map to `properties["parameters"]`
2. **Credentials** → Map to `description["credentials"]`
3. **Operations** → Map to parameter with `type: "options"` named "operation"
4. **Output fields** → Map to `NodeExecutionData["json"]` structure

Every field in the schema **must** have a trace map entry documenting its source.
