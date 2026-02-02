"""
Scenario Workflow Test Skill Implementation

Builds minimal test workflows and executes them via platform API.
DETERMINISTIC: Pure workflow building + REST API calls.
SYNC-CELERY SAFE: Synchronous execution with timeouts.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext

from runtime.platform_client import PlatformClient, PlatformClientError, create_client_from_env
from runtime.protocol import AgentResponse, TaskState


def _build_minimal_workflow(
    node_type: str,
    parameters: Dict[str, Any],
    credentials: Dict[str, str],
    input_data: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Build a minimal workflow: Start → NodeUnderTest → End.
    
    Args:
        node_type: Type of node to test (e.g., "bitly")
        parameters: Node parameters
        credentials: Credential type to ID mapping
        input_data: Optional input data for Start node
    
    Returns:
        Workflow definition dictionary
    """
    workflow = {
        "nodes": [
            {
                "id": "start",
                "type": "start",
                "name": "Start",
                "position": [0, 0],
                "parameters": {},
            },
            {
                "id": "node-under-test",
                "type": node_type,
                "name": f"{node_type.title()} Test",
                "position": [200, 0],
                "parameters": parameters,
                "credentials": credentials,
            },
            {
                "id": "end",
                "type": "end",
                "name": "End",
                "position": [400, 0],
                "parameters": {},
            },
        ],
        "connections": [
            {
                "source": "start",
                "sourceOutput": 0,
                "target": "node-under-test",
                "targetInput": 0,
            },
            {
                "source": "node-under-test",
                "sourceOutput": 0,
                "target": "end",
                "targetInput": 0,
            },
        ],
    }
    
    if input_data:
        workflow["nodes"][0]["parameters"]["data"] = input_data
    
    return workflow


def _classify_error(error_message: str, execution_result: Dict[str, Any]) -> str:
    """
    Classify error type for self-healing.
    
    Returns error classification:
    - ImportError, AttributeError, SchemaError, CredentialError, RuntimeError, TimeoutError, Unknown
    """
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


def _extract_node_outputs(execution_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract per-node outputs from execution result.
    
    Returns dictionary mapping node_id -> output_data
    """
    node_outputs = {}
    
    # Check for node results in execution data
    if "data" in execution_result:
        data = execution_result["data"]
        if "resultData" in data:
            result_data = data["resultData"]
            if "runData" in result_data:
                run_data = result_data["runData"]
                for node_id, node_data in run_data.items():
                    if isinstance(node_data, list) and node_data:
                        # Get output from first run
                        first_run = node_data[0]
                        if "data" in first_run:
                            node_outputs[node_id] = first_run["data"]
    
    return node_outputs


def run(ctx: "ExecutionContext") -> dict[str, Any]:
    """
    Execute scenario workflow tests.
    
    Reads from:
    - inputs: node_type, test_scenarios, platform_config
    - artifacts/{correlation_id}/credentials_provisioned.json (for credential IDs)
    
    Writes to:
    - artifacts/{correlation_id}/scenarios/{scenario_name}/*
    - artifacts/{correlation_id}/scenario_summary.json
    """
    inputs = ctx.inputs
    correlation_id = inputs["correlation_id"]
    node_type = inputs["node_type"]
    test_scenarios = inputs["test_scenarios"]
    platform_config = inputs.get("platform_config", {})
    execution_timeout = inputs.get("execution_timeout", 60)
    
    ctx.log("scenario_test_start", {
        "correlation_id": correlation_id,
        "node_type": node_type,
        "scenario_count": len(test_scenarios),
    })
    
    # Setup paths
    artifact_base = ctx.artifact_root / correlation_id
    scenarios_dir = artifact_base / "scenarios"
    scenarios_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize platform client
    try:
        if platform_config:
            client = PlatformClient(
                base_url=platform_config["base_url"],
                auth_token=platform_config["auth_token"],
                timeout=platform_config.get("timeout", 30),
            )
        else:
            client = create_client_from_env()
    except Exception as e:
        ctx.log("platform_client_init_error", {"error": str(e)})
        return {
            "scenarios_executed": [],
            "scenarios_failed": [
                {
                    "scenario_name": "all",
                    "reason": f"Platform client initialization failed: {str(e)}"
                }
            ],
        }
    
    executed = []
    failed = []
    
    for scenario in test_scenarios:
        scenario_name = scenario["scenario_name"]
        operation = scenario.get("operation", "")
        parameters = scenario["parameters"]
        credentials = scenario["credentials"]
        input_data = scenario.get("input_data")
        
        # Create scenario directory
        scenario_dir = scenarios_dir / scenario_name
        scenario_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            ctx.log("scenario_executing", {
                "scenario_name": scenario_name,
                "operation": operation,
            })
            
            # Build workflow
            workflow_def = _build_minimal_workflow(
                node_type=node_type,
                parameters=parameters,
                credentials=credentials,
                input_data=input_data,
            )
            
            # Write workflow definition
            workflow_file = scenario_dir / "workflow.json"
            workflow_file.write_text(json.dumps(workflow_def, indent=2))
            
            # Create workflow via API
            workflow_name = f"test-{node_type}-{scenario_name}"
            create_result = client.workflows.create(
                name=workflow_name,
                workflow_data=workflow_def,
                active=True,
            )
            
            workflow_id = create_result.get("id") or create_result.get("workflow_id")
            
            if not workflow_id:
                raise ValueError("No workflow ID in response")
            
            ctx.log("workflow_created", {
                "scenario_name": scenario_name,
                "workflow_id": workflow_id,
            })
            
            # Execute workflow
            exec_result = client.workflows.execute_rest(
                workflow_id=workflow_id,
                input_data=input_data,
                wait_for_completion=True,
                timeout=execution_timeout,
            )
            
            execution_id = exec_result.get("id") or exec_result.get("execution_id")
            status = exec_result.get("status", "unknown")
            success = status == "completed" or status == "success"
            
            # Write execution result
            result_file = scenario_dir / "execution_result.json"
            result_file.write_text(json.dumps(exec_result, indent=2))
            
            # Extract node outputs
            node_outputs = _extract_node_outputs(exec_result)
            outputs_file = scenario_dir / "node_outputs.json"
            outputs_file.write_text(json.dumps(node_outputs, indent=2))
            
            # Check for errors
            error_message = exec_result.get("error") or exec_result.get("error_message", "")
            
            if error_message or not success:
                error_classification = _classify_error(error_message, exec_result)
                
                error_details = {
                    "error_message": error_message,
                    "classification": error_classification,
                    "status": status,
                    "execution_id": execution_id,
                }
                
                error_file = scenario_dir / "error_details.json"
                error_file.write_text(json.dumps(error_details, indent=2))
                
                ctx.log("scenario_error", {
                    "scenario_name": scenario_name,
                    "classification": error_classification,
                })
            else:
                ctx.log("scenario_success", {
                    "scenario_name": scenario_name,
                    "execution_id": execution_id,
                })
            
            executed.append({
                "scenario_name": scenario_name,
                "workflow_id": workflow_id,
                "execution_id": execution_id,
                "status": status,
                "success": success,
                "error_classification": error_classification if error_message else None,
            })
            
            # Cleanup: delete workflow
            try:
                client.workflows.delete(workflow_id)
            except Exception:
                pass  # Ignore cleanup errors
            
        except PlatformClientError as e:
            ctx.log("scenario_platform_error", {
                "scenario_name": scenario_name,
                "error": str(e),
            })
            failed.append({
                "scenario_name": scenario_name,
                "reason": f"Platform API error: {str(e)}"
            })
        except Exception as e:
            ctx.log("scenario_unexpected_error", {
                "scenario_name": scenario_name,
                "error": str(e),
            })
            failed.append({
                "scenario_name": scenario_name,
                "reason": f"Unexpected error: {str(e)}"
            })
    
    # Write summary
    summary = {
        "correlation_id": correlation_id,
        "node_type": node_type,
        "timestamp": datetime.utcnow().isoformat(),
        "total_scenarios": len(test_scenarios),
        "executed": len(executed),
        "failed": len(failed),
        "success_rate": len([s for s in executed if s["success"]]) / len(executed) if executed else 0,
        "scenarios": executed,
        "failures": failed,
    }
    
    summary_file = artifact_base / "scenario_summary.json"
    summary_file.write_text(json.dumps(summary, indent=2))
    
    ctx.log("scenario_test_complete", {
        "executed": len(executed),
        "failed": len(failed),
        "success_rate": summary["success_rate"],
    })
    
    return {
        "scenarios_executed": executed,
        "scenarios_failed": failed,
    }
