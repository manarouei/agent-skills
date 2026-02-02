---
name: contract-validate
autonomy_level: IMPLEMENT
side_effects: [fs]
timeout_seconds: 30
max_fix_iterations: 0
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
---

# contract-validate

**Purpose:** Mechanically validate execution contracts to enforce ≥80% correctness threshold.

## Inputs

- `correlation_id` (required) - Unique workflow identifier
- `contract_path` (optional) - Path to contract YAML (default: artifacts/{correlation_id}/node.contract.yaml)

## Outputs

- `validation_result.json` - Score breakdown and pass/fail status
- Exit 0 if score ≥80 and no hard-fail violations
- Exit 1 if score <80 or hard-fail violation detected

## Behavior

1. Load contract from `contract_path`
2. Validate using `contracts.validator.validate_contract_file()`
3. Write validation result to `artifacts/{correlation_id}/validation_result.json`
4. If score <80 or hard-fail: return FAIL
5. If score ≥80 and no hard-fail: return PASS

## Integration

Runs after `code-implement` and before `code-validate`:

```
code-implement → contract-validate → code-validate → code-fix → pr-prepare
```

Contract generation is handled by `node-scaffold` (generates template) and `code-implement` (fills in specifics).

## Hard-Fail Invariants

1. Retry without idempotency (max_retries > 0 requires idempotent=true)
2. Placeholder hosts (example.com, localhost, TODO, dummy, placeholder)
3. Empty allowlists (if specified, must contain at least one entry)
4. Missing side-effect destinations (if type declared, must specify destinations)
5. Timeout bounds (1-3600 seconds)
6. Max retries bounds (0-5 attempts)
7. Retry policy consistency (idempotent_only requires idempotent=true)
8. Credential type required (cannot be empty)

## Scoring Model

- Contract Completeness: 40 points
- Side-Effects & Credentials: 25 points
- Execution Semantics: 25 points
- n8n Normalization: 10 points

**Threshold:** ≥80/100 to PASS
