---
name: self-heal-coordinator
version: "1.0.0"
description: Bounded retry loop coordinator with deterministic error classification and automated fixes. Max 2 attempts with template/validator patches.

# Contract
autonomy_level: IMPLEMENT
side_effects: [fs]
timeout_seconds: 300
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id"
max_fix_iterations: 0  # No nested fixing - this IS the fix loop

# Filesystem scope: ARTIFACT - writes to artifact directory only
fs_scope: artifact

# Sync Celery Constraints (MANDATORY)
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: false
  forbids_background_tasks: true

# Execution mode: HYBRID (deterministic classification + template fixes)
execution_mode: HYBRID

input_schema:
  type: object
  required: [correlation_id, scenario_results, node_type]
  properties:
    correlation_id:
      type: string
    scenario_results:
      type: object
      description: Results from scenario-workflow-test
    node_type:
      type: string
    max_attempts:
      type: integer
      default: 2
      description: Max fix attempts (hard limit)

output_schema:
  type: object
  required: [healed, attempts, final_status]
  properties:
    healed:
      type: boolean
      description: True if errors were fixed
    attempts:
      type: integer
    final_status:
      type: string
      enum: [success, failed_max_attempts, failed_unfixable]
    fixes_applied:
      type: array
      items:
        type: object

required_artifacts:
  - name: self_heal_report.json
    type: json
    description: Detailed self-healing attempt log

failure_modes: [max_attempts_exceeded, unfixable_error]
depends_on: [scenario-workflow-test]
---

# Self-Heal Coordinator

Bounded retry loop with deterministic error fixes.

## Purpose

This skill:
1. Analyzes scenario test failures
2. Classifies errors deterministically
3. Applies template/validator fixes
4. Re-runs scenarios (max 2 attempts)
5. Produces detailed failure report if unfixable

## Error Classification → Fix Mapping

| Error Type | Fix Strategy |
|------------|-------------|
| ImportError | Add missing import to template |
| AttributeError | Check BaseNode method signature |
| SchemaError | Update node schema validator |
| CredentialError | Re-provision credential |
| RuntimeError | Log for manual review |
| TimeoutError | Increase timeout, check API |

## Fix Application Rules

1. **Prefer templates over hand-editing**
   - If template needs fixing, update template FIRST
   - Then regenerate node from template
   
2. **Strengthen validators**
   - If error should have been caught, add validation rule
   - Never weaken tests to pass
   
3. **Bound attempts strictly**
   - Max 2 attempts (configurable, hard cap at 3)
   - After max attempts, escalate with detailed report

## Output Artifacts

```
artifacts/{correlation_id}/
└── self_heal_report.json
    {
      "correlation_id": "...",
      "node_type": "bitly",
      "attempts": 2,
      "final_status": "failed_max_attempts",
      "errors_classified": [
        {
          "error_type": "ImportError",
          "message": "No module named 'requests'",
          "fix_attempted": "add_dependency",
          "fix_success": false
        }
      ],
      "recommendations": [
        "Add 'requests' to requirements.txt",
        "Verify base template includes common dependencies"
      ]
    }
```

## Escalation Criteria

Escalate (stop and report) if:
- Max attempts reached
- Error is classified as "Unfixable"
- Same error repeats after fix
- No applicable fix pattern exists
