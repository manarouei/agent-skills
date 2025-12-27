#!/usr/bin/env python3
"""
Unit tests for node-scaffold skill implementation.

Tests the scaffold generation functionality including:
- File generation from schema
- Allowlist artifact generation
- Manifest artifact generation
- Template rendering
- Edge cases
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


# Test imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the implementation module dynamically (hyphenated directory)
import importlib.util
impl_path = Path(__file__).parent.parent / "skills" / "node-scaffold" / "impl.py"
spec = importlib.util.spec_from_file_location("node_scaffold_impl", impl_path)
node_scaffold_impl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(node_scaffold_impl)

# Import functions for testing
execute_node_scaffold = node_scaffold_impl.execute_node_scaffold
normalize_to_class_name = node_scaffold_impl.normalize_to_class_name
normalize_to_module_name = node_scaffold_impl.normalize_to_module_name
normalize_operation_name = node_scaffold_impl.normalize_operation_name
format_python_value = node_scaffold_impl.format_python_value
extract_operations = node_scaffold_impl.extract_operations


@dataclass
class MockExecutionContext:
    """Mock ExecutionContext for testing."""
    correlation_id: str
    skill_name: str
    inputs: dict[str, Any]
    artifacts_dir: Path
    iteration: int = 0
    trace: list[dict[str, Any]] = field(default_factory=list)
    
    def log(self, event: str, data: dict[str, Any] | None = None) -> None:
        """Add event to execution trace."""
        self.trace.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": event,
            "data": data or {},
        })


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create temporary directory for test artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_node_schema():
    """Sample node schema for testing."""
    return {
        "type": "n8n-nodes-base.testService",
        "version": 1,
        "description": {
            "displayName": "Test Service",
            "name": "testService",
            "description": "A test service node for unit testing",
            "icon": "file:testService.svg",
            "group": ["output"],
            "version": 1,
            "inputs": ["main"],
            "outputs": ["main"],
            "credentials": [
                {
                    "name": "testServiceApi",
                    "required": True,
                    "displayName": "Test Service API",
                }
            ],
        },
        "properties": {
            "parameters": [
                {
                    "displayName": "Operation",
                    "name": "operation",
                    "type": "options",
                    "default": "getData",
                    "required": True,
                    "options": [
                        {"name": "Get Data", "value": "getData"},
                        {"name": "Send Data", "value": "sendData"},
                        {"name": "Delete Data", "value": "deleteData"},
                    ],
                },
                {
                    "displayName": "Resource ID",
                    "name": "resourceId",
                    "type": "string",
                    "default": "",
                    "required": True,
                    "description": "The ID of the resource",
                },
                {
                    "displayName": "Limit",
                    "name": "limit",
                    "type": "number",
                    "default": 100,
                    "displayOptions": {
                        "show": {"operation": ["getData"]},
                    },
                },
            ],
        },
    }


@pytest.fixture
def minimal_node_schema():
    """Minimal valid node schema."""
    return {
        "type": "minimal",
        "version": 1,
        "description": {
            "displayName": "Minimal",
            "name": "minimal",
        },
        "properties": {
            "parameters": [],
        },
    }


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================

class TestNormalizeToClassName:
    """Tests for normalize_to_class_name function."""

    def test_simple_name(self):
        assert normalize_to_class_name("telegram") == "Telegram"

    def test_camel_case(self):
        assert normalize_to_class_name("testService") == "Testservice"

    def test_with_prefix(self):
        assert normalize_to_class_name("n8n-nodes-base.telegram") == "Telegram"

    def test_with_hyphens(self):
        assert normalize_to_class_name("my-cool-node") == "MyCoolNode"

    def test_with_underscores(self):
        assert normalize_to_class_name("my_cool_node") == "MyCoolNode"


class TestNormalizeToModuleName:
    """Tests for normalize_to_module_name function."""

    def test_simple_name(self):
        assert normalize_to_module_name("telegram") == "telegram"

    def test_camel_case(self):
        assert normalize_to_module_name("testService") == "test_service"

    def test_with_prefix(self):
        assert normalize_to_module_name("n8n-nodes-base.telegram") == "telegram"

    def test_with_hyphens(self):
        assert normalize_to_module_name("my-cool-node") == "my_cool_node"


class TestNormalizeOperationName:
    """Tests for normalize_operation_name function."""

    def test_camel_case(self):
        assert normalize_operation_name("getData") == "get_data"

    def test_already_snake(self):
        assert normalize_operation_name("get_data") == "get_data"

    def test_complex(self):
        assert normalize_operation_name("sendEmailMessage") == "send_email_message"


class TestFormatPythonValue:
    """Tests for format_python_value function."""

    def test_none(self):
        assert format_python_value(None) == "None"

    def test_bool_true(self):
        assert format_python_value(True) == "True"

    def test_bool_false(self):
        assert format_python_value(False) == "False"

    def test_string(self):
        # Uses repr() which produces single quotes
        assert format_python_value("hello") == "'hello'"

    def test_string_with_quotes(self):
        result = format_python_value('say "hello"')
        # repr() handles quote escaping appropriately
        assert result == '\'say "hello"\''

    def test_list(self):
        result = format_python_value(["a", "b"])
        # Output is Python literal, not JSON - use eval to verify
        assert eval(result) == ["a", "b"]

    def test_dict(self):
        result = format_python_value({"key": "value"})
        # Output is Python literal, not JSON - use eval to verify
        assert eval(result) == {"key": "value"}

    def test_nested_with_booleans(self):
        """Ensure booleans in nested structures are Python True/False, not JSON true/false."""
        result = format_python_value([{"enabled": True, "disabled": False}])
        assert "True" in result
        assert "False" in result
        assert "true" not in result
        assert "false" not in result
        assert eval(result) == [{"enabled": True, "disabled": False}]

    def test_number(self):
        assert format_python_value(42) == "42"


class TestExtractOperations:
    """Tests for extract_operations function."""

    def test_with_operation_parameter(self, sample_node_schema):
        params = sample_node_schema["properties"]["parameters"]
        ops = extract_operations(params)
        assert len(ops) == 3
        assert ops[0]["value"] == "getData"

    def test_no_operation_parameter(self):
        params = [{"name": "other", "type": "string"}]
        ops = extract_operations(params)
        assert ops == []

    def test_empty_parameters(self):
        ops = extract_operations([])
        assert ops == []


# =============================================================================
# MAIN IMPLEMENTATION TESTS
# =============================================================================

class TestExecuteNodeScaffold:
    """Tests for execute_node_scaffold function."""

    def test_generates_node_file(self, temp_dir, sample_node_schema):
        """Test that node Python file is generated."""
        ctx = MockExecutionContext(
            correlation_id="TEST-001",
            skill_name="node-scaffold",
            inputs={
                "correlation_id": "TEST-001",
                "node_schema": sample_node_schema,
                "normalized_name": "testService",
            },
            artifacts_dir=temp_dir / "artifacts",
        )
        
        result = execute_node_scaffold(ctx)
        
        assert "files_created" in result
        assert len(result["files_created"]) >= 1
        
        # Check node file exists and has content
        node_files = [f for f in result["files_created"] if f.endswith(".py") and not f.endswith("__init__.py")]
        assert len(node_files) == 1
        
        node_content = Path(node_files[0]).read_text()
        assert "class TestserviceNode(BaseNode):" in node_content
        assert 'type = "n8n-nodes-base.testService"' in node_content
        assert "version = 1" in node_content

    def test_generates_init_file(self, temp_dir, sample_node_schema):
        """Test that __init__.py is generated."""
        ctx = MockExecutionContext(
            correlation_id="TEST-002",
            skill_name="node-scaffold",
            inputs={
                "correlation_id": "TEST-002",
                "node_schema": sample_node_schema,
                "normalized_name": "testService",
            },
            artifacts_dir=temp_dir / "artifacts",
        )
        
        result = execute_node_scaffold(ctx)
        
        init_files = [f for f in result["files_created"] if f.endswith("__init__.py")]
        assert len(init_files) == 1
        
        init_content = Path(init_files[0]).read_text()
        assert "TestserviceNode" in init_content

    def test_generates_manifest_artifact(self, temp_dir, sample_node_schema):
        """Test that scaffold_manifest.json is generated."""
        artifacts_dir = temp_dir / "artifacts"
        ctx = MockExecutionContext(
            correlation_id="TEST-003",
            skill_name="node-scaffold",
            inputs={
                "correlation_id": "TEST-003",
                "node_schema": sample_node_schema,
                "normalized_name": "testService",
            },
            artifacts_dir=artifacts_dir,
        )
        
        execute_node_scaffold(ctx)
        
        manifest_path = artifacts_dir / "scaffold_manifest.json"
        assert manifest_path.exists()
        
        manifest = json.loads(manifest_path.read_text())
        assert manifest["correlation_id"] == "TEST-003"
        assert manifest["node_name"] == "testService"
        assert "files_created" in manifest

    def test_generates_allowlist_artifact(self, temp_dir, sample_node_schema):
        """Test that allowlist.json is generated."""
        artifacts_dir = temp_dir / "artifacts"
        ctx = MockExecutionContext(
            correlation_id="TEST-004",
            skill_name="node-scaffold",
            inputs={
                "correlation_id": "TEST-004",
                "node_schema": sample_node_schema,
                "normalized_name": "testService",
            },
            artifacts_dir=artifacts_dir,
        )
        
        result = execute_node_scaffold(ctx)
        
        allowlist_path = artifacts_dir / "allowlist.json"
        assert allowlist_path.exists()
        
        allowlist = json.loads(allowlist_path.read_text())
        assert allowlist["node_name"] == "testService"
        assert "allowed_paths" in allowlist
        assert any("test_service" in p or "testService" in p for p in allowlist["allowed_paths"])
        
        # Check output includes allowlist
        assert "allowlist" in result
        assert result["allowlist"]["node_name"] == "testService"

    def test_includes_operation_stubs(self, temp_dir, sample_node_schema):
        """Test that operation handler stubs are generated."""
        ctx = MockExecutionContext(
            correlation_id="TEST-005",
            skill_name="node-scaffold",
            inputs={
                "correlation_id": "TEST-005",
                "node_schema": sample_node_schema,
                "normalized_name": "testService",
            },
            artifacts_dir=temp_dir / "artifacts",
        )
        
        result = execute_node_scaffold(ctx)
        
        node_files = [f for f in result["files_created"] if f.endswith(".py") and not f.endswith("__init__.py")]
        node_content = Path(node_files[0]).read_text()
        
        # Should have stubs for all operations
        assert "_handle_get_data" in node_content
        assert "_handle_send_data" in node_content
        assert "_handle_delete_data" in node_content

    def test_minimal_schema(self, temp_dir, minimal_node_schema):
        """Test with minimal valid schema."""
        ctx = MockExecutionContext(
            correlation_id="TEST-006",
            skill_name="node-scaffold",
            inputs={
                "correlation_id": "TEST-006",
                "node_schema": minimal_node_schema,
                "normalized_name": "minimal",
            },
            artifacts_dir=temp_dir / "artifacts",
        )
        
        result = execute_node_scaffold(ctx)
        
        assert len(result["files_created"]) >= 1
        
        node_files = [f for f in result["files_created"] if f.endswith(".py") and not f.endswith("__init__.py")]
        node_content = Path(node_files[0]).read_text()
        assert "class MinimalNode(BaseNode):" in node_content

    def test_missing_node_schema_raises(self, temp_dir):
        """Test that missing node_schema raises ValueError."""
        ctx = MockExecutionContext(
            correlation_id="TEST-007",
            skill_name="node-scaffold",
            inputs={
                "correlation_id": "TEST-007",
                "normalized_name": "test",
            },
            artifacts_dir=temp_dir / "artifacts",
        )
        
        with pytest.raises(ValueError, match="node_schema is required"):
            execute_node_scaffold(ctx)

    def test_missing_normalized_name_raises(self, temp_dir, sample_node_schema):
        """Test that missing normalized_name raises ValueError."""
        ctx = MockExecutionContext(
            correlation_id="TEST-008",
            skill_name="node-scaffold",
            inputs={
                "correlation_id": "TEST-008",
                "node_schema": sample_node_schema,
            },
            artifacts_dir=temp_dir / "artifacts",
        )
        
        with pytest.raises(ValueError, match="normalized_name is required"):
            execute_node_scaffold(ctx)

    def test_custom_target_dir(self, temp_dir, sample_node_schema):
        """Test writing to custom target directory."""
        target_dir = temp_dir / "custom_target"
        artifacts_dir = temp_dir / "artifacts"
        
        ctx = MockExecutionContext(
            correlation_id="TEST-009",
            skill_name="node-scaffold",
            inputs={
                "correlation_id": "TEST-009",
                "node_schema": sample_node_schema,
                "normalized_name": "testService",
                "target_dir": str(target_dir),
            },
            artifacts_dir=artifacts_dir,
        )
        
        result = execute_node_scaffold(ctx)
        
        # Files should be in custom target
        assert any(str(target_dir) in f for f in result["files_created"])

    def test_logs_events(self, temp_dir, sample_node_schema):
        """Test that execution logs events to context trace."""
        ctx = MockExecutionContext(
            correlation_id="TEST-010",
            skill_name="node-scaffold",
            inputs={
                "correlation_id": "TEST-010",
                "node_schema": sample_node_schema,
                "normalized_name": "testService",
            },
            artifacts_dir=temp_dir / "artifacts",
        )
        
        execute_node_scaffold(ctx)
        
        # Should have logged events
        event_types = [e["event"] for e in ctx.trace]
        assert "scaffold_config" in event_types
        assert "file_created" in event_types
        assert "artifact_created" in event_types


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestNodeScaffoldIntegration:
    """Integration tests with executor framework."""

    def test_executor_can_load_implementation(self, temp_dir):
        """Test that executor can dynamically load the implementation."""
        from runtime.executor import SkillExecutor, SkillRegistry
        
        repo_root = Path(__file__).parent.parent
        
        executor = SkillExecutor(
            skills_dir=repo_root / "skills",
            scripts_dir=repo_root / "scripts",
            artifacts_dir=temp_dir,
        )
        
        # Register implementation manually for this test
        executor.register_implementation("node-scaffold", execute_node_scaffold)
        
        assert "node-scaffold" in executor._implementations

    def test_create_executor_registers_implementation(self, temp_dir):
        """Test that create_executor registers node-scaffold implementation."""
        from runtime.executor import create_executor
        
        repo_root = Path(__file__).parent.parent
        
        # Patch artifacts_dir for test
        executor = create_executor(repo_root, register_implementations=True)
        
        # Should have node-scaffold registered
        assert "node-scaffold" in executor._implementations
