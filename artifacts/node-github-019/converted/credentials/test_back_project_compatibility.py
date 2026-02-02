"""
Test GitHub credential with actual back project BaseCredential.

This ensures our generated credential is compatible with the real platform.
"""
import sys
from pathlib import Path

# Add back project credentials to path
back_credentials_path = Path("/home/toni/n8n/back/credentials")
if back_credentials_path.exists():
    sys.path.insert(0, str(back_credentials_path.parent))
    print(f"✓ Added back project to path: {back_credentials_path.parent}")
else:
    print(f"❌ Back project not found at: {back_credentials_path}")
    sys.exit(1)

# Import from back project
try:
    from credentials.base import BaseCredential
    print("✓ Imported BaseCredential from back project")
except ImportError as e:
    print(f"❌ Failed to import BaseCredential: {e}")
    sys.exit(1)

# Import our generated credential (uses same base)
sys.path.insert(0, str(Path(__file__).parent.parent))
from credentials.githubApi import GithubApiCredential


def test_inheritance():
    """Test that GithubApiCredential properly inherits from back project's BaseCredential."""
    print("\nTesting inheritance...")
    
    # Check class hierarchy
    assert issubclass(GithubApiCredential, BaseCredential)
    print("✓ GithubApiCredential inherits from BaseCredential")
    
    # Check class attributes
    assert hasattr(GithubApiCredential, 'name')
    assert hasattr(GithubApiCredential, 'display_name')
    assert hasattr(GithubApiCredential, 'properties')
    print("✓ Required class attributes present")


def test_instantiation():
    """Test creating instance with back project's BaseCredential."""
    print("\nTesting instantiation...")
    
    cred_data = {
        "server": "https://api.github.com",
        "user": "testuser",
        "accessToken": "ghp_test123"
    }
    
    cred = GithubApiCredential(cred_data, client_id="test-client")
    
    # Check instance attributes
    assert cred.data == cred_data
    assert cred.client_id == "test-client"
    print("✓ Instance created successfully")
    print(f"  - data: {len(cred.data)} fields")
    print(f"  - client_id: {cred.client_id}")


def test_base_methods():
    """Test base class methods work."""
    print("\nTesting base class methods...")
    
    cred = GithubApiCredential({
        "server": "https://api.github.com",
        "accessToken": "ghp_test123"
    })
    
    # Test validate() from base class
    validation = cred.validate()
    assert validation["valid"]
    print("✓ validate() works")
    
    # Test get_definition() from base class
    definition = GithubApiCredential.get_definition()
    assert definition["name"] == "githubApi"
    assert definition["display_name"] == "GitHub API"
    assert len(definition["properties"]) == 3
    print("✓ get_definition() works")
    print(f"  - name: {definition['name']}")
    print(f"  - display_name: {definition['display_name']}")
    print(f"  - properties: {len(definition['properties'])} fields")


def test_custom_methods():
    """Test custom methods specific to GitHub credential."""
    print("\nTesting custom methods...")
    
    cred = GithubApiCredential({
        "server": "https://api.github.com",
        "accessToken": "ghp_test123"
    })
    
    # Test test() method
    result = cred.test()
    assert "success" in result
    assert "message" in result
    print("✓ test() method structure correct")
    
    # Test helper methods
    headers = cred.get_auth_headers()
    assert "Authorization" in headers
    print("✓ get_auth_headers() works")
    
    url = cred.get_server_url()
    assert url == "https://api.github.com"
    print("✓ get_server_url() works")
    
    api_url = cred.get_api_url("/repos/owner/repo")
    assert "/repos/owner/repo" in api_url
    print("✓ get_api_url() works")


def test_properties_format():
    """Test that properties match back project format."""
    print("\nTesting properties format...")
    
    for prop in GithubApiCredential.properties:
        # Each property should be a dict
        assert isinstance(prop, dict)
        
        # Required fields
        assert "name" in prop
        assert "displayName" in prop
        assert "type" in prop
        
        # Check types
        assert isinstance(prop["name"], str)
        assert isinstance(prop["displayName"], str)
        assert isinstance(prop["type"], str)
        
    print(f"✓ All {len(GithubApiCredential.properties)} properties are properly formatted")


if __name__ == "__main__":
    print("=" * 60)
    print("GitHub Credential vs Back Project Compatibility Test")
    print("=" * 60)
    
    try:
        test_inheritance()
        test_instantiation()
        test_base_methods()
        test_custom_methods()
        test_properties_format()
        
        print("\n" + "=" * 60)
        print("✅ All compatibility tests passed!")
        print("   Credential is compatible with back project!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
