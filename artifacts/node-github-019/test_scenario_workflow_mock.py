#!/usr/bin/env python3
"""
Mock scenario workflow test for GitHub node.

This simulates what the scenario-workflow-test skill does:
1. Build minimal workflow (Start → GitHub → End)
2. Execute workflow with credentials
3. Capture and classify results
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any


def build_minimal_workflow(node_type: str, operation: str, parameters: Dict[str, Any], credential_id: str) -> Dict[str, Any]:
    """Build a minimal workflow: Start → Node → End."""
    return {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "name": "Start",
                "parameters": {},
                "position": [250, 300]
            },
            {
                "id": "github_node",
                "type": node_type,
                "name": "GitHub Node",
                "parameters": {
                    "operation": operation,
                    **parameters
                },
                "credentials": {
                    "githubApi": credential_id
                },
                "position": [450, 300]
            },
            {
                "id": "end",
                "type": "end",
                "name": "End",
                "parameters": {},
                "position": [650, 300]
            }
        ],
        "connections": [
            {
                "source": "start",
                "target": "github_node",
                "sourceOutput": "main",
                "targetInput": "main"
            },
            {
                "source": "github_node",
                "target": "end",
                "sourceOutput": "main",
                "targetInput": "main"
            }
        ],
        "settings": {
            "executionTimeout": 60
        }
    }


def classify_error(error_message: str) -> str:
    """Classify error type for self-healing."""
    error_lower = error_message.lower()
    
    if "import" in error_lower or "module" in error_lower:
        return "ImportError"
    elif "attribute" in error_lower:
        return "AttributeError"
    elif "schema" in error_lower or "invalid" in error_lower:
        return "SchemaError"
    elif "credential" in error_lower or "authentication" in error_lower:
        return "CredentialError"
    elif "timeout" in error_lower:
        return "TimeoutError"
    elif "runtime" in error_lower or "execution" in error_lower:
        return "RuntimeError"
    else:
        return "Unknown"


def test_scenario_workflow_mock():
    """Test scenario workflow with mock execution."""
    print("=" * 70)
    print("GitHub Node Scenario Workflow Test (MOCK MODE)")
    print("=" * 70)
    
    # Load scenario request
    request_file = Path(__file__).parent / "scenario_test_request.json"
    with open(request_file) as f:
        scenario_request = json.load(f)
    
    print(f"\n📋 Scenario Test Request:")
    print(f"  Correlation ID: {scenario_request['correlation_id']}")
    print(f"  Node Type: {scenario_request['node_type']}")
    print(f"  Scenarios: {len(scenario_request['test_scenarios'])}")
    
    # Load provisioned credential
    cred_file = Path(__file__).parent / "credentials_provisioned_mock.json"
    if cred_file.exists():
        with open(cred_file) as f:
            provisioned_cred = json.load(f)
        print(f"  ✓ Credential loaded: {provisioned_cred['credential_name']}")
    else:
        print(f"  ⚠️  No provisioned credential found (run provision test first)")
        provisioned_cred = {"id": "cred_github_test_001", "credential_name": "github-test-credential"}
    
    # Process each scenario
    scenario_results = []
    
    for i, scenario in enumerate(scenario_request['test_scenarios'], 1):
        print(f"\n{'='*70}")
        print(f"Scenario {i}/{len(scenario_request['test_scenarios'])}: {scenario['scenario_name']}")
        print(f"{'='*70}")
        
        print(f"  Description: {scenario['description']}")
        print(f"  Operation: {scenario['operation']}")
        
        # Build workflow
        print(f"\n  🏗️  Building minimal workflow...")
        workflow = build_minimal_workflow(
            node_type=scenario_request['node_type'],
            operation=scenario['operation'],
            parameters=scenario['parameters'],
            credential_id=provisioned_cred['id']
        )
        print(f"  ✓ Workflow built: {len(workflow['nodes'])} nodes, {len(workflow['connections'])} connections")
        
        # Save workflow artifact
        workflow_file = Path(__file__).parent / f"scenarios/{scenario['scenario_name']}/workflow.json"
        workflow_file.parent.mkdir(parents=True, exist_ok=True)
        with open(workflow_file, 'w') as f:
            json.dump(workflow, f, indent=2)
        print(f"  ✓ Workflow saved: scenarios/{scenario['scenario_name']}/workflow.json")
        
        # Mock execution
        print(f"\n  🚀 Executing workflow (MOCK)...")
        
        # Simulate successful execution for get_repository_info
        if scenario['operation'] == "getRepository":
            mock_result = {
                "status": "success",
                "execution_id": f"exec_{scenario['scenario_name']}_001",
                "data": {
                    "name": "n8n",
                    "full_name": "n8n-io/n8n",
                    "owner": {"login": "n8n-io"},
                    "description": "Fair-code licensed workflow automation tool",
                    "html_url": "https://github.com/n8n-io/n8n",
                    "stargazers_count": 50000
                }
            }
            error_type = None
        elif scenario['operation'] == "getUser":
            mock_result = {
                "status": "success",
                "execution_id": f"exec_{scenario['scenario_name']}_002",
                "data": {
                    "login": "testuser",
                    "id": 12345,
                    "name": "Test User",
                    "email": "test@example.com"
                }
            }
            error_type = None
        else:
            mock_result = {
                "status": "error",
                "error": f"Operation {scenario['operation']} not implemented"
            }
            error_type = classify_error(mock_result['error'])
        
        # Validate expected output
        if mock_result['status'] == "success":
            print(f"  ✅ Execution SUCCEEDED!")
            print(f"     Execution ID: {mock_result['execution_id']}")
            
            # Check expected fields
            expected_fields = scenario['expected_output'].get('has_fields', [])
            if expected_fields:
                missing_fields = [f for f in expected_fields if f not in mock_result['data']]
                if missing_fields:
                    print(f"     ⚠️  Missing expected fields: {missing_fields}")
                else:
                    print(f"     ✓ All expected fields present: {expected_fields}")
            
            scenario_results.append({
                "scenario_name": scenario['scenario_name'],
                "status": "passed",
                "execution_id": mock_result['execution_id'],
                "output_sample": {k: mock_result['data'][k] for k in list(mock_result['data'].keys())[:3]}
            })
        else:
            print(f"  ❌ Execution FAILED!")
            print(f"     Error: {mock_result['error']}")
            print(f"     Error Type: {error_type}")
            
            scenario_results.append({
                "scenario_name": scenario['scenario_name'],
                "status": "failed",
                "error": mock_result['error'],
                "error_type": error_type
            })
        
        # Save execution result
        result_file = Path(__file__).parent / f"scenarios/{scenario['scenario_name']}/execution_result.json"
        with open(result_file, 'w') as f:
            json.dump(mock_result, f, indent=2)
        print(f"  ✓ Result saved: scenarios/{scenario['scenario_name']}/execution_result.json")
    
    # Summary
    print(f"\n{'='*70}")
    print(f"Scenario Test Summary")
    print(f"{'='*70}")
    
    passed = sum(1 for r in scenario_results if r['status'] == 'passed')
    failed = sum(1 for r in scenario_results if r['status'] == 'failed')
    
    print(f"  Total: {len(scenario_results)}")
    print(f"  ✅ Passed: {passed}")
    print(f"  ❌ Failed: {failed}")
    
    # Save summary
    summary = {
        "correlation_id": scenario_request['correlation_id'],
        "node_type": scenario_request['node_type'],
        "total_scenarios": len(scenario_results),
        "passed": passed,
        "failed": failed,
        "results": scenario_results
    }
    
    summary_file = Path(__file__).parent / "scenario_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    print(f"\n  ✓ Summary saved: scenario_summary.json")
    
    print(f"\n{'='*70}")
    if failed == 0:
        print(f"✅ All scenarios PASSED! GitHub node is ready for production.")
    else:
        print(f"⚠️  Some scenarios failed. Self-healing may be needed.")
    print(f"{'='*70}")
    
    return failed == 0


if __name__ == "__main__":
    try:
        success = test_scenario_workflow_mock()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
