#!/usr/bin/env python3
"""
Mock credential provisioning test (no real API calls).

This demonstrates the credential-provision skill workflow without requiring actual tokens.
"""
import json
import sys
from pathlib import Path


def test_mock_provision():
    """Test credential provisioning with mock data."""
    print("=" * 70)
    print("GitHub Credential Provisioning Test (MOCK MODE)")
    print("=" * 70)
    
    # Load provision request
    request_file = Path(__file__).parent / "credential_provision_request.json"
    with open(request_file) as f:
        provision_request = json.load(f)
    
    print(f"\n📋 Provision Request:")
    print(f"  Correlation ID: {provision_request['correlation_id']}")
    print(f"  Credential Type: {provision_request['credential_type']}")
    print(f"  Credential Name: {provision_request['credential_name']}")
    
    # Mock resolved data (simulating env var resolution)
    print(f"\n🔧 Resolving credential data (MOCK)...")
    resolved_data = {
        "server": "https://api.github.com",
        "user": "testuser",
        "accessToken": "ghp_mock_token_for_testing_123456789"
    }
    print(f"  ✓ server: {resolved_data['server']}")
    print(f"  ✓ user: {resolved_data['user']}")
    print(f"  ✓ accessToken: {resolved_data['accessToken'][:15]}...")
    
    # Load credential class
    print(f"\n🧪 Testing credential (MOCK)...")
    sys.path.insert(0, "/home/toni/n8n/back")
    from credentials.githubApi import GithubApiCredential
    
    # Create instance
    cred = GithubApiCredential(resolved_data)
    print(f"  ✓ Credential instance created")
    
    # Validate
    validation = cred.validate()
    if validation["valid"]:
        print(f"  ✓ Validation passed")
    else:
        print(f"  ❌ Validation failed: {validation['message']}")
        return False
    
    # Mock test result (simulating successful API call)
    print(f"  🌐 Simulating API test...")
    mock_test_result = {
        "success": True,
        "message": "Successfully connected to GitHub as testuser (MOCK)",
        "data": {
            "user_id": 12345,
            "username": "testuser",
            "name": "Test User",
            "email": "test@example.com",
            "server": "https://api.github.com"
        }
    }
    print(f"  ✅ Credential test PASSED (MOCK)!")
    print(f"     User: {mock_test_result['data']['username']}")
    print(f"     User ID: {mock_test_result['data']['user_id']}")
    
    # Simulate provisioning
    print(f"\n📝 Simulating credential provisioning...")
    
    provisioned_credential = {
        "id": "cred_github_test_001",
        "correlation_id": provision_request['correlation_id'],
        "credential_type": provision_request['credential_type'],
        "credential_name": provision_request['credential_name'],
        "credential_data": {
            "server": "https://api.github.com",
            "user": "testuser",
            "accessToken": "***REDACTED***"
        },
        "test_result": {
            "success": True,
            "tested_at": "2026-01-06T15:45:00Z",
            "mode": "mock"
        },
        "status": "provisioned"
    }
    
    # Save artifact
    output_file = Path(__file__).parent / "credentials_provisioned_mock.json"
    with open(output_file, 'w') as f:
        json.dump(provisioned_credential, f, indent=2)
    
    print(f"  ✓ Credential provisioned (MOCK)")
    print(f"  ✓ Artifact saved: {output_file.name}")
    
    # Verify helper methods work
    print(f"\n🔍 Testing helper methods...")
    headers = cred.get_auth_headers()
    print(f"  ✓ get_auth_headers(): {list(headers.keys())}")
    
    server_url = cred.get_server_url()
    print(f"  ✓ get_server_url(): {server_url}")
    
    api_url = cred.get_api_url("/repos/owner/repo")
    print(f"  ✓ get_api_url('/repos/owner/repo'): {api_url}")
    
    print(f"\n" + "=" * 70)
    print(f"✅ Mock credential provisioning test COMPLETED!")
    print(f"   Ready for real provisioning with actual GITHUB_TOKEN")
    print(f"=" * 70)
    
    return True


if __name__ == "__main__":
    try:
        success = test_mock_provision()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
