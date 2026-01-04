# Hybrid Backbone Architecture

This document describes the "deterministic backbone + bounded AI advisor" architecture implemented in the agent-skills project.

## Overview

The system is NOT "over-agentized". It uses AI/LLM reasoning only where it adds unique value, with most pipeline stages being deterministic transforms that are auditable, reproducible, and testable.

## Layered Architecture

### A) Deterministic Orchestrator Layer (Primary Control Flow)

The orchestrator layer in `runtime/executor.py`:

- **Owns state machine and step sequencing** via `SkillExecutor.execute()`
- **Enforces hard limits**: MAX_STEPS=50, FIX_LOOP_MAX=3
- **Controls gates**: scope, trace_map, sync-celery, artifact completeness
- **Manages idempotency** for safe retries
- **Prevents auto-merge** by default (human-in-the-loop)

### B) Agent Advisor Layer (Strictly Bounded)

AI/LLM reasoning is invoked only for:

1. **Docs → structured spec extraction** (schema-infer for TYPE2 sources)
2. **Code translation/synthesis** (code-convert, code-implement)
3. **Minimal diffs for failing tests** (code-fix patch proposals)

All advisor outputs are:
- Validated by `AdvisorOutputValidator` before any side effects
- Checked for sync-celery compatibility
- Verified against scope allowlists
- Required to be JSON-serializable

### C) Validation & Enforcement Layer

- **TraceMap generation & validation** is mandatory for schema steps
- **Sync-celery compatibility** check runs on all generated code
- **Tests must pass**; never weaken tests to "make green"
- **Artifact completeness** gate verifies required outputs exist

## Skill Execution Modes

Each skill is classified into one of three modes (defined in `contracts/skill_contract.py`):

| Mode | Description | Skills |
|------|-------------|--------|
| **DETERMINISTIC** | Pure functions, templates, structured transforms. No LLM. Reproducible. | node-normalize, source-classify, source-ingest, schema-build, node-scaffold, code-validate, pr-prepare |
| **HYBRID** | Deterministic first, advisor fallback for ambiguity. | schema-infer (TS: deterministic; docs: advisor), test-generate |
| **ADVISOR_ONLY** | Requires AI reasoning for core function. Still bounded. | code-convert, code-implement, code-fix |

## Pipeline Flow (Control-Flow Diagram)

```
node-normalize        [DETERMINISTIC]
  → source-classify   [DETERMINISTIC] - lookup, no LLM
  → source-ingest     [DETERMINISTIC] - fetch/bundle
  → schema-infer      [HYBRID] - TS: deterministic parse; docs: advisor extraction
  → schema-build      [DETERMINISTIC] - build from inferred schema + trace_map
  → node-scaffold     [DETERMINISTIC] - template expansion
  → (TYPE1 code-convert) OR (TYPE2 code-implement)  [ADVISOR_ONLY]
  → test-generate     [HYBRID] - templates first, advisor fallback
  → code-validate     [DETERMINISTIC] - pytest + lint run
  → code-fix          [ADVISOR_ONLY] - bounded patch suggestions (≤3 loops)
  → pr-prepare        [DETERMINISTIC] - NO AUTO MERGE by default
```

## Bounded Autonomy Controls

### 1. Skill Execution Mode Enforcement

```python
from contracts import get_skill_execution_mode, SkillExecutionMode

mode = get_skill_execution_mode("schema-infer")  # Returns HYBRID
```

The executor logs execution mode and applies appropriate validation based on mode.

### 2. Advisor Output Validation

For HYBRID and ADVISOR_ONLY skills, outputs are validated before side effects:

- **Code outputs**: Sync-celery compatibility + syntax check
- **Schema outputs**: Evidence coverage + assumption ratio (≤30%)
- **Patch outputs**: Within allowlist scope

### 3. Fix Loop Bounds

```python
class BoundedFixLoop:
    # HARD LIMIT - cannot exceed 3
    MAX_ITERATIONS = 3
    
    def run(self, correlation_id, initial_errors):
        for i in range(self.MAX_ITERATIONS):
            # ... fix attempt ...
        return ESCALATED  # After 3 failures
```

### 4. PR Auto-Merge Prevention

```python
@dataclass
class RuntimeConfig:
    auto_merge_enabled: bool = False  # NEVER True by default
    require_human_review: bool = True  # Always require review
```

The pr-prepare skill:
- Default: Prepares PR artifacts only, NO merge
- Outputs `merge_executed=False`, `human_review_required=True`
- Auto-merge requires explicit `RuntimeConfig(auto_merge_enabled=True)`

### 5. Trace Map Requirements

Schema-infer and schema-build require `trace_map.json` with:
- Every schema field having evidence
- Max 30% ASSUMPTION entries
- Rationale for each assumption

## Required Artifacts Per Correlation ID

Every skill run produces audit trail:

| Artifact | Required For | Description |
|----------|--------------|-------------|
| `request_snapshot.json` | All | Immutable input record |
| `source_bundle/` | All | Ingested source materials |
| `inferred_schema.json` | schema-infer | Extracted schema |
| `trace_map.json` | schema-infer, schema-build | Field-to-source evidence |
| `allowlist.json` | IMPLEMENT/COMMIT | Scope patterns |
| `diff.patch` | IMPLEMENT/COMMIT | Git diff of changes |
| `validation_logs.txt` | All | pytest + lint output |
| `escalation_report.md` | On failure | Only after fix-loop max |

## Key Implementation Files

- `contracts/skill_contract.py` - SkillExecutionMode enum and mappings
- `runtime/executor.py` - SkillExecutor, AdvisorOutputValidator, RuntimeConfig
- `runtime/adapter.py` - AgentAdapter for multi-turn skills
- `tests/test_hybrid_backbone.py` - Tests for hybrid backbone behaviors

## Configuration

### RuntimeConfig

```python
from runtime import RuntimeConfig, SkillExecutor

# RuntimeConfig with safe defaults (shown explicitly)
config = RuntimeConfig(
    auto_merge_enabled=False,         # Default: no auto-merge
    require_human_review=True,        # Default: human review required
    max_steps=50,                     # Hard cap per correlation_id
    fix_loop_max=3,                   # Hard cap on fix iterations
    max_changed_files=20,             # Policy limit
    default_timeout_seconds=300,      # 5 minutes
    max_turns_per_context=8,          # Agent multi-turn limit
    max_events_per_context=100,       # StateStore event limit
)

executor = SkillExecutor(
    skills_dir=Path("skills"),
    scripts_dir=Path("scripts"),
    artifacts_dir=Path("artifacts"),
    config=config,
)
```

## Validation Commands

```bash
# All gates must pass
python3 scripts/agent_gate.py
python3 scripts/validate_skill_contracts.py
python3 scripts/validate_sync_celery_compat.py .
python3 -m pytest -q

# Trace map validation (for schema outputs)
python3 scripts/validate_trace_map.py artifacts/<id>/trace_map.json
```

## Design Principles

1. **Deterministic by default** - Use pure functions where possible
2. **Advisor is bounded** - Structured outputs, validation, no direct side effects
3. **Human-in-the-loop** - No auto-merge, review required
4. **Auditable** - Trace maps, artifacts, execution logs
5. **Testable** - Each mode has specific test coverage
6. **Fail-safe** - Escalate after bounded retries, don't loop forever
