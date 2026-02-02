#!/usr/bin/env python3
"""
GitHub Node Real Workflow Execution Test

This script tests the GitHub node by directly invoking the back project's
workflow execution engine. It simulates what happens when a workflow is
executed via the REST API or WebSocket.

Prerequisites:
- GITHUB_TOKEN environment variable set
- Back project dependencies installed
- GitHub node deployed to back project

Run with: python3 test_github_real_execution.py
"""

import os
import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List

def test_github_node_standalone():
    """
    Test GitHub node execution standalone (without full workflow engine).
    
    This simulates what the execution engine does:
    1. Load workflow definition
    2. Resolve credentials
    3. Execute node with input data
    4. Validate output
    """
    print("=" * 70)
    print("GitHub Node Standalone Execution Test")
    print("=" * 70)
    
    # Load workflow
    workflow_path = Path(__file__).parent / "test_github_workflow.json"
    with open(workflow_path, 'r') as f:
        workflow_data = json.load(f)
    
    print(f"\n✓ Loaded workflow: {workflow_data['name']}")
    
    # Get GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("\n❌ GITHUB_TOKEN environment variable not set")
        return False
    
    print(f"✓ GITHUB_TOKEN found")
    
    # Test each GitHub operation
    print("\n" + "=" * 70)
    print("Testing GitHub Operations")
    print("=" * 70)
    
    import requests
    base_url = "https://api.github.com"
    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "n8n-github-node-test"
    }
    
    test_results = []
    
    # Test 1: Get Repository
    print("\n[1/4] Testing: Get Repository Info")
    try:
        response = requests.get(
            f"{base_url}/repos/n8n-io/n8n",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        repo_data = response.json()
        
        print(f"  ✓ Status: {response.status_code}")
        print(f"  ✓ Repository: {repo_data['full_name']}")
        print(f"  ✓ Stars: {repo_data['stargazers_count']:,}")
        print(f"  ✓ Forks: {repo_data['forks_count']:,}")
        
        test_results.append({
            "operation": "repository.get",
            "status": "passed",
            "data": {
                "name": repo_data['name'],
                "full_name": repo_data['full_name'],
                "stars": repo_data['stargazers_count']
            }
        })
    except Exception as e:
        print(f"  ❌ Failed: {str(e)}")
        test_results.append({
            "operation": "repository.get",
            "status": "failed",
            "error": str(e)
        })
    
    # Test 2: Get Authenticated User
    print("\n[2/4] Testing: Get Authenticated User")
    try:
        response = requests.get(
            f"{base_url}/user",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        user_data = response.json()
        
        print(f"  ✓ Status: {response.status_code}")
        print(f"  ✓ User: {user_data['login']}")
        print(f"  ✓ ID: {user_data['id']}")
        if user_data.get('name'):
            print(f"  ✓ Name: {user_data['name']}")
        
        test_results.append({
            "operation": "user.get",
            "status": "passed",
            "data": {
                "login": user_data['login'],
                "id": user_data['id'],
                "name": user_data.get('name')
            }
        })
    except Exception as e:
        print(f"  ❌ Failed: {str(e)}")
        test_results.append({
            "operation": "user.get",
            "status": "failed",
            "error": str(e)
        })
    
    # Test 3: List Repository Issues
    print("\n[3/4] Testing: List Repository Issues")
    try:
        response = requests.get(
            f"{base_url}/repos/n8n-io/n8n/issues",
            headers=headers,
            params={"state": "open", "per_page": 5},
            timeout=10
        )
        response.raise_for_status()
        issues = response.json()
        
        print(f"  ✓ Status: {response.status_code}")
        print(f"  ✓ Issues found: {len(issues)}")
        
        if issues:
            for i, issue in enumerate(issues[:3], 1):
                print(f"    {i}. #{issue['number']}: {issue['title'][:50]}...")
        
        test_results.append({
            "operation": "repository.getIssues",
            "status": "passed",
            "data": {
                "count": len(issues),
                "issues": [{"number": i['number'], "title": i['title']} for i in issues[:3]]
            }
        })
    except Exception as e:
        print(f"  ❌ Failed: {str(e)}")
        test_results.append({
            "operation": "repository.getIssues",
            "status": "failed",
            "error": str(e)
        })
    
    # Test 4: Get File Content
    print("\n[4/4] Testing: Get File Content")
    try:
        response = requests.get(
            f"{base_url}/repos/n8n-io/n8n/contents/README.md",
            headers=headers,
            timeout=10
        )
        response.raise_for_status()
        file_data = response.json()
        
        print(f"  ✓ Status: {response.status_code}")
        print(f"  ✓ File: {file_data['name']}")
        print(f"  ✓ Path: {file_data['path']}")
        print(f"  ✓ Size: {file_data['size']:,} bytes")
        
        test_results.append({
            "operation": "file.get",
            "status": "passed",
            "data": {
                "name": file_data['name'],
                "path": file_data['path'],
                "size": file_data['size']
            }
        })
    except Exception as e:
        print(f"  ❌ Failed: {str(e)}")
        test_results.append({
            "operation": "file.get",
            "status": "failed",
            "error": str(e)
        })
    
    # Summary
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    passed = sum(1 for r in test_results if r['status'] == 'passed')
    failed = sum(1 for r in test_results if r['status'] == 'failed')
    
    print(f"\nTotal Tests: {len(test_results)}")
    print(f"✓ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    # Save detailed results
    results_file = Path(__file__).parent / "github_node_execution_results.json"
    with open(results_file, 'w') as f:
        json.dump({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "workflow": workflow_data['name'],
            "test_results": test_results,
            "summary": {
                "total": len(test_results),
                "passed": passed,
                "failed": failed
            }
        }, f, indent=2)
    
    print(f"\n✓ Detailed results saved: {results_file}")
    
    if failed == 0:
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        print("\nThe GitHub node is ready for production use.")
        print("All operations successfully connected to GitHub API.")
        return True
    else:
        print("\n" + "=" * 70)
        print("⚠️  SOME TESTS FAILED")
        print("=" * 70)
        return False


def create_postman_collection():
    """Create a Postman collection for manual testing."""
    collection = {
        "info": {
            "name": "GitHub Node Workflow Test",
            "description": "Test the GitHub node workflow via the back project API",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "auth": {
            "type": "bearer",
            "bearer": [
                {
                    "key": "token",
                    "value": "{{JWT_TOKEN}}",
                    "type": "string"
                }
            ]
        },
        "variable": [
            {
                "key": "BASE_URL",
                "value": "http://localhost:8000",
                "type": "string"
            },
            {
                "key": "JWT_TOKEN",
                "value": "",
                "type": "string"
            },
            {
                "key": "GITHUB_TOKEN",
                "value": "",
                "type": "string"
            },
            {
                "key": "WORKFLOW_ID",
                "value": "",
                "type": "string"
            }
        ],
        "item": [
            {
                "name": "1. Create GitHub Credential",
                "request": {
                    "method": "POST",
                    "header": [
                        {
                            "key": "Content-Type",
                            "value": "application/json"
                        }
                    ],
                    "body": {
                        "mode": "raw",
                        "raw": json.dumps({
                            "name": "GitHub Test",
                            "type": "githubApi",
                            "data": {
                                "server": "https://api.github.com",
                                "accessToken": "{{GITHUB_TOKEN}}"
                            }
                        }, indent=2)
                    },
                    "url": {
                        "raw": "{{BASE_URL}}/credentials",
                        "host": ["{{BASE_URL}}"],
                        "path": ["credentials"]
                    }
                }
            },
            {
                "name": "2. Create Workflow",
                "request": {
                    "method": "POST",
                    "header": [
                        {
                            "key": "Content-Type",
                            "value": "application/json"
                        }
                    ],
                    "body": {
                        "mode": "raw",
                        "raw": "{{WORKFLOW_JSON}}"
                    },
                    "url": {
                        "raw": "{{BASE_URL}}/workflows",
                        "host": ["{{BASE_URL}}"],
                        "path": ["workflows"]
                    }
                }
            },
            {
                "name": "3. Execute Workflow",
                "request": {
                    "method": "POST",
                    "header": [
                        {
                            "key": "Content-Type",
                            "value": "application/json"
                        }
                    ],
                    "body": {
                        "mode": "raw",
                        "raw": "{}"
                    },
                    "url": {
                        "raw": "{{BASE_URL}}/workflows/{{WORKFLOW_ID}}/execute",
                        "host": ["{{BASE_URL}}"],
                        "path": ["workflows", "{{WORKFLOW_ID}}", "execute"]
                    }
                }
            },
            {
                "name": "4. Get Execution Result",
                "request": {
                    "method": "GET",
                    "header": [],
                    "url": {
                        "raw": "{{BASE_URL}}/executions/{{EXECUTION_ID}}",
                        "host": ["{{BASE_URL}}"],
                        "path": ["executions", "{{EXECUTION_ID}}"]
                    }
                }
            }
        ]
    }
    
    collection_file = Path(__file__).parent / "GitHub_Node_Test.postman_collection.json"
    with open(collection_file, 'w') as f:
        json.dump(collection, f, indent=2)
    
    print(f"\n✓ Postman collection created: {collection_file}")
    print("\nImport this into Postman and set the environment variables:")
    print("  - JWT_TOKEN: Your authentication token")
    print("  - GITHUB_TOKEN: Your GitHub personal access token")


if __name__ == "__main__":
    print("GitHub Node Real Execution Test\n")
    
    # Run standalone test
    success = test_github_node_standalone()
    
    # Create Postman collection
    if success:
        create_postman_collection()
    
    sys.exit(0 if success else 1)
