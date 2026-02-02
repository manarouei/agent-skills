#!/usr/bin/env python3
"""
Unit tests for node-validate skill - New Pipeline Safety Gates

Tests the new validation checks that ensure the pipeline cannot
"greenlight" broken nodes:

1. NotImplementedError rejection
2. Placeholder URL rejection (api.example.com, /endpoint)
3. Resource dispatch correctness
4. continue_on_fail pattern validation
5. Duplicate methods detection
"""

import ast
import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the implementation module dynamically (hyphenated directory)
import importlib.util
impl_path = Path(__file__).parent.parent / "skills" / "node-validate" / "impl.py"
spec = importlib.util.spec_from_file_location("node_validate_impl", impl_path)
node_validate_impl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(node_validate_impl)

# Import functions for testing
_check_not_implemented = node_validate_impl._check_not_implemented
_check_placeholder_urls = node_validate_impl._check_placeholder_urls
_check_resource_dispatch = node_validate_impl._check_resource_dispatch
_check_continue_on_fail = node_validate_impl._check_continue_on_fail
_check_duplicate_methods = node_validate_impl._check_duplicate_methods


@pytest.fixture
def temp_dir():
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# TEST: NotImplementedError Rejection
# =============================================================================

class TestNotImplementedRejection:
    """Tests for _check_not_implemented validation."""
    
    def test_rejects_raise_notimplementederror(self, temp_dir):
        """Validation must fail if NotImplementedError is raised."""
        code = '''
class TestNode:
    def _operation(self):
        raise NotImplementedError("operation not implemented")
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        tree = ast.parse(code)
        
        passed, details, lines = _check_not_implemented(tree, py_file)
        
        assert not passed, "Should reject NotImplementedError"
        assert "NotImplementedError" in details
        assert len(lines) > 0
    
    def test_rejects_todo_implement_marker(self, temp_dir):
        """Validation must fail if TODO: Implement marker exists."""
        code = '''
class TestNode:
    def _operation(self):
        # TODO: Implement operation logic
        pass
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        tree = ast.parse(code)
        
        passed, details, lines = _check_not_implemented(tree, py_file)
        
        assert not passed, "Should reject TODO: Implement marker"
        assert "TODO" in details
    
    def test_accepts_implemented_operations(self, temp_dir):
        """Validation must pass if no NotImplementedError exists."""
        code = '''
class TestNode:
    def _operation(self):
        return {"result": "success"}
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        tree = ast.parse(code)
        
        passed, details, lines = _check_not_implemented(tree, py_file)
        
        assert passed, f"Should accept implemented operations: {details}"


# =============================================================================
# TEST: Placeholder URL Rejection
# =============================================================================

class TestPlaceholderUrlRejection:
    """Tests for _check_placeholder_urls validation."""
    
    def test_rejects_api_example_com(self, temp_dir):
        """Validation must fail if api.example.com exists."""
        code = '''
class TestNode:
    def _api_request(self):
        url = f"https://api.example.com/endpoint"
        return url
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        
        passed, details, lines = _check_placeholder_urls(py_file)
        
        assert not passed, "Should reject api.example.com"
        assert "api.example.com" in details.lower() or "placeholder" in details.lower()
    
    def test_rejects_endpoint_placeholder(self, temp_dir):
        """Validation must fail if '/endpoint' placeholder exists."""
        code = '''
class TestNode:
    def _api_request(self):
        response = self._request("GET", "/endpoint")
        return response
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        
        passed, details, lines = _check_placeholder_urls(py_file)
        
        assert not passed, "Should reject /endpoint placeholder"
    
    def test_accepts_real_api_urls(self, temp_dir):
        """Validation must pass with real API URLs."""
        code = '''
class TestNode:
    BASE_URL = "https://discord.com/api/v10"
    
    def _api_request(self, endpoint: str):
        url = f"{self.BASE_URL}{endpoint}"
        return url
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        
        passed, details, lines = _check_placeholder_urls(py_file)
        
        assert passed, f"Should accept real API URLs: {details}"


# =============================================================================
# TEST: Resource Dispatch Validation
# =============================================================================

class TestResourceDispatchValidation:
    """Tests for _check_resource_dispatch validation."""
    
    def test_rejects_operation_only_dispatch_with_resource_param(self, temp_dir):
        """Validation must fail if resource param exists but execute() only reads operation."""
        code = '''
class TestNode:
    properties = {
        "parameters": [
            {"name": "resource", "type": "options"},
            {"name": "operation", "type": "options"}
        ]
    }
    
    def execute(self):
        for i, item in enumerate(input_data):
            operation = self.get_node_parameter("operation", i)
            if operation == "get":
                result = self._get(i, item)
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        tree = ast.parse(code)
        
        passed, details = _check_resource_dispatch(tree, py_file)
        
        assert not passed, "Should reject operation-only dispatch when resource param exists"
        assert "resource" in details.lower()
    
    def test_accepts_resource_operation_dispatch(self, temp_dir):
        """Validation must pass if both resource and operation are read."""
        code = '''
class TestNode:
    properties = {
        "parameters": [
            {"name": "resource", "type": "options"},
            {"name": "operation", "type": "options"}
        ]
    }
    
    def execute(self):
        for i, item in enumerate(input_data):
            resource = self.get_node_parameter("resource", i)
            operation = self.get_node_parameter("operation", i)
            if resource == "channel" and operation == "get":
                result = self._channel_get(i, item)
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        tree = ast.parse(code)
        
        passed, details = _check_resource_dispatch(tree, py_file)
        
        assert passed, f"Should accept resource+operation dispatch: {details}"
    
    def test_skips_single_resource_nodes(self, temp_dir):
        """Validation must skip nodes without resource parameter."""
        code = '''
class TestNode:
    properties = {
        "parameters": [
            {"name": "operation", "type": "options"}
        ]
    }
    
    def execute(self):
        for i, item in enumerate(input_data):
            operation = self.get_node_parameter("operation", i)
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        tree = ast.parse(code)
        
        passed, details = _check_resource_dispatch(tree, py_file)
        
        assert passed, f"Should skip single-resource nodes: {details}"


# =============================================================================
# TEST: continue_on_fail Pattern Validation
# =============================================================================

class TestContinueOnFailValidation:
    """Tests for _check_continue_on_fail validation."""
    
    def test_rejects_self_continue_on_fail(self, temp_dir):
        """Validation must fail if self.continue_on_fail is used."""
        code = '''
class TestNode:
    def execute(self):
        try:
            result = self._operation()
        except Exception as e:
            if self.continue_on_fail:
                return {"error": str(e)}
            raise
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        
        passed, details, lines = _check_continue_on_fail(py_file)
        
        assert not passed, "Should reject self.continue_on_fail"
        assert "node_data" in details.lower() or "continue_on_fail" in details.lower()
    
    def test_accepts_node_data_continue_on_fail(self, temp_dir):
        """Validation must pass if self.node_data.continue_on_fail is used."""
        code = '''
class TestNode:
    def execute(self):
        try:
            result = self._operation()
        except Exception as e:
            if self.node_data.continue_on_fail:
                return {"error": str(e)}
            raise
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        
        passed, details, lines = _check_continue_on_fail(py_file)
        
        assert passed, f"Should accept self.node_data.continue_on_fail: {details}"
    
    def test_accepts_no_continue_on_fail(self, temp_dir):
        """Validation must pass if continue_on_fail is not used."""
        code = '''
class TestNode:
    def execute(self):
        result = self._operation()
        return result
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        
        passed, details, lines = _check_continue_on_fail(py_file)
        
        assert passed, f"Should accept when continue_on_fail not used: {details}"


# =============================================================================
# TEST: Duplicate Methods Detection
# =============================================================================

class TestDuplicateMethodsDetection:
    """Tests for _check_duplicate_methods validation."""
    
    def test_rejects_duplicate_methods(self, temp_dir):
        """Validation must fail if methods are defined multiple times."""
        code = '''
class TestNode:
    def _get(self, item_index):
        pass
    
    def _getAll(self, item_index):
        pass
    
    def _get(self, item_index):  # Duplicate!
        pass
    
    def _getAll(self, item_index):  # Duplicate!
        pass
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        tree = ast.parse(code)
        
        passed, details, duplicates = _check_duplicate_methods(tree)
        
        assert not passed, "Should reject duplicate methods"
        assert "_get" in duplicates or "_getAll" in duplicates
    
    def test_accepts_unique_methods(self, temp_dir):
        """Validation must pass if all methods are unique."""
        code = '''
class TestNode:
    def _channel_get(self, item_index):
        pass
    
    def _channel_getAll(self, item_index):
        pass
    
    def _message_get(self, item_index):
        pass
    
    def _message_getAll(self, item_index):
        pass
'''
        py_file = temp_dir / "test_node.py"
        py_file.write_text(code)
        tree = ast.parse(code)
        
        passed, details, duplicates = _check_duplicate_methods(tree)
        
        assert passed, f"Should accept unique methods: {details}"


# =============================================================================
# TEST: Current Discord Node Would FAIL Validation
# =============================================================================

class TestCurrentDiscordNodeFailsValidation:
    """
    These tests verify that the current generated discord.py would fail validation.
    This proves our guardrails work correctly.
    """
    
    @pytest.fixture
    def discord_node_path(self):
        """Path to the current generated discord.py."""
        return Path(__file__).parent.parent / "artifacts" / "node-discord-v2test-4001e842" / "converted" / "discord.py"
    
    def test_discord_fails_not_implemented_check(self, discord_node_path):
        """Current discord.py must fail NotImplementedError check."""
        if not discord_node_path.exists():
            pytest.skip("Discord artifact not available")
        
        content = discord_node_path.read_text()
        tree = ast.parse(content)
        
        passed, details, lines = _check_not_implemented(tree, discord_node_path)
        
        assert not passed, f"Discord node should fail NotImplementedError check: {details}"
        # Should find multiple NotImplementedError raises
        assert len(lines) >= 10, f"Expected many NotImplementedError, found {len(lines)}"
    
    def test_discord_fails_placeholder_url_check(self, discord_node_path):
        """Current discord.py must fail placeholder URL check."""
        if not discord_node_path.exists():
            pytest.skip("Discord artifact not available")
        
        passed, details, lines = _check_placeholder_urls(discord_node_path)
        
        assert not passed, f"Discord node should fail placeholder URL check: {details}"
    
    def test_discord_fails_resource_dispatch_check(self, discord_node_path):
        """Current discord.py must fail resource dispatch check."""
        if not discord_node_path.exists():
            pytest.skip("Discord artifact not available")
        
        content = discord_node_path.read_text()
        tree = ast.parse(content)
        
        passed, details = _check_resource_dispatch(tree, discord_node_path)
        
        assert not passed, f"Discord node should fail resource dispatch check: {details}"
    
    def test_discord_fails_continue_on_fail_check(self, discord_node_path):
        """Current discord.py must fail continue_on_fail check."""
        if not discord_node_path.exists():
            pytest.skip("Discord artifact not available")
        
        passed, details, lines = _check_continue_on_fail(discord_node_path)
        
        assert not passed, f"Discord node should fail continue_on_fail check: {details}"
    
    def test_discord_fails_duplicate_methods_check(self, discord_node_path):
        """Current discord.py must fail duplicate methods check."""
        if not discord_node_path.exists():
            pytest.skip("Discord artifact not available")
        
        content = discord_node_path.read_text()
        tree = ast.parse(content)
        
        passed, details, duplicates = _check_duplicate_methods(tree)
        
        assert not passed, f"Discord node should fail duplicate methods check: {details}"
        # Should find _get and _getAll defined multiple times
        assert "_get" in duplicates or "_getAll" in duplicates


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
