"""
Test GitHub API credential implementation.

Tests:
- Credential definition
- Validation logic
- Test method structure
- Helper methods
"""
import sys
from pathlib import Path

# Add converted module to path
converted_path = Path(__file__).parent.parent
sys.path.insert(0, str(converted_path))

from credentials.githubApi import GithubApiCredential
from credentials.base import BaseCredential


def test_credential_definition():
    """Test that credential has proper definition."""
    assert GithubApiCredential.name == "githubApi"
    assert GithubApiCredential.display_name == "GitHub API"
    assert len(GithubApiCredential.properties) == 3
    
    # Check property names
    prop_names = [p["name"] for p in GithubApiCredential.properties]
    assert "server" in prop_names
    assert "user" in prop_names
    assert "accessToken" in prop_names
    
    print("✓ Credential definition valid")


def test_validation():
    """Test validation logic."""
    # Missing required field
    cred = GithubApiCredential({"server": "https://api.github.com"})
    validation = cred.validate()
    assert not validation["valid"]
    assert "accessToken" in validation["message"]
    
    # Valid credential data
    cred = GithubApiCredential({
        "server": "https://api.github.com",
        "accessToken": "ghp_test123"
    })
    validation = cred.validate()
    assert validation["valid"]
    
    print("✓ Validation logic works")


def test_helper_methods():
    """Test helper methods."""
    cred = GithubApiCredential({
        "server": "https://api.github.com",
        "user": "testuser",
        "accessToken": "ghp_test123"
    })
    
    # Test get_server_url
    assert cred.get_server_url() == "https://api.github.com"
    
    # Test get_auth_headers
    headers = cred.get_auth_headers()
    assert "Authorization" in headers
    assert headers["Authorization"] == "token ghp_test123"
    assert headers["Accept"] == "application/vnd.github.v3+json"
    
    # Test get_api_url
    url = cred.get_api_url("/repos/owner/repo")
    assert url == "https://api.github.com/repos/owner/repo"
    
    print("✓ Helper methods work")


def test_get_definition():
    """Test class method for definition."""
    definition = GithubApiCredential.get_definition()
    assert definition["name"] == "githubApi"
    assert definition["display_name"] == "GitHub API"
    assert len(definition["properties"]) == 3
    
    print("✓ get_definition() works")


def test_test_method_structure():
    """Test that test method has proper structure (without actual HTTP call)."""
    cred = GithubApiCredential({
        "server": "https://api.github.com",
        "accessToken": ""
    })
    
    # Test with missing token
    result = cred.test()
    assert "success" in result
    assert not result["success"]
    assert "message" in result
    
    print("✓ Test method structure valid")


if __name__ == "__main__":
    print("Testing GitHub API Credential Implementation\n")
    test_credential_definition()
    test_validation()
    test_helper_methods()
    test_get_definition()
    test_test_method_structure()
    print("\n✅ All tests passed!")
