---
name: code-fix
version: "1.0.0"
description: Fix validation failures with bounded iteration. Max 3 attempts then escalate with artifacts.

# Contract
autonomy_level: IMPLEMENT
side_effects: [fs]
timeout_seconds: 300
retry:
  policy: none
  max_retries: 0
idempotency:
  required: false
  key_spec: null
max_fix_iterations: 3

input_schema:
  type: object
  required: [correlation_id, validation_report, files_modified, allowlist, iteration]
  properties:
    correlation_id:
      type: string
    validation_report:
      type: object
    files_modified:
      type: array
    allowlist:
      type: object
    iteration:
      type: integer
      minimum: 1
      maximum: 3

output_schema:
  type: object
  required: [fixed, iteration, changes_made]
  properties:
    fixed:
      type: boolean
    iteration:
      type: integer
    changes_made:
      type: array
      items: { type: string }
    escalation:
      type: object
      description: Present only if max iterations reached
      properties:
        reason: { type: string }
        remaining_errors: { type: array }

required_artifacts:
  - name: fix_log_{iteration}.json
    type: json
    description: Fix attempt log
  - name: escalation_report.json
    type: json
    description: Only if escalating after max iterations

failure_modes: [max_iterations, scope_violation, validation_error]
depends_on: [code-validate]
---

# Code Fix

Fix validation failures with bounded iteration loop.

## BOUNDED FIX LOOP

```
iteration 1 → validate → if pass: done
                      → if fail: fix → iteration 2
iteration 2 → validate → if pass: done
                      → if fail: fix → iteration 3
iteration 3 → validate → if pass: done
                      → if fail: ESCALATE (do NOT continue)
```

## SCOPE ENFORCEMENT

**ALL fixes MUST be within allowlist patterns.**
Scope violations are NOT fixable - escalate immediately.

## Fix Priority

1. **Scope violations** → Cannot fix, escalate
2. **Pytest failures** → Fix implementation bugs
3. **Ruff errors** → Auto-fixable with `ruff check --fix`
4. **Mypy errors** → Add type hints

## Fix Strategies

### Pytest Failures
- Read error message
- Identify failing assertion
- Fix implementation logic
- DO NOT change test to pass

### Ruff Errors
```bash
ruff check nodes/{node_name}.py --fix
```

### Mypy Errors
- Add missing type hints
- Fix type mismatches
- Use `Optional[]` for nullable

## Escalation Report

If iteration 3 fails, generate:

```json
{
  "correlation_id": "...",
  "total_iterations": 3,
  "reason": "max_iterations_exceeded",
  "remaining_errors": [
    {"type": "pytest", "error": "..."},
    {"type": "mypy", "error": "..."}
  ],
  "files_modified": ["..."],
  "recommendation": "Human review required"
}
```

## Artifacts Emitted

- `artifacts/{correlation_id}/fix_log_{iteration}.json`
- `artifacts/{correlation_id}/escalation_report.json` (if escalating)
