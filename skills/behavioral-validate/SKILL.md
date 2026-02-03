---
name: behavioral-validate
autonomy_level: READ
side_effects: []
timeout_seconds: 60
max_fix_iterations: 0
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
---

# Behavioral Validate Skill

Validates generated code for **behavioral correctness**, not just syntactic validity.

## Purpose

This skill implements the four behavioral validation gates that ensure generated code
actually works like the source implementation, not just looks correct.

## The Four Gates

### 1. NO-STUB GATE (Critical)

Rejects any generated code containing:
- `# TODO: Implement`
- `raise NotImplementedError`
- `response = {}`
- `pass` (as sole handler body)
- Empty method bodies

**Rationale**: TYPE1 conversion must produce complete, working code. Any placeholder
indicates failed extraction.

### 2. HTTP PARITY GATE

Verifies that generated code makes the same HTTP calls as the golden implementation:
- Same HTTP methods (GET/POST/PUT/DELETE)
- Same endpoint patterns
- Same authentication headers
- Same query parameter construction

**Rationale**: HTTP calls are the observable behavior of a node. Different calls = broken node.

### 3. SEMANTIC DIFF GATE

Compares AST structure between generated and golden:
- Same class methods (by name)
- Same parameter handling patterns
- Same control flow structure (if/else branches)
- Same return patterns

**Rationale**: Structural similarity indicates semantic similarity.

### 4. CONTRACT ROUND-TRIP GATE

Verifies that the generated code satisfies its own contract:
- Parse code → extract schema
- Compare extracted schema with input schema
- Flag any operations in schema not implemented in code
- Flag any code methods not in schema

**Rationale**: Schema and code must agree on what the node does.

## Inputs

```yaml
correlation_id: str                    # Tracking ID
generated_code: str                    # Generated Python code
golden_impl: dict                      # From golden-extract skill
node_schema: dict                      # From schema-infer skill
strict_mode: bool                      # If true, any gate failure = hard fail
```

## Outputs

```yaml
validation_passed: bool
gate_results:
  no_stub:
    passed: bool
    violations: list[str]
  http_parity:
    passed: bool
    missing_calls: list[str]
    extra_calls: list[str]
  semantic_diff:
    passed: bool
    diff_score: float                  # 0.0 = identical, 1.0 = completely different
    structural_differences: list[str]
  contract_roundtrip:
    passed: bool
    unimplemented_operations: list[str]
    undeclared_methods: list[str]
errors: list[str]
```

## Execution Mode

**DETERMINISTIC** - Pure validation, no AI. All checks are regex/AST based.

## Integration

This skill is called:
1. After code-convert for TYPE1 conversions
2. After code-implement for TYPE2 conversions
3. As a gate in agent_gate.py before PR generation

## Hard-Fail Conditions

In strict mode, ANY gate failure causes immediate FAILED state.
In non-strict mode, validation_passed is false but state is COMPLETED.
