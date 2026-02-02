"""
Tests for new node-validate rules that catch pipeline defects.

These tests prove that the validator rejects broken patterns
that the pipeline used to generate.
"""

import ast
import sys
import tempfile
from pathlib import Path

import pytest

# Import validation functions - directly import the impl module
# Use absolute path to avoid issues with module resolution
impl_path = Path("/home/toni/agent-skills/skills/node-validate/impl.py")

# Load impl module dynamically
import importlib.util
spec = importlib.util.spec_from_file_location("node_validate_impl", str(impl_path))
impl = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = impl
spec.loader.exec_module(impl)

_check_missing_helpers = impl._check_missing_helpers
_check_hardcoded_repos = impl._check_hardcoded_repos
_check_wrong_auth_scheme = impl._check_wrong_auth_scheme
_check_returnall_pagination = impl._check_returnall_pagination
_check_phantom_operations = impl._check_phantom_operations
_check_body_in_write_operations = impl._check_body_in_write_operations
_check_generic_credential_names = impl._check_generic_credential_names


class TestMissingHelpers:
    """Test detection of missing helper methods."""
    
    def test_rejects_missing_api_request_all_items(self, tmp_path):
        """Reject code that calls _api_request_all_items but doesn't define it."""
        code = """
class GithubNode:
    def execute(self):
        result = self._api_request_all_items("GET", "/repos")
        return result
"""
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        tree = ast.parse(code)
        passed, details, missing = _check_missing_helpers(tree, file_path)
        
        assert not passed
        assert "_api_request_all_items" in missing
        assert "Helper methods called but not defined" in details
    
    def test_passes_when_helper_defined(self, tmp_path):
        """Pass when helper is defined."""
        code = """
class GithubNode:
    def _api_request_all_items(self, method, endpoint):
        return []
    
    def execute(self):
        result = self._api_request_all_items("GET", "/repos")
        return result
"""
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        tree = ast.parse(code)
        passed, details, missing = _check_missing_helpers(tree, file_path)
        
        assert passed
        assert not missing


class TestHardcodedRepos:
    """Test detection of hardcoded repo names in URLs."""
    
    def test_rejects_test_owner_test_repo(self, tmp_path):
        """Reject /repos/test-owner/test-repo pattern."""
        code = '''
url = "https://api.github.com/repos/test-owner/test-repo/issues"
'''
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        passed, details, lines = _check_hardcoded_repos(file_path)
        
        assert not passed
        assert "test-owner/test-repo" in details
    
    def test_passes_with_variable_repos(self, tmp_path):
        """Pass when using variables for owner/repo."""
        code = '''
url = f"https://api.github.com/repos/{owner}/{repo}/issues"
'''
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        passed, details, lines = _check_hardcoded_repos(file_path)
        
        assert passed


class TestWrongAuthScheme:
    """Test detection of wrong authentication schemes."""
    
    def test_rejects_bot_prefix_for_github(self, tmp_path):
        """Reject 'Bot {token}' - should be 'Bearer {token}' for GitHub."""
        code = '''
headers = {"Authorization": f"Bot {token}"}
'''
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        passed, details, lines = _check_wrong_auth_scheme(file_path)
        
        assert not passed
        assert "Bot" in details
        assert "Bearer" in details
    
    def test_passes_with_bearer_auth(self, tmp_path):
        """Pass when using Bearer token."""
        code = '''
headers = {"Authorization": f"Bearer {token}"}
'''
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        passed, details, lines = _check_wrong_auth_scheme(file_path)
        
        assert passed


class TestReturnAllPagination:
    """Test that returnAll parameter requires pagination helper."""
    
    def test_rejects_returnall_without_helper(self, tmp_path):
        """Reject returnAll parameter without pagination helper."""
        code = '''
properties = {
    "parameters": [
        {"name": "returnAll", "type": "boolean"}
    ]
}

def execute(self):
    return_all = self.get_node_parameter("returnAll", 0)
    if return_all:
        # BUG: calls _api_request_all_items but it doesn't exist
        pass
'''
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        tree = ast.parse(code)
        passed, details, _ = _check_returnall_pagination(tree, file_path)
        
        assert not passed
        assert "returnAll" in details
        assert "pagination helper" in details.lower()
    
    def test_passes_with_pagination_helper(self, tmp_path):
        """Pass when returnAll has corresponding helper."""
        code = '''
properties = {
    "parameters": [
        {"name": "returnAll", "type": "boolean"}
    ]
}

def _api_request_all_items(self, method, endpoint):
    return []

def execute(self):
    return_all = self.get_node_parameter("returnAll", 0)
    if return_all:
        result = self._api_request_all_items("GET", "/items")
    return result
'''
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        tree = ast.parse(code)
        passed, details, _ = _check_returnall_pagination(tree, file_path)
        
        assert passed


class TestPhantomOperations:
    """Test detection of operations in UI but not implemented."""
    
    def test_rejects_dispatchandwait_not_implemented(self, tmp_path):
        """Reject dispatchAndWait in UI but not in execute()."""
        code = '''
properties = {
    "parameters": [
        {
            "name": "operation",
            "type": "options",
            "options": [
                {"name": "Dispatch", "value": "dispatch"},
                {"name": "Dispatch and Wait", "value": "dispatchAndWait"}
            ]
        }
    ]
}

def execute(self):
    operation = self.get_node_parameter("operation", 0)
    if operation == "dispatch":
        return self._dispatch()
    # BUG: dispatchAndWait not handled
'''
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        tree = ast.parse(code)
        passed, details, unimpl = _check_phantom_operations(tree, file_path)
        
        assert not passed
        assert "dispatchAndWait" in unimpl
    
    def test_passes_when_all_ops_implemented(self, tmp_path):
        """Pass when all operations are implemented."""
        code = '''
properties = {
    "parameters": [
        {
            "name": "operation",
            "type": "options",
            "options": [
                {"name": "Create", "value": "create"},
                {"name": "Get", "value": "get"}
            ]
        }
    ]
}

def execute(self):
    operation = self.get_node_parameter("operation", 0)
    if operation == "create":
        return self._create()
    elif operation == "get":
        return self._get()
'''
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        tree = ast.parse(code)
        passed, details, unimpl = _check_phantom_operations(tree, file_path)
        
        assert passed


class TestBodyInWriteOperations:
    """Test that POST/PUT/PATCH operations pass body parameter."""
    
    def test_rejects_post_with_body_none(self, tmp_path):
        """Reject POST operation with body=None."""
        code = '''
class GithubNode:
    def _api_request(self, method, endpoint, body=None, query=None):
        pass
    
    def _issue_create(self, item_index, item_data):
        # BUG: Extracts params but passes body=None
        title = self.get_node_parameter("title", item_index)
        response = self._api_request("POST", "/issues", body=None)
        return response
'''
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        tree = ast.parse(code)
        passed, details, lines = _check_body_in_write_operations(tree, file_path)
        
        assert not passed
        assert "body=None" in details or "body" in details.lower()
    
    def test_passes_when_body_provided(self, tmp_path):
        """Pass when write operation provides body."""
        code = '''
class GithubNode:
    def _api_request(self, method, endpoint, body=None, query=None):
        pass
    
    def _issue_create(self, item_index, item_data):
        title = self.get_node_parameter("title", item_index)
        body = {"title": title}
        response = self._api_request("POST", "/issues", body=body)
        return response
'''
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        tree = ast.parse(code)
        passed, details, lines = _check_body_in_write_operations(tree, file_path)
        
        assert passed


class TestGenericCredentialNames:
    """Test detection of generic credential names."""
    
    def test_rejects_oauth2_credential(self, tmp_path):
        """Reject generic 'oauth2' credential name."""
        code = '''
def _api_request(self, method, endpoint):
    credentials = self.get_credentials("oauth2")
    return credentials
'''
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        passed, details, lines = _check_generic_credential_names(file_path)
        
        assert not passed
        assert "oauth2" in details
        assert "service-specific" in details.lower()
    
    def test_passes_with_service_specific_credential(self, tmp_path):
        """Pass when using service-specific credential name."""
        code = '''
def _api_request(self, method, endpoint):
    credentials = self.get_credentials("githubApi")
    return credentials
'''
        file_path = tmp_path / "test.py"
        file_path.write_text(code)
        
        passed, details, lines = _check_generic_credential_names(file_path)
        
        assert passed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
