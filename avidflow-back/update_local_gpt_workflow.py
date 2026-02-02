#!/usr/bin/env python3
"""
Update the Local GPT workflow to use correct OpenWebUI parameters.
Run this script to fix the authentication type and endpoints.
"""

import requests
import json
import getpass

# Configuration
WORKFLOW_ID = "4f452bd8-6866-415a-a2ea-632a58bb5e24"
API_BASE = "http://localhost:8000"

def main():
    print("🔄 Updating Local GPT workflow parameters...")
    print()
    
    # Get JWT token
    token = input("Enter your JWT token: ").strip()
    
    if not token:
        print("❌ No token provided")
        return
    
    print("✅ Using provided JWT token")
    
    # Get current workflow
    print(f"\n📥 Fetching workflow {WORKFLOW_ID}...")
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        workflow_response = requests.get(
            f"{API_BASE}/api/workflows/{WORKFLOW_ID}",
            headers=headers
        )
        workflow_response.raise_for_status()
        workflow_data = workflow_response.json()
        print("✅ Workflow fetched")
    except Exception as e:
        print(f"❌ Failed to fetch workflow: {e}")
        return
    
    # Update the Local GPT node parameters
    print("\n🔧 Updating Local GPT node parameters...")
    updated = False
    
    for node in workflow_data.get("nodes", []):
        if node.get("type") == "localGpt":
            print(f"   Found node: {node.get('name', 'Unnamed')}")
            
            # Update parameters
            if "parameters" not in node:
                node["parameters"] = {}
            
            old_params = node["parameters"].copy()
            
            node["parameters"]["authType"] = "bearer"
            node["parameters"]["loginEndpoint"] = "/api/v1/auths/signin"
            node["parameters"]["endpointPath"] = "/api/chat/completions"
            
            print(f"   Changed authType: {old_params.get('authType', 'not set')} → bearer")
            print(f"   Changed loginEndpoint: {old_params.get('loginEndpoint', 'not set')} → /api/v1/auths/signin")
            print(f"   Changed endpointPath: {old_params.get('endpointPath', 'not set')} → /api/chat/completions")
            
            updated = True
    
    if not updated:
        print("⚠️  No Local GPT nodes found in workflow")
        return
    
    # Save the updated workflow
    print("\n💾 Saving updated workflow...")
    try:
        update_response = requests.put(
            f"{API_BASE}/api/workflows/{WORKFLOW_ID}",
            headers=headers,
            json=workflow_data
        )
        update_response.raise_for_status()
        print("✅ Workflow updated successfully!")
        
        print("\n" + "="*60)
        print("✨ Workflow is now configured for OpenWebUI:")
        print("   - Authentication: Bearer token via /api/v1/auths/signin")
        print("   - Endpoint: /api/chat/completions")
        print("   - Model: gpt-oss:120b")
        print("="*60)
        print("\n🚀 You can now run the workflow - it should work!")
        
    except Exception as e:
        print(f"❌ Failed to update workflow: {e}")
        if hasattr(e, 'response'):
            print(f"   Response: {e.response.text}")

if __name__ == "__main__":
    main()
