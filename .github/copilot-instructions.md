# Agent Skills - Copilot Instructions

You must follow the workspace policy in .copilot/agent.md and .copilot/policy.yaml.
Before coding, read .copilot/agent.md and identify applicable gates.

## FIRST: Read Policy Files

Before any task, read and follow:
- `.copilot/agent.md` - Core operating rules and constraints
- `.copilot/policy.yaml` - Execution limits and gate requirements

Never modify files outside the allowlist. Always run scripts/agent_gate.py before proposing PR-ready output.
Runtime constraint: workflows run in a single synchronous Celery task; node code must be sync-safe.

## Architecture Overview

Contract-first skill library for bounded agent autonomy. 12 skills form a pipeline:
```
node-normalize → source-classify → source-ingest → schema-infer → schema-build → node-scaffold
                                                                                      ↓
                              [TYPE1: code-convert] OR [TYPE2: code-implement]
                                                                                      ↓
                              test-generate → code-validate ↔ code-fix → pr-prepare
```

**Key directories:**
- `skills/` - SKILL.md files with YAML frontmatter contracts
- `contracts/` - Pydantic models (`SkillContract`, `SyncCeleryConstraints`)
- `runtime/executor.py` - Gate enforcement engine
- `scripts/` - Validators (trace_map, scope, sync_celery_compat)

## Non-Negotiable Constraints

### Hybrid Backbone Execution Modes

Skills are classified into execution modes. When modifying a skill, respect its mode:

| Mode | Skills | AI Usage |
|------|--------|----------|
| **DETERMINISTIC** | node-normalize, source-classify, source-ingest, schema-build, node-scaffold, code-validate, pr-prepare | None - pure functions |
| **HYBRID** | schema-infer, test-generate | Deterministic first, advisor fallback |
| **ADVISOR_ONLY** | code-convert, code-implement, code-fix | Bounded AI with validation |

All ADVISOR_ONLY outputs are validated by `AdvisorOutputValidator` before side effects.

### Sync Celery Execution (CRITICAL)

The entire workflow runs in one synchronous Celery task. Any async dependency or long-blocking call stalls the entire workflow. Generated code MUST NOT use:
- `async def` / `await`
- `asyncio`, `aiohttp`, `aiofiles`
- `threading.Thread` without `.join()`
- HTTP calls without `timeout=` parameter

Validate: `python3 scripts/validate_sync_celery_compat.py <file_or_dir>`

### Trace Map Requirement

Every inferred schema field needs evidence in `trace_map.json`. Canonical enums: `SOURCE_CODE | API_DOCS | ASSUMPTION`

Schema: `.copilot/schemas/trace_map.schema.json`

```json
{
  "correlation_id": "abc-123",
  "node_type": "ExampleNode",
  "trace_entries": [
    {
      "field_path": "operations[0].name",
      "source": "SOURCE_CODE",
      "evidence": "Function 'getName' returns string at line 120",
      "confidence": "high",
      "source_file": "path/to/node.ts",
      "line_range": "L120-L140",
      "excerpt_hash": "sha256:abc123"
    }
  ]
}
```

Max 30% ASSUMPTION entries. Validate: `python3 scripts/validate_trace_map.py <trace_map.json>`

### Scope Gate

IMPLEMENT/COMMIT skills require `allowlist.json`. Changes to BaseNode, node loader, or shared infrastructure require explicit confirmation.

### Hard Limits

- `MAX_STEPS = 50` per correlation_id
- `FIX_LOOP_MAX = 3` iterations, then escalate
- Never weaken tests to pass validation

## Required Artifacts (per correlation_id)

Every skill run must produce audit trail:
- `request_snapshot.json` - Immutable input record
- `source_bundle/` - Ingested source materials
- `inferred_schema.json` - Extracted schema
- `trace_map.json` - Field-to-source evidence (mandatory)
- `allowlist.json` - Scope patterns (IMPLEMENT/COMMIT only)
- `diff.patch` - Git diff of changes
- `validation_logs.txt` - pytest + lint output
- `escalation_report.md` - Only on failure after fix-loop max

## Skill Contract Pattern

Every `skills/*/SKILL.md` has enforced frontmatter:
```yaml
---
name: skill-name
autonomy_level: READ | SUGGEST | IMPLEMENT | COMMIT
side_effects: [fs, net, git]
timeout_seconds: 60
max_fix_iterations: 3
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
---
```

## Agent Capabilities Constraints

When implementing or modifying agent-capable skills:

1. **No async/await**: All code must be sync Celery compatible
2. **No background loops**: Long-lived identity via StateStore, not processes
3. **DELEGATE state forbidden**: Skills MUST NOT return DELEGATING until router enabled
4. **All persisted payloads must be redacted**: Use `redact_sensitive()` before storing
5. **Non-terminal states must include metadata**: Set `metadata.agent_state` for INPUT_REQUIRED/DELEGATING/PAUSED
6. **Resume token validation**: When `resume=True`, validate token before proceeding
7. **Contract enforcement**: Only return intermediate states declared in `interaction_outcomes.allowed_intermediate_states`

## Validation Commands

```bash
python3 scripts/validate_skill_contracts.py       # All 12 skills
python3 scripts/validate_trace_map.py <file>      # Trace evidence
python3 scripts/validate_sync_celery_compat.py .  # Async detection (file or dir)
python3 -m pytest -q                              # All tests must pass
```

## How to Run Gates (Pre-PR)

Before proposing any PR-ready output, run the agent gate with a correlation ID:

```bash
# Full gate check (scope + trace map + pytest)
python3 scripts/agent_gate.py --correlation-id <id>

# With explicit paths
python3 scripts/agent_gate.py --correlation-id <id> --trace-map artifacts/<id>/trace_map.json --repo-path .

# Skip pytest (faster iteration)
python3 scripts/agent_gate.py --correlation-id <id> --skip-pytest
```

The gate checks:
1. **Scope gate**: allowlist.json exists, changed files match patterns
2. **Trace map gate**: All schema fields have evidence, <30% ASSUMPTION
3. **Pytest**: All tests pass (unless --skip-pytest)

## Knowledge Base (Learning Loop)

The KB at `runtime/kb/` contains patterns for:
- `auth` - Authentication/credential patterns
- `pagination` - Cursor/offset pagination
- `ts_to_python` - TypeScript to Python idiom conversion
- `service_quirk` - Service-specific behaviors

Patterns are injected into advisor-facing skills (schema-infer, code-implement, code-convert, code-fix).

To promote artifacts to KB:
```bash
python3 scripts/promote_artifact.py list golden           # List available
python3 scripts/promote_artifact.py golden <id> --category auth  # Promote
```

## When to Ask vs Proceed

**Proceed autonomously:** Changes within allowlist, all gates pass, no new deps
**Ask first:** New dependencies, BaseNode changes, infrastructure outside skills/
