---
name: scenario-workflow-test
version: "1.0.0"
description: Build and execute minimal test workflows (Start → NodeUnderTest → End) via platform API. Captures execution results and events for validation.

# Contract
autonomy_level: IMPLEMENT
side_effects: [net]
timeout_seconds: 180
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id + node_type"
max_fix_iterations: 2

# Filesystem scope: ARTIFACT - writes to artifact directory only
fs_scope: artifact

# Sync Celery Constraints (MANDATORY)
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: true
  forbids_background_tasks: true

# Execution mode: DETERMINISTIC (workflow building + API calls, no AI)
execution_mode: DETERMINISTIC

input_schema:
  type: object
  required: [correlation_id, node_type, test_scenarios]
  properties:
    correlation_id:
      type: string
      description: Session correlation ID for artifact paths
    node_type:
      type: string
      description: Node type being tested (e.g., "bitly")
    test_scenarios:
      type: array
      items:
        type: object
        required: [scenario_name, operation, parameters, credentials]
        properties:
          scenario_name:
            type: string
          operation:
            type: string
          parameters:
            type: object
          credentials:
            type: object
          input_data:
            type: object
      description: Test scenarios to execute
    platform_config:
      type: object
      description: Platform connection config
    execution_timeout:
      type: integer
      default: 60
      description: Max wait time for workflow execution (seconds)

output_schema:
  type: object
  required: [scenarios_executed, scenarios_failed]
  properties:
    scenarios_executed:
      type: array
      items:
        type: object
        properties:
          scenario_name:
            type: string
          workflow_id:
            type: string
          execution_id:
            type: string
          status:
            type: string
          success:
            type: boolean
    scenarios_failed:
      type: array
      items:
        type: object
        properties:
          scenario_name:
            type: string
          reason:
            type: string

required_artifacts:
  - name: scenarios/
    type: directory
    description: Per-scenario workflow definitions and results
  - name: scenario_summary.json
    type: json
    description: Summary of all scenario executions

failure_modes: [network_error, workflow_error, timeout_error]
depends_on: [credential-provision, apply-changes]
---

# Scenario Workflow Test

Build and execute minimal test workflows to verify node behavior.

## Purpose

This skill:
1. Builds minimal workflows: Start → NodeUnderTest → End
2. Executes workflows via platform API (REST)
3. Captures execution results and per-node outputs
4. Detects common errors (missing imports, schema errors, runtime failures)
5. Writes detailed artifacts for debugging and self-healing

## Workflow Structure

```json
{
  "nodes": [
    {
      "id": "start",
      "type": "start",
      "position": [0, 0]
    },
    {
      "id": "node-under-test",
      "type": "bitly",
      "position": [200, 0],
      "parameters": {
        "resource": "link",
        "operation": "create",
        "longUrl": "https://example.com"
      },
      "credentials": {
        "bitlyApi": "cred_abc123"
      }
    },
    {
      "id": "end",
      "type": "end",
      "position": [400, 0]
    }
  ],
  "connections": [
    {"from": "start", "to": "node-under-test"},
    {"from": "node-under-test", "to": "end"}
  ]
}
```

## Test Scenarios

Each scenario specifies:
- `scenario_name`: Human-readable identifier
- `operation`: Node operation to test (e.g., "link/create")
- `parameters`: Node parameters for this operation
- `credentials`: Credential ID mapping
- `input_data`: Optional input data for Start node

Example:
```yaml
test_scenarios:
  - scenario_name: "bitly-link-create"
    operation: "link/create"
    parameters:
      resource: "link"
      operation: "create"
      longUrl: "https://example.com"
    credentials:
      bitlyApi: "cred_abc123"
```

## Output Artifacts

```
artifacts/{correlation_id}/scenarios/
├── bitly-link-create/
│   ├── workflow.json         # Workflow definition
│   ├── execution_result.json # Full execution result
│   ├── node_outputs.json     # Per-node output data
│   └── error_details.json    # If execution failed
└── scenario_summary.json     # Summary of all scenarios
```

## Error Classification

Classifies errors for self-healing:
- `ImportError`: Missing module/dependency
- `AttributeError`: Missing node method/property
- `SchemaError`: Invalid node schema
- `CredentialError`: Credential missing/invalid
- `RuntimeError`: Node execution error
- `TimeoutError`: Execution timeout

## Success Criteria

A scenario is successful if:
1. Workflow executes without error
2. NodeUnderTest produces output
3. No exception in execution result
