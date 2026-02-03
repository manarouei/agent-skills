# Contract-First Node Architecture

## Critical: Read This First

**The GitHub node (`avidflow-back/nodes/github.py`) is the ONLY agent-generated node that currently meets the correctness bar.**

All other manually implemented nodes are behavioral references, NOT structural templates.

## The Problem (Why We Need This)

The current system behaves like:
> "Python modules that happen to be called nodes"

NOT like:
> "Agent tools with explicit, machine-checkable contracts"

This is the root cause of:
- Generated nodes with placeholder logic
- Undeclared side-effects causing runtime failures
- No mechanical rejection of bad conversions
- Human reviewers compensating for missing invariants

## The Solution: Contract-First Architecture

A converted node is **NOT** a Python file.

It is a **pair**:

1. **Contract Manifest** (`.contract.yaml`) - Authoritative, machine-checked
2. **Implementation** (`.py`) - Must conform exactly to manifest

### Hard-Fail Invariants

If ANY of these fail → node is **mechanically rejected** (<80% correctness):

```yaml
❌ No machine-readable contract manifest
❌ Input/output schema cannot be validated
❌ Undeclared side-effects (network / db / fs / messaging)
❌ No hard execution timeout
❌ Retry policy without idempotency semantics
❌ Placeholder endpoints (example.com, TODO, empty DSN)
❌ Unknown inputs silently accepted
❌ Error model is implicit (raw exceptions leak)
```

### ≥80% Correctness Scoring

Only evaluated if no hard-fail occurred:

| Component | Points | Requirements |
|-----------|--------|--------------|
| **Contract Completeness** | 40 | Input schema (15) + Output schema (15) + Error contract (10) |
| **Side-Effects & Credentials** | 25 | Explicit declarations (15) + Allowlists (10) |
| **Execution Semantics** | 25 | Hard timeout (10) + Retry semantics (10) + Error categories (5) |
| **n8n Normalization** | 10 | Explicit defaults (5) + Expression boundaries (5) |

**≥80 points** → acceptable for human review  
**<80 points** → mechanically rejected

## Usage

### 1. Generate Contract Template

```bash
python -m contracts.validator template \
  --node-type redis \
  --semantic-class tcp_client \
  --output contracts/redis.contract.yaml
```

### 2. Fill in Contract (Before Writing Code!)

Edit `contracts/redis.contract.yaml`:

```yaml
node_type: redis
version: "1.0.0"
semantic_class: tcp_client

input_schema:
  fields:
    - name: operation
      type: string
      required: true
      enum: [get, set, delete, incr, decr, exists, expire, ttl, keys, flushdb]
    
    - name: key
      type: string
      required: true
      min_length: 1
      max_length: 512
      
  additional_properties: false  # CRITICAL: No unknown inputs
  strict: true

output_schema:
  success_fields:
    - name: result
      type: any
      description: "Operation result (type depends on operation)"
  
  error_fields:
    - name: error
      type: string
    - name: errorCategory
      type: string
  
  deterministic: true  # Same input → same output

error_categories:
  - validation      # Invalid input
  - timeout         # Operation timeout
  - network         # Connection failures
  - auth_failed     # Authentication failed
  - not_found       # Key not found
  - unknown         # Unclassified

side_effects:
  types:
    - database
  database_operations:
    - read
    - write
    - delete

credential_scope:
  credential_type: redisApi
  required: true
  host_allowlist:
    - localhost
    - redis.production.internal
  database_allowlist:
    - 0  # Redis DB index

execution_semantics:
  timeout_seconds: 30
  retry_policy: idempotent  # Safe to retry
  idempotent: true          # Operations can be retried
  transactional: false      # No multi-key transactions
  max_retries: 2
  retry_delay_seconds: 1

n8n_normalization:
  defaults_explicit: true
  expression_boundaries:
    - key
    - value
  eval_disabled: false
```

### 3. Validate Contract

```bash
# Validate single contract
python -m contracts.validator validate contracts/redis.contract.yaml

# Should output:
# ✅ ACCEPTED - Score: 95/100
# 
# 📊 Score Breakdown:
#   • Contract Completeness: 38/40
#   • Side-Effects & Credentials: 24/25
#   • Execution Semantics: 25/25
#   • n8n Normalization: 8/10
```

### 4. Implement Node (Conforms to Contract)

Now write `avidflow-back/nodes/redis.py`:

```python
class RedisNode(BaseNode):
    """
    Redis node.
    
    CONTRACT: contracts/redis.contract.yaml
    Generated: 2026-02-02
    """
    
    type = "redis"
    version = 1
    
    # CRITICAL: Properties MUST match contract input_schema
    properties = {
        "parameters": [
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "required": True,
                "options": [
                    {"name": "Get", "value": "get"},
                    {"name": "Set", "value": "set"},
                    # ... MUST match contract enum
                ]
            },
            {
                "name": "key",
                "type": NodeParameterType.STRING,
                "required": True,
                # MUST validate min_length/max_length from contract
            }
        ]
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        # MUST enforce timeout from contract
        # MUST normalize errors to contract error_categories
        # MUST NOT accept additional_properties
        # MUST produce output matching success_fields
        pass
```

### 5. Mechanical Validation

```bash
# Batch validate all contracts
python -m contracts.validator batch contracts/

# Output:
# 🔍 Found 2 contract files
# 
# ✅ Accepted: 2/2
# ❌ Rejected: 0/2
```

## Integration with Existing Pipeline

**NO CHANGES to existing GitHub node conversion!**

The contract system is **additive only**:

1. Existing `code-convert` skill generates `.py` files (as before)
2. NEW `code-validate` skill generates `.contract.yaml` + validates
3. If validation fails → reject conversion, don't proceed to PR

### Modified Pipeline Flow

```
node-normalize → source-classify → source-ingest → schema-infer → schema-build → node-scaffold
                                                                                      ↓
                              [TYPE1: code-convert] OR [TYPE2: code-implement]
                                                                                      ↓
                            *** NEW: contract-generate + contract-validate ***
                                                                                      ↓
                              test-generate → code-validate ↔ code-fix → pr-prepare
```

### New Skill: `contract-validate`

```python
# skills/contract-validate/impl.py

def execute(correlation_id: str) -> SkillResult:
    """
    Generate and validate execution contract for converted node.
    
    Hard-fail if:
    - Contract cannot be generated
    - Validation score < 80
    - Hard-fail invariants violated
    """
    contract_path = f"contracts/{node_type}.contract.yaml"
    
    # Generate contract from inferred schema
    contract = generate_contract_from_schema(schema, node_type)
    
    # Validate contract
    result = validate_contract(contract)
    
    if not result.acceptable:
        return SkillResult(
            status="FAILED",
            outputs={
                "error": "Contract validation failed",
                "score": result.score,
                "violations": result.hard_fail_violations
            }
        )
    
    # Write contract to disk
    write_contract(contract, contract_path)
    
    return SkillResult(
        status="COMPLETED",
        outputs={
            "contract_path": contract_path,
            "score": result.score
        }
    )
```

## Golden Reference: GitHub Node

See: `contracts/github.contract.yaml`

This is the **only** contract that meets the 80% bar.

Use it as the reference for:
- Input schema strictness (`additional_properties: false`)
- Output schema completeness (success + error fields)
- Error category normalization
- Side-effect declaration (explicit network destinations)
- Credential scope (host allowlist)
- Execution semantics (timeout + retry policy)
- n8n normalization (explicit defaults, expression boundaries)

## FAQs

### Q: Do I need to rewrite existing nodes?

**A: NO.** Contract system is additive. Existing nodes continue to work.

New conversions MUST have contracts. Old nodes can be migrated gradually.

### Q: What if a node scores 75%?

**A: REJECT.** Below 80% = mechanically rejected. No human review.

Fix the contract, regenerate, re-validate.

### Q: Can I set `additional_properties: true`?

**A: NO.** This is a hard-fail violation.

Unknown inputs = undefined behavior = rejection.

### Q: What about database trigger nodes?

**A: Special contract requirements:**

```yaml
side_effects:
  types:
    - database
    - stateful  # Maintains checkpoint

execution_semantics:
  timeout_seconds: 300  # Longer for polling
  delivery_semantics: at_least_once  # NEW field
  checkpoint_strategy: incremental   # NEW field
  deduplication_key: event_id        # NEW field
```

See: `docs/TRIGGER_CONTRACT_SPEC.md` (to be created)

### Q: How do I handle n8n expressions?

**A: Declare them explicitly:**

```yaml
n8n_normalization:
  expression_boundaries:
    - owner          # Can use {{ $json.owner }}
    - repository     # Can use {{ $json.repo }}
  eval_disabled: false
```

This documents which fields support dynamic evaluation.

## Next Steps

1. ✅ Contract schema defined (`contracts/node_contract.py`)
2. ✅ Validator implemented (`contracts/validator.py`)
3. ✅ GitHub golden reference (`contracts/github.contract.yaml`)
4. ⏳ Integrate into pipeline (`skills/contract-validate/`)
5. ⏳ Generate contracts for Redis, Postgres (database nodes)
6. ⏳ Generate contracts for Schedule, Webhook (trigger nodes)
7. ⏳ Update README with contract-first workflow

## References

- Contract schema: `contracts/node_contract.py`
- Validator CLI: `python -m contracts.validator --help`
- Golden reference: `contracts/github.contract.yaml`
- GitHub node impl: `avidflow-back/nodes/github.py`
