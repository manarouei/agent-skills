---
name: test-generate
version: "1.0.0"
description: Generate pytest test suite for node implementation. Tests are placed in /home/toni/n8n/back/tests/ following existing patterns.

# Contract
autonomy_level: IMPLEMENT
side_effects: [fs]
timeout_seconds: 180
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id"
max_fix_iterations: 2

# Sync Celery Constraints (MANDATORY)
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: true
  forbids_background_tasks: true

input_schema:
  type: object
  required: [correlation_id, node_schema, files_modified, allowlist]
  properties:
    correlation_id:
      type: string
    node_schema:
      type: object
    files_modified:
      type: array
    allowlist:
      type: object

output_schema:
  type: object
  required: [test_files_created, test_count]
  properties:
    test_files_created:
      type: array
      items: { type: string }
    test_count:
      type: integer

required_artifacts:
  - name: test_manifest.json
    type: json
    description: List of generated tests

failure_modes: [validation_error, scope_violation]
depends_on: [code-convert, code-implement]
---

# Test Generate

Generate pytest test suite for node implementation.

## SCOPE ENFORCEMENT

Test files MUST be in allowlist patterns:
- `tests/test_{node_name}.py`
- `tests/integration/test_{node_name}_*.py`

## Test Structure

```python
# tests/test_{node_name}.py
import pytest
from unittest.mock import Mock, patch
from nodes.{node_name} import {ClassName}Node
from models import Node, WorkflowModel, NodeExecutionData

@pytest.fixture
def mock_workflow():
    return Mock(spec=WorkflowModel)

@pytest.fixture  
def mock_node_data():
    return Mock(spec=Node)

class Test{ClassName}Node:
    """Unit tests for {ClassName}Node"""
    
    def test_execute_operation_success(self, mock_workflow, mock_node_data):
        """Test successful operation execution"""
        ...
    
    def test_execute_invalid_params(self, mock_workflow, mock_node_data):
        """Test error handling for invalid parameters"""
        ...
    
    def test_credentials_required(self, mock_workflow, mock_node_data):
        """Test that missing credentials raises error"""
        ...
```

## Test Categories

### Unit Tests (Required)
- Happy path for each operation
- Invalid input handling
- Missing credentials
- Response parsing

### Integration Tests (Optional)
- Live API tests (skipped by default)
- Mock server tests

## Pytest Configuration

Tests use config from `/home/toni/n8n/back/pyproject.toml`:
- `asyncio_mode = "auto"`
- Markers: `slow`, `integration`, `unit`

## Artifacts Emitted

- `artifacts/{correlation_id}/test_manifest.json`
