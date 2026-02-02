#!/usr/bin/env python3
"""
Test credential provisioning for GitHub API credential.

This script simulates what the credential-provision skill does:
1. Load credential definition
2. Resolve environment variables
3. Validate credential data
4. Create credential instance (simulated - would call platform API)
"""
import json
import os
import sys
from pathlib import Path

# Add agent-skills to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

def resolve_env_var(value: str) -> str:
    """Resolve environment variable placeholders like ${VAR} or ${VAR:-default}."""
    if not isinstance(value, str) or not value.startswith("${"):
        return value
    
    # Extract variable name and optional default
    if ":-" in value:
        var_name = value[2:value.index(":-")]
        default = value[value.index(":-")+2:-1]
    else:
        var_name = value[2:-1]
        default = None
    
    # Get from environment
    env_value = os.getenv(var_name)
    if env_value:
        return env_value
    elif default is not None:
        return default
    else:
        raise ValueError(f"Environment variable {var_name} not set and no default provided")


def resolve_credential_data(data: dict) -> dict:
    """Resolve all environment variables in credential data."""
    resolved = {}
    for key, value in data.items():
        if isinstance(value, str):
            resolved[key] = resolve_env_var(value)
        else:
            resolved[key] = value
    return resolved


def sanitize_credential(data: dict) -> dict:
    """Remove sensitive data for artifact storage."""
    sanitized = {}
    sensitive_fields = ["accessToken", "password", "token", "secret", "key"]
    
    for key, value in data.items():
        if any(field in key.lower() for field in sensitive_fields):
            sanitized[key] = "***REDACTED***"
        else:
            sanitized[key] = value
    
    return sanitized


def test_credential_provision():
    """Test GitHub credential provisioning."""
    print("=" * 70)
    print("GitHub Credential Provisioning Test")
    print("=" * 70)
    
    # Load provision request
    request_file = Path(__file__).parent / "credential_provision_request.json"
    with open(request_file) as f:
        provision_request = json.load(f)
    
    print(f"\n📋 Provision Request:")
    print(f"  Correlation ID: {provision_request['correlation_id']}")
    print(f"  Credential Type: {provision_request['credential_type']}")
    print(f"  Credential Name: {provision_request['credential_name']}")
    
    # Check environment variables
    print(f"\n🔍 Checking environment variables...")
    missing_vars = []
    for var_name, var_info in provision_request['environment_variables'].items():
        if var_info.get('required') and not os.getenv(var_name):
            missing_vars.append(var_name)
            print(f"  ❌ {var_name}: NOT SET (required)")
        else:
            value = os.getenv(var_name, "not set")
            masked_value = value[:10] + "..." if len(value) > 10 else value
            print(f"  ✓ {var_name}: {masked_value if value != 'not set' else value}")
    
    if missing_vars:
        print(f"\n⚠️  Missing required environment variables: {', '.join(missing_vars)}")
        print(f"  Set them with: export GITHUB_TOKEN='your_token'")
        return False
    
    # Resolve credential data
    print(f"\n🔧 Resolving credential data...")
    try:
        resolved_data = resolve_credential_data(provision_request['credential_data'])
        print(f"  ✓ All environment variables resolved")
        
        # Validate resolved data
        for key, value in resolved_data.items():
            if key == "accessToken":
                print(f"  ✓ {key}: {value[:10]}..." if value else f"  ❌ {key}: empty")
            else:
                print(f"  ✓ {key}: {value}")
    except ValueError as e:
        print(f"  ❌ Resolution failed: {e}")
        return False
    
    # Load and test credential
    print(f"\n🧪 Testing credential...")
    
    # Import credential class from back project
    sys.path.insert(0, "/home/toni/n8n/back")
    from credentials.githubApi import GithubApiCredential
    
    # Create credential instance
    cred = GithubApiCredential(resolved_data)
    
    # Validate
    validation = cred.validate()
    if not validation["valid"]:
        print(f"  ❌ Validation failed: {validation['message']}")
        return False
    print(f"  ✓ Validation passed")
    
    # Test credential (makes real API call)
    print(f"  🌐 Testing API connection...")
    test_result = cred.test()
    
    if test_result["success"]:
        print(f"  ✅ Credential test PASSED!")
        print(f"     Message: {test_result['message']}")
        if "data" in test_result:
            print(f"     User: {test_result['data'].get('username')}")
            print(f"     User ID: {test_result['data'].get('user_id')}")
    else:
        print(f"  ❌ Credential test FAILED!")
        print(f"     Message: {test_result['message']}")
        return False
    
    # Simulate provisioning (would call platform API in real scenario)
    print(f"\n📝 Simulating credential provisioning...")
    
    provisioned_credential = {
        "id": "cred_github_test_001",
        "correlation_id": provision_request['correlation_id'],
        "credential_type": provision_request['credential_type'],
        "credential_name": provision_request['credential_name'],
        "credential_data": sanitize_credential(resolved_data),
        "test_result": {
            "success": test_result["success"],
            "tested_at": "2026-01-06T15:45:00Z"
        },
        "status": "provisioned"
    }
    
    # Save provisioned credential artifact
    output_file = Path(__file__).parent / "credentials_provisioned.json"
    with open(output_file, 'w') as f:
        json.dump(provisioned_credential, f, indent=2)
    
    print(f"  ✓ Credential provisioned (simulated)")
    print(f"  ✓ Artifact saved: {output_file.name}")
    
    print(f"\n" + "=" * 70)
    print(f"✅ Credential provisioning test COMPLETED!")
    print(f"=" * 70)
    
    return True


if __name__ == "__main__":
    try:
        success = test_credential_provision()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
