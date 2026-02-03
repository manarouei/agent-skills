#!/usr/bin/env python3
"""
Tests for Behavioral Validation Gates

Tests the four behavioral validation gates:
1. NO-STUB GATE: Reject TODO/placeholder/NotImplementedError patterns
2. HTTP PARITY GATE: Verify HTTP calls match golden implementation
3. SEMANTIC DIFF GATE: Compare AST structure with golden
4. CONTRACT ROUND-TRIP GATE: Verify contract -> code -> contract cycle

These tests use the GitHub node as the canonical example:
- Golden: avidflow-back/nodes/github.py (1469 lines, real implementation)
- Broken: artifacts/github-final-test-006/converted_node/github.py (stub-filled)
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import via importlib since skill dirs have hyphens
import importlib.util

skill_impl = PROJECT_ROOT / "skills" / "behavioral-validate" / "impl.py"
spec = importlib.util.spec_from_file_location("behavioral_validate_impl", skill_impl)
behavioral_validate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(behavioral_validate)

validate_no_stubs = behavioral_validate.validate_no_stubs
validate_http_parity = behavioral_validate.validate_http_parity
validate_semantic_diff = behavioral_validate.validate_semantic_diff
validate_contract_roundtrip = behavioral_validate.validate_contract_roundtrip


# =============================================================================
# TEST FIXTURES
# =============================================================================

GOOD_HANDLER_CODE = '''
def _list_repos(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
    """List repositories for a user."""
    owner = self.get_node_parameter("owner", item_index)
    
    response = self._api_request(
        "GET",
        f"/users/{quote(owner, safe='')}/repos",
        query={"per_page": 100}
    )
    
    return {"json": response}
'''

STUB_HANDLER_CODE = '''
def _list_repos(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
    """List repositories for a user."""
    # TODO: Implement API call
    response = {}
    return {"json": response}
'''

NOTIMPL_HANDLER_CODE = '''
def _list_repos(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
    """List repositories for a user."""
    raise NotImplementedError("list_repos operation not implemented")
'''

PASS_ONLY_HANDLER_CODE = '''
def _list_repos(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
    """List repositories for a user."""
    pass
'''

EMPTY_RESPONSE_CODE = '''
def _list_repos(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
    """List repositories for a user."""
    owner = self.get_node_parameter("owner", item_index)
    response = {}
    return {"json": response}
'''

GOLDEN_HTTP_CODE = '''
class GitHubNode:
    def _list_repos(self):
        credentials = self.get_credentials("githubApi")
        headers = {"Authorization": f"Bearer {credentials['accessToken']}"}
        response = requests.get(
            f"https://api.github.com/users/{owner}/repos",
            headers=headers,
            timeout=30
        )
        return response.json()
        
    def _create_issue(self):
        response = requests.post(
            f"https://api.github.com/repos/{owner}/{repo}/issues",
            json=body,
            headers=headers,
            timeout=30
        )
        return response.json()
'''

GENERATED_HTTP_CODE_GOOD = '''
class GitHubNode:
    def _list_repos(self):
        credentials = self.get_credentials("githubApi")
        headers = {"Authorization": f"Bearer {credentials['accessToken']}"}
        response = requests.get(
            f"https://api.github.com/users/{owner}/repos",
            headers=headers,
            timeout=30
        )
        return response.json()
        
    def _create_issue(self):
        response = requests.post(
            f"https://api.github.com/repos/{owner}/{repo}/issues",
            json=body,
            headers=headers,
            timeout=30
        )
        return response.json()
'''

GENERATED_HTTP_CODE_MISSING = '''
class GitHubNode:
    def _list_repos(self):
        # No actual HTTP call
        return {"data": []}
        
    def _create_issue(self):
        pass
'''


# =============================================================================
# GATE 1: NO-STUB TESTS
# =============================================================================

class TestNoStubGate:
    """Tests for the no-stub validation gate."""
    
    def test_good_handler_passes(self):
        """Handler with real implementation should pass."""
        result = validate_no_stubs(GOOD_HANDLER_CODE)
        assert result.passed, f"Should pass but got violations: {result.violations}"
    
    def test_todo_comment_fails(self):
        """Handler with TODO comment should fail."""
        result = validate_no_stubs(STUB_HANDLER_CODE)
        assert not result.passed
        assert any("TODO" in v for v in result.violations)
    
    def test_notimplementederror_fails(self):
        """Handler raising NotImplementedError should fail."""
        result = validate_no_stubs(NOTIMPL_HANDLER_CODE)
        assert not result.passed
        assert any("NotImplementedError" in v for v in result.violations)
    
    def test_pass_only_fails(self):
        """Handler with only 'pass' should fail."""
        result = validate_no_stubs(PASS_ONLY_HANDLER_CODE)
        assert not result.passed
        assert any("pass" in v.lower() for v in result.violations)
    
    def test_empty_response_fails(self):
        """Handler with empty response dict should fail."""
        result = validate_no_stubs(EMPTY_RESPONSE_CODE)
        assert not result.passed
        assert any("empty" in v.lower() or "response = {}" in v.lower() for v in result.violations)
    
    def test_multiple_violations(self):
        """Code with multiple stub patterns should report all."""
        code_with_multiple = '''
def _handler1(self):
    # TODO: Implement this
    pass

def _handler2(self):
    raise NotImplementedError("not done")

def _handler3(self):
    response = {}
    return response
'''
        result = validate_no_stubs(code_with_multiple)
        assert not result.passed
        # Should have multiple violations
        assert len(result.violations) >= 3


# =============================================================================
# GATE 2: HTTP PARITY TESTS
# =============================================================================

class TestHttpParityGate:
    """Tests for the HTTP parity validation gate."""
    
    def test_matching_http_calls_passes(self):
        """Code with same HTTP patterns should pass."""
        result = validate_http_parity(GENERATED_HTTP_CODE_GOOD, GOLDEN_HTTP_CODE)
        assert result.passed, f"Should pass but got violations: {result.violations}"
    
    def test_missing_http_calls_fails(self):
        """Code without HTTP calls should fail."""
        result = validate_http_parity(GENERATED_HTTP_CODE_MISSING, GOLDEN_HTTP_CODE)
        assert not result.passed
        assert any("no HTTP calls" in v.lower() or "missing" in v.lower() for v in result.violations)
    
    def test_missing_auth_fails(self):
        """Code missing authentication pattern should fail."""
        code_no_auth = '''
class GitHubNode:
    def _list_repos(self):
        response = requests.get(
            f"https://api.github.com/users/{owner}/repos",
            timeout=30
        )
        return response.json()
'''
        result = validate_http_parity(code_no_auth, GOLDEN_HTTP_CODE)
        assert not result.passed
        assert any("authentication" in v.lower() or "authorization" in v.lower() for v in result.violations)
    
    def test_details_include_methods(self):
        """Result details should include HTTP methods found."""
        result = validate_http_parity(GENERATED_HTTP_CODE_GOOD, GOLDEN_HTTP_CODE)
        assert "generated_http_methods" in result.details
        assert "golden_http_methods" in result.details


# =============================================================================
# GATE 3: SEMANTIC DIFF TESTS
# =============================================================================

class TestSemanticDiffGate:
    """Tests for the semantic diff validation gate."""
    
    def test_matching_structure_passes(self):
        """Code with matching method structure should pass."""
        golden_methods = {
            "_list_repos": {"name": "_list_repos"},
            "_create_issue": {"name": "_create_issue"},
            "_get_repo": {"name": "_get_repo"},
        }
        code = '''
class GitHubNode:
    def _list_repos(self):
        return self._api_request("GET", "/repos")
    
    def _create_issue(self):
        return self._api_request("POST", "/issues")
    
    def _get_repo(self):
        return self._api_request("GET", "/repo")
'''
        result = validate_semantic_diff(code, golden_methods)
        assert result.passed, f"Should pass but got violations: {result.violations}"
    
    def test_missing_handlers_fails(self):
        """Code missing many handlers should fail."""
        golden_methods = {
            "_list_repos": {"name": "_list_repos"},
            "_create_issue": {"name": "_create_issue"},
            "_get_repo": {"name": "_get_repo"},
            "_update_repo": {"name": "_update_repo"},
            "_delete_repo": {"name": "_delete_repo"},
        }
        code = '''
class GitHubNode:
    def _list_repos(self):
        return {}
'''
        result = validate_semantic_diff(code, golden_methods)
        assert not result.passed
        assert any("missing" in v.lower() for v in result.violations)
    
    def test_diff_score_calculated(self):
        """Result should include diff score."""
        golden_methods = {"_handler1": {}, "_handler2": {}}
        code = '''
def _handler1():
    pass
def _handler2():
    pass
'''
        result = validate_semantic_diff(code, golden_methods)
        assert "diff_score" in result.details
        assert 0.0 <= result.details["diff_score"] <= 1.0


# =============================================================================
# GATE 4: CONTRACT ROUND-TRIP TESTS
# =============================================================================

class TestContractRoundtripGate:
    """Tests for the contract round-trip validation gate."""
    
    def test_all_operations_implemented_passes(self):
        """Code implementing all schema operations should pass."""
        schema = {
            "operations": [
                {"name": "list_repos", "value": "list_repos"},
                {"name": "create_issue", "value": "create_issue"},
            ]
        }
        code = '''
class GitHubNode:
    def _list_repos(self):
        return self._api_request("GET", "/repos")
    
    def _create_issue(self):
        return self._api_request("POST", "/issues")
'''
        result = validate_contract_roundtrip(code, schema)
        assert result.passed, f"Should pass but got violations: {result.violations}"
    
    def test_missing_operations_fails(self):
        """Code missing schema operations should fail."""
        schema = {
            "operations": [
                {"name": "list_repos", "value": "list_repos"},
                {"name": "create_issue", "value": "create_issue"},
                {"name": "delete_repo", "value": "delete_repo"},
            ]
        }
        code = '''
class GitHubNode:
    def _list_repos(self):
        return {}
'''
        result = validate_contract_roundtrip(code, schema)
        assert not result.passed
        assert any("create_issue" in str(v) or "delete_repo" in str(v) for v in result.violations)
    
    def test_details_include_unimplemented(self):
        """Result details should list unimplemented operations."""
        schema = {
            "operations": [
                {"name": "op1", "value": "op1"},
                {"name": "op2", "value": "op2"},
            ]
        }
        code = "class Node: pass"
        result = validate_contract_roundtrip(code, schema)
        assert "unimplemented_operations" in result.details


# =============================================================================
# INTEGRATION TESTS WITH REAL FILES
# =============================================================================

class TestRealGitHubNode:
    """Integration tests using real GitHub node files if available."""
    
    @pytest.fixture
    def golden_github_path(self):
        """Path to golden GitHub node."""
        path = PROJECT_ROOT / "avidflow-back" / "nodes" / "github.py"
        if not path.exists():
            pytest.skip("Golden GitHub node not found")
        return path
    
    @pytest.fixture
    def broken_github_path(self):
        """Path to broken GitHub node (from failed conversion)."""
        path = PROJECT_ROOT / "artifacts" / "github-final-test-006" / "converted_node" / "github.py"
        if not path.exists():
            pytest.skip("Broken GitHub node artifact not found")
        return path
    
    def test_golden_passes_no_stub(self, golden_github_path):
        """Golden implementation should pass no-stub gate."""
        code = golden_github_path.read_text()
        result = validate_no_stubs(code)
        assert result.passed, f"Golden should pass but got: {result.violations}"
    
    def test_broken_fails_no_stub(self, broken_github_path):
        """Broken implementation should fail no-stub gate."""
        code = broken_github_path.read_text()
        result = validate_no_stubs(code)
        # If this passes, the broken file might have been fixed
        if result.passed:
            pytest.skip("Broken GitHub node has been fixed (no stubs found)")
        assert not result.passed
        assert len(result.violations) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
