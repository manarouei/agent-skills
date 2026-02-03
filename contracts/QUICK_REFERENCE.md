# Contract Validator Quick Reference

## Installation

No installation needed - validator is a pure Python module.

```bash
cd /home/toni/agent-skills
# Validator is ready to use
```

## Basic Commands

### Validate Single Contract
```bash
python -m contracts.validator validate <contract.yaml>

# With verbose output (shows score breakdown)
python -m contracts.validator validate <contract.yaml> --verbose
```

**Example:**
```bash
python -m contracts.validator validate contracts/github.contract.yaml --verbose
```

**Output:**
```
✅ ACCEPTED - Score: 98/100

📊 Score Breakdown:
  • Contract Completeness: 40/40
  • Side-Effects & Credentials: 23/25
  • Execution Semantics: 25/25
  • n8n Normalization: 10/10
```

### Batch Validate Directory
```bash
python -m contracts.validator batch <directory>

# With verbose output
python -m contracts.validator batch <directory> --verbose
```

**Example:**
```bash
python -m contracts.validator batch contracts/
```

### Generate Contract Template
```bash
python -m contracts.validator template \
  --node-type <type> \
  --semantic-class <class> \
  [--credential-type <cred>]
```

**Example:**
```bash
python -m contracts.validator template \
  --node-type redis \
  --semantic-class tcp_client \
  --credential-type redisApi \
  > contracts/redis.contract.yaml
```

---

## Contract YAML Structure

### Minimal Contract
```yaml
node_type: mynode
version: "1.0.0"
semantic_class: http_rest

input_schema:
  fields:
    - name: operation
      type: string
      required: true
      enum: [read, write]

output_schema:
  success_fields:
    - name: result
      type: object
  error_fields:
    - name: error
      type: object

side_effects:
  types: [network]
  network_destinations: [api.example.com]

credential_scope:
  credential_type: myApi
  required: true
  host_allowlist: [api.example.com]

execution_semantics:
  timeout_seconds: 60
  retry_policy: transient
  idempotent: true
  max_retries: 2
  retry_delay_seconds: 2

n8n_normalization:
  defaults_explicit: true
  expression_boundaries: []
  eval_disabled: false
```

---

## Validation Rules

### Hard-Fail Invariants (Auto-Reject)

1. **Retry without Idempotency**
   ```yaml
   # ❌ REJECTED
   execution_semantics:
     max_retries: 2
     idempotent: false
   ```
   
   ```yaml
   # ✅ ACCEPTED
   execution_semantics:
     max_retries: 2
     idempotent: true
   ```

2. **Placeholder Hosts**
   ```yaml
   # ❌ REJECTED
   credential_scope:
     host_allowlist: [example.com, localhost, TODO]
   ```
   
   ```yaml
   # ✅ ACCEPTED
   credential_scope:
     host_allowlist: [api.github.com, api.stripe.com]
   ```

3. **Empty Allowlists**
   ```yaml
   # ❌ REJECTED
   credential_scope:
     host_allowlist: []
   ```
   
   ```yaml
   # ✅ ACCEPTED
   credential_scope:
     host_allowlist: [api.example.com]
   ```

4. **Missing Side-Effect Destinations**
   ```yaml
   # ❌ REJECTED
   side_effects:
     types: [network]
     network_destinations: null
   ```
   
   ```yaml
   # ✅ ACCEPTED
   side_effects:
     types: [network]
     network_destinations: [api.example.com]
   ```

### Scoring Thresholds

- **ACCEPTED:** Score ≥ 80/100
- **REJECTED:** Score < 80/100

**Score Components:**
- Contract Completeness: 40 points
- Side-Effects & Credentials: 25 points
- Execution Semantics: 25 points
- n8n Normalization: 10 points

---

## Common Patterns

### HTTP/REST Node
```yaml
semantic_class: http_rest
side_effects:
  types: [network]
  network_destinations: [api.example.com]
credential_scope:
  credential_type: exampleApi
  required: true
  host_allowlist: [api.example.com]
execution_semantics:
  timeout_seconds: 60
  retry_policy: transient
  idempotent: true  # For GET requests
  max_retries: 2
```

### Database Node (TCP)
```yaml
semantic_class: tcp_client
side_effects:
  types: [database]
  database_operations: [read, write]
credential_scope:
  credential_type: redisApi
  required: true
  database_allowlist: [production, staging]
execution_semantics:
  timeout_seconds: 30
  retry_policy: transient
  idempotent: false  # Write operations
  max_retries: 0      # No retries for writes
```

### SDK-Based Node
```yaml
semantic_class: sdk_client
side_effects:
  types: [network]
  network_destinations: [api.stripe.com]
credential_scope:
  credential_type: stripeApi
  required: true
  host_allowlist: [api.stripe.com]
execution_semantics:
  timeout_seconds: 45
  retry_policy: idempotent_only
  idempotent: true
  max_retries: 3
```

### Pure Transform Node
```yaml
semantic_class: pure_transform
side_effects:
  types: []
  network_destinations: null
  database_operations: null
  filesystem_paths: null
credential_scope:
  credential_type: none
  required: false
execution_semantics:
  timeout_seconds: 10
  retry_policy: none
  idempotent: true
  max_retries: 0
```

---

## Troubleshooting

### Contract Rejected: "Invalid placeholder host"

**Problem:** Host contains forbidden substring (example.com, localhost, TODO, dummy, placeholder)

**Fix:**
```yaml
# ❌ Before
host_allowlist: [api.example.com]

# ✅ After
host_allowlist: [api.mycompany.com]
```

### Contract Rejected: "Cannot have max_retries > 0 without idempotent=True"

**Problem:** Retry without idempotency causes data corruption

**Fix Option 1 (No Retries):**
```yaml
execution_semantics:
  max_retries: 0
  idempotent: false
```

**Fix Option 2 (Mark as Idempotent):**
```yaml
execution_semantics:
  max_retries: 2
  idempotent: true
```

### Score Too Low (<80)

**Problem:** Missing required fields in contract

**Check:**
1. Input schema completeness
2. Output schema completeness (success + error fields)
3. Side-effect destinations specified
4. Credential scope defined

**Fix:** Add missing sections to contract

---

## Exit Codes

- `0` - Validation PASSED (score ≥80, no hard-fails)
- `1` - Validation FAILED (score <80 or hard-fail violation)
- `2` - Invalid arguments or file not found

---

## Examples

### Example 1: GitHub Node (Golden Reference)
```bash
python -m contracts.validator validate contracts/github.contract.yaml --verbose
```

**Result:** ✅ ACCEPTED - Score: 98/100

### Example 2: Redis Node (To Be Created)
```bash
# Generate template
python -m contracts.validator template \
  --node-type redis \
  --semantic-class tcp_client \
  > contracts/redis.contract.yaml

# Edit contract
vim contracts/redis.contract.yaml

# Validate
python -m contracts.validator validate contracts/redis.contract.yaml --verbose
```

### Example 3: Batch Validate All Contracts
```bash
python -m contracts.validator batch contracts/ --verbose
```

---

## Quick Checklist

Before submitting a contract for validation:

- [ ] `node_type`, `version`, `semantic_class` specified
- [ ] Input schema has at least one required field
- [ ] Output schema has both success_fields and error_fields
- [ ] Side-effects types declared with destinations
- [ ] Credential scope specified (even if required=false)
- [ ] Execution semantics complete (timeout, retry, idempotent)
- [ ] No placeholder hosts (example.com, localhost, TODO)
- [ ] If max_retries > 0, then idempotent=true
- [ ] n8n normalization declared

---

## Getting Help

**Documentation:**
- Full Architecture: `docs/CONTRACT_FIRST_ARCHITECTURE.md`
- Bug Fix Report: `contracts/VALIDATOR_BUG_FIX.md`
- Implementation Report: `contracts/IMPLEMENTATION_REPORT.md`

**Code:**
- Contract Schema: `contracts/node_contract.py`
- Validator CLI: `contracts/validator.py`
- Golden Reference: `contracts/github.contract.yaml`

**Tests:**
- Verification Suite: `contracts/test_validator_bugfix.py`
```

**Run Tests:**
```bash
python -m contracts.test_validator_bugfix
```
