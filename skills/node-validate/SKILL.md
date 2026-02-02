---
name: node-validate
version: "1.0.0"
description: Validate packaged node artifacts before apply-changes. Runs syntax check, import test, and optional linting.

# Contract
autonomy_level: IMPLEMENT
side_effects: [fs]
timeout_seconds: 120
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id"
max_fix_iterations: 1

# Filesystem scope: ARTIFACTS means this skill only writes to artifacts/
# Reads from artifacts/{correlation_id}/package/
# Writes validation results to artifacts/{correlation_id}/validation/
fs_scope: artifacts

# Sync Celery Constraints
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: true
  forbids_background_tasks: true

input_schema:
  type: object
  required: [correlation_id]
  properties:
    correlation_id:
      type: string
      description: Session correlation ID for artifact paths
    skip_lint:
      type: boolean
      default: false
      description: Skip linting (faster but less thorough)
    target_repo_layout:
      type: object
      description: Target repo layout for context (Python version, etc.)

output_schema:
  type: object
  required: [valid, checks]
  properties:
    valid:
      type: boolean
      description: True if all validation checks passed
    checks:
      type: array
      items:
        type: object
        properties:
          name:
            type: string
          passed:
            type: boolean
          details:
            type: string
    errors:
      type: array
      items:
        type: string
    warnings:
      type: array
      items:
        type: string

required_artifacts:
  - name: validation/results.json
    type: json
    description: Validation results with all check outcomes

failure_modes: [validation_error, parse_error]
depends_on: [node-package]
---

# Node Validate

This skill validates packaged node artifacts before apply-changes.

## Purpose

Before applying changes to the target repo, validate that:
1. Python files have valid syntax (compile test)
2. Imports can be resolved (import test with mocking)
3. Code passes basic linting (optional)
4. Class structure matches expected patterns

## Validation Checks

1. **Syntax Check**: Uses py_compile to verify valid Python syntax
2. **AST Check**: Parses AST to verify structure
3. **Import Check**: Verifies imports can be parsed (no execution)
4. **Class Check**: Verifies node class exists with expected pattern
5. **Lint Check** (optional): Runs ruff or basic style checks

## Output Structure

Creates:
```
artifacts/{correlation_id}/validation/
  └── results.json  # All check results
```

## Usage in Pipeline

```
node-package → node-validate → apply-changes
                    ↑
            Validates before apply
            (catches errors early)
```
