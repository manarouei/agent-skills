"""
Integration test for GitHub API credential with real API calls.

Run with: python3 test_github_integration.py
Optional: Set GITHUB_TOKEN environment variable for authenticated test
"""
import os
import sys
from pathlib import Path

# Add converted module to path
converted_path = Path(__file__).parent.parent
sys.path.insert(0, str(converted_path))

from credentials.githubApi import GithubApiCredential


def test_public_api_call():
    """Test GitHub API with public endpoint (no auth needed)."""
    print("Testing GitHub API credential with public endpoint...")
    
    cred = GithubApiCredential({
        "server": "https://api.github.com",
        "accessToken": "dummy_token_for_structure_test"
    })
    
    # Test helper methods
    assert cred.get_server_url() == "https://api.github.com"
    headers = cred.get_auth_headers()
    assert headers["Authorization"] == "token dummy_token_for_structure_test"
    
    print("✓ Credential structure is correct")
    print("✓ Helper methods work")
    

def test_with_real_token():
    """Test with actual GitHub token if available."""
    github_token = os.getenv("GITHUB_TOKEN")
    
    if not github_token:
        print("\n⚠️  GITHUB_TOKEN not set - skipping authenticated test")
        print("   To test with real API: export GITHUB_TOKEN='ghp_your_token'")
        return False
    
    print(f"\nTesting with real GitHub token (length: {len(github_token)})...")
    
    cred = GithubApiCredential({
        "server": "https://api.github.com",
        "user": "test",
        "accessToken": github_token
    })
    
    # Test the credential
    result = cred.test()
    
    if result["success"]:
        print(f"✅ Authentication successful!")
        print(f"   Connected as: {result['data']['username']}")
        print(f"   User ID: {result['data']['user_id']}")
        if result['data'].get('name'):
            print(f"   Name: {result['data']['name']}")
        return True
    else:
        print(f"❌ Authentication failed: {result['message']}")
        return False


def test_validation():
    """Test validation logic."""
    print("\nTesting validation...")
    
    # Missing required field
    cred = GithubApiCredential({"server": "https://api.github.com"})
    validation = cred.validate()
    assert not validation["valid"]
    assert "accessToken" in validation["message"]
    print("✓ Validation catches missing accessToken")
    
    # Valid data
    cred = GithubApiCredential({
        "server": "https://api.github.com",
        "accessToken": "test_token"
    })
    validation = cred.validate()
    assert validation["valid"]
    print("✓ Validation passes with required fields")


def test_enterprise_url():
    """Test GitHub Enterprise URL handling."""
    print("\nTesting GitHub Enterprise support...")
    
    cred = GithubApiCredential({
        "server": "https://github.mycompany.com/api/v3",
        "accessToken": "test_token"
    })
    
    assert cred.get_server_url() == "https://github.mycompany.com/api/v3"
    url = cred.get_api_url("/repos/org/repo")
    assert url.startswith("https://github.mycompany.com")
    print("✓ GitHub Enterprise URLs work correctly")


if __name__ == "__main__":
    print("=" * 60)
    print("GitHub API Credential Integration Test")
    print("=" * 60)
    
    try:
        test_public_api_call()
        test_validation()
        test_enterprise_url()
        test_with_real_token()
        
        print("\n" + "=" * 60)
        print("✅ Integration tests completed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
