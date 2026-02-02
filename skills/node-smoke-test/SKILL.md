---
name: node-smoke-test
version: "1.0.0"
description: Smoke test the applied node by importing it in the target repo's Python environment. Verifies the node class exists and can be instantiated.

# Contract
autonomy_level: READ
side_effects: []
timeout_seconds: 60
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id"
max_fix_iterations: 1

# Filesystem scope: ARTIFACTS (only writes test results)
# Reads from target_repo but does NOT modify it
fs_scope: artifacts

# Sync Celery Constraints
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: true
  forbids_background_tasks: true

input_schema:
  type: object
  required: [correlation_id, target_repo_layout]
  properties:
    correlation_id:
      type: string
      description: Session correlation ID for artifact paths
    target_repo_layout:
      type: object
      required: [target_repo_root, node_output_base_dir]
      description: Target repository layout from repo-ground
    node_type:
      type: string
      description: Node type to test (from manifest if not provided)

output_schema:
  type: object
  required: [success, tests]
  properties:
    success:
      type: boolean
      description: True if all smoke tests passed
    tests:
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

required_artifacts:
  - name: smoke_test/results.json
    type: json
    description: Smoke test results

failure_modes: [timeout, validation_error]
depends_on: [apply-changes]
---

# Node Smoke Test

This skill verifies the applied node can be imported and instantiated in the target repo's Python environment.

## Purpose

After apply-changes writes files to target repo, this skill:
1. Attempts to import the node module
2. Verifies the node class exists
3. Checks the node can be instantiated (basic instantiation)
4. Validates required attributes exist

## Test Approach

Uses subprocess to run a Python import test in the target repo's environment:
```python
import sys
sys.path.insert(0, '/path/to/repo')
from nodes.bitly import BitlyNode
print(BitlyNode.type)  # Verify attribute
```

## Safety

- **fs_scope: artifacts** - Only writes results to artifacts/
- Does NOT modify target_repo (READ autonomy)
- Uses subprocess with timeout for safety
- No side effects on target repo

## Usage in Pipeline

```
apply-changes → node-smoke-test
                     ↑
             Verifies applied node
             works in target env
```
