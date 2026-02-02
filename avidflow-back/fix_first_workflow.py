#!/usr/bin/env python3
"""
Fix the first Local GPT workflow with correct OpenWebUI parameters.
This updates the workflow that's still using basic auth + wrong endpoint.
"""

import requests
import sys

# Configuration
WORKFLOW_ID = "4f452bd8-6866-415a-a2ea-632a58bb5e24"  # Your workflow ID
API_BASE = "http://localhost:8000"
JWT_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI0YTM4M2RkZS0yZGIxLTQ3ZGEtYWM3Zi1jNmJjZDRmYTA2MWYiLCJleHAiOjE3Njk1MTE3MjIsInR5cGUiOiJhY2Nlc3MiLCJqdGkiOiJiNWZhMjZmZDU2NjUyZDg4In0.AW9qk2VSXS6Z0yMTSSP42XQj4MEAbXc74_uyCAc26x4"

def main():
    print("🔧 Fixing Local GPT workflow parameters...")
    print()
    
    headers = {"Authorization": f"Bearer {JWT_TOKEN}"}
    
    # Get current workflow
    print(f"📥 Fetching workflow {WORKFLOW_ID}...")
    try:
        response = requests.get(
            f"{API_BASE}/api/workflows/{WORKFLOW_ID}",
            headers=headers
        )
        response.raise_for_status()
        workflow = response.json()
        print("✅ Workflow fetched")
    except Exception as e:
        print(f"❌ Failed to fetch workflow: {e}")
        sys.exit(1)
    
    # Find and update Local GPT nodes
    print("\n🔧 Updating Local GPT node parameters...")
    updated = False
    
    for node in workflow.get("nodes", []):
        if node.get("type") == "localGpt":
            print(f"   Found node: {node.get('name', 'Unnamed')}")
            
            if "parameters" not in node:
                node["parameters"] = {}
            
            params = node["parameters"]
            
            # Show current values
            print(f"   Current authType: {params.get('authType', 'not set')}")
            print(f"   Current endpointPath: {params.get('endpointPath', 'not set')}")
            print(f"   Current loginEndpoint: {params.get('loginEndpoint', 'not set')}")
            
            # Update to correct values
            params["authType"] = "bearer"
            params["endpointPath"] = "/api/chat/completions"
            params["loginEndpoint"] = "/api/v1/auths/signin"
            
            print(f"   ✅ Updated authType → bearer")
            print(f"   ✅ Updated endpointPath → /api/chat/completions")
            print(f"   ✅ Updated loginEndpoint → /api/v1/auths/signin")
            
            updated = True
    
    if not updated:
        print("⚠️  No Local GPT nodes found")
        sys.exit(1)
    
    # Save updated workflow
    print("\n💾 Saving updated workflow...")
    try:
        response = requests.put(
            f"{API_BASE}/api/workflows/{WORKFLOW_ID}",
            headers=headers,
            json=workflow
        )
        response.raise_for_status()
        print("✅ Workflow updated successfully!")
        
        print("\n" + "="*60)
        print("✨ Your workflow is now fixed!")
        print("   - Authentication: Bearer token ✅")
        print("   - Endpoint: /api/chat/completions ✅")
        print("   - Login: /api/v1/auths/signin ✅")
        print("="*60)
        print("\n🚀 Run the workflow again - it will work now!")
        
    except Exception as e:
        print(f"❌ Failed to update workflow: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"   Response: {e.response.text}")
        sys.exit(1)

if __name__ == "__main__":
    main()
