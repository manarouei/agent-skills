---
name: code-validate
version: "1.0.0"
description: Run validation suite - pytest, ruff, mypy. Enforces scope gate. Returns structured validation report.

# Contract
autonomy_level: READ
side_effects: []
timeout_seconds: 300
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id"
max_fix_iterations: 1

# Sync Celery Constraints (MANDATORY)
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: true
  forbids_background_tasks: true

input_schema:
  type: object
  required: [correlation_id, files_modified, test_files, allowlist]
  properties:
    correlation_id:
      type: string
    files_modified:
      type: array
    test_files:
      type: array
    allowlist:
      type: object

output_schema:
  type: object
  required: [passed, scope_check, pytest_result, ruff_result, mypy_result]
  properties:
    passed:
      type: boolean
    scope_check:
      type: object
      properties:
        passed: { type: boolean }
        violations: { type: array }
    pytest_result:
      type: object
      properties:
        passed: { type: boolean }
        tests_run: { type: integer }
        failures: { type: array }
    ruff_result:
      type: object
      properties:
        passed: { type: boolean }
        errors: { type: array }
    mypy_result:
      type: object
      properties:
        passed: { type: boolean }
        errors: { type: array }

required_artifacts:
  - name: validation_report.json
    type: json
    description: Complete validation report

failure_modes: [scope_violation, validation_error]
depends_on: [test-generate]
---

# Code Validate

Run validation suite and enforce scope gate.

## SCOPE GATE (MANDATORY)

**Runs BEFORE any other validation.**

```bash
python scripts/enforce_scope.py --allowlist artifacts/{correlation_id}/allowlist.json
```

If scope gate fails:
- Validation FAILS immediately
- No further checks run
- Generate scope_violation artifact

## Validation Commands

### 1. Scope Check
```bash
scripts/enforce_scope.py --allowlist {allowlist_path}
```

### 2. Pytest
```bash
cd /home/toni/n8n/back
pytest tests/test_{node_name}.py -v --tb=short
```

### 3. Ruff
```bash
cd /home/toni/n8n/back
ruff check nodes/{node_name}.py
```

### 4. Mypy
```bash
cd /home/toni/n8n/back
mypy nodes/{node_name}.py
```

## Pass Criteria

Validation passes if ALL:
- Scope check: No violations
- Pytest: All tests pass
- Ruff: No errors (warnings OK)
- Mypy: No errors (notes OK)

## Validation Report Structure

```json
{
  "passed": false,
  "scope_check": {
    "passed": true,
    "violations": []
  },
  "pytest_result": {
    "passed": false,
    "tests_run": 5,
    "failures": [
      {"test": "test_execute_create", "error": "AssertionError..."}
    ]
  },
  "ruff_result": {
    "passed": true,
    "errors": []
  },
  "mypy_result": {
    "passed": true,
    "errors": []
  }
}
```

## Artifacts Emitted

- `artifacts/{correlation_id}/validation_report.json`
