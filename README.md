# Agent Skills - Contract-First Skill Library

A **contract-first, enforceable** skill library for agent-driven node development with bounded autonomy.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Validate all skill contracts
python scripts/validate_skill_contracts.py

# Run tests
pytest tests/ -v
```

## Architecture

```
agent-skills/
├── skills/           # 12 skill definitions with contracts
├── contracts/        # Contract definitions & BaseNode interface
├── runtime/          # Execution engine (SkillExecutor)
├── scripts/          # Enforcement scripts
├── tests/            # Integration tests
└── registry.yaml     # Central skill index
```

## Skills

| Skill | Autonomy | Description |
|-------|----------|-------------|
| [node-normalize](skills/node-normalize/) | READ | Normalize node names and generate correlation IDs |
| [source-classify](skills/source-classify/) | READ | Classify source as Type1 (TypeScript) or Type2 (documentation) |
| [source-ingest](skills/source-ingest/) | READ | Fetch and bundle source materials |
| [schema-infer](skills/schema-infer/) | SUGGEST | Extract operations, parameters, credentials (**requires trace_map**) |
| [schema-build](skills/schema-build/) | SUGGEST | Build BaseNode-compliant schema |
| [node-scaffold](skills/node-scaffold/) | IMPLEMENT | Generate Python class skeleton |
| [code-convert](skills/code-convert/) | IMPLEMENT | Convert TypeScript to Python (Type1) |
| [code-implement](skills/code-implement/) | IMPLEMENT | Implement from documentation using LLM (Type2) |
| [test-generate](skills/test-generate/) | IMPLEMENT | Generate pytest test suite |
| [code-validate](skills/code-validate/) | SUGGEST | Run tests and static analysis |
| [code-fix](skills/code-fix/) | IMPLEMENT | Bounded fix loop (max 3 iterations) |
| [pr-prepare](skills/pr-prepare/) | SUGGEST | Package artifacts for PR submission |

## Execution Modes (Hybrid Backbone)

Skills are classified into execution modes that determine how AI is used:

| Mode | Description | Skills |
|------|-------------|--------|
| **DETERMINISTIC** | Pure functions, no LLM. Reproducible. | node-normalize, source-classify, source-ingest, schema-build, node-scaffold, code-validate, pr-prepare |
| **HYBRID** | Deterministic first, advisor fallback | schema-infer, test-generate |
| **ADVISOR_ONLY** | Requires AI reasoning. Still bounded. | code-convert, code-implement, code-fix |

```python
from contracts import get_skill_execution_mode, SkillExecutionMode

mode = get_skill_execution_mode("schema-infer")  # Returns SkillExecutionMode.HYBRID
```

See [docs/hybrid_backbone_architecture.md](docs/hybrid_backbone_architecture.md) for details.

## Contract-First Design

Every skill has enforced contracts in YAML frontmatter:

```yaml
---
name: skill-name
version: "1.0.0"
autonomy_level: READ | SUGGEST | IMPLEMENT | COMMIT
side_effects: [fs, net, git]
timeout_seconds: 60
max_fix_iterations: 3
input_schema: {...}
output_schema: {...}
required_artifacts: [...]
failure_modes: [timeout, parse_error]
depends_on: [other-skill]
---
```

## Enforcement Gates

### Trace Map Gate (schema-infer)
- Every schema field must have documented source
- Max 30% ASSUMPTION entries allowed
- Run: `python scripts/validate_trace_map.py trace_map.yaml`

### Scope Gate (IMPLEMENT+ skills)
- File operations limited to allowlist
- Forbidden: `base.py`, `__init__.py`, `pyproject.toml`
- Run: `python scripts/enforce_scope.py CORRELATION_ID --check-git`

## Pipeline Flow

```
node-normalize → source-classify → source-ingest → schema-infer → schema-build → node-scaffold
                                                                                      ↓
                                              [TYPE1: code-convert] OR [TYPE2: code-implement]
                                                                                      ↓
                                              test-generate → code-validate ↔ code-fix → pr-prepare
```

## Runtime

```python
from runtime import create_executor, BoundedFixLoop, ExecutionStatus

# Create executor
executor = create_executor(repo_root)

# Execute a skill
result = executor.execute(
    skill_name="schema-infer",
    inputs={"correlation_id": "ABC123", "source_bundle": {...}},
    correlation_id="ABC123",
)

# Bounded fix loop
fix_loop = BoundedFixLoop(executor, max_iterations=3)
result = fix_loop.run(correlation_id, initial_errors)
if result.status == ExecutionStatus.ESCALATED:
    print("Human review required")
```

## BaseNode Contract

Generated nodes must implement the BaseNode interface from `/home/toni/n8n/back/nodes/base.py`. See `contracts/BASENODE_CONTRACT.md` for details.

## Validation

```bash
# Validate all skill contracts
python scripts/validate_skill_contracts.py

# Validate a trace map
python scripts/validate_trace_map.py artifacts/ABC123/trace_map.yaml

# Validate sync-Celery compatibility
python scripts/validate_sync_celery_compat.py src/

# Run tests
pytest tests/ -v
```

## Runtime Reality: Sync Celery Execution Constraint

**CRITICAL**: All skills execute within a single synchronous Celery task. This has binding implications for code generation:

### Constraints Enforced

| Constraint | Reason |
|------------|--------|
| No `async def` | Blocks Celery worker |
| No `await` | Requires async context unavailable |
| No `asyncio`/`aiohttp` | Async-only libraries |
| No `threading.Thread` without `.join()` | Orphan threads |
| HTTP calls must have `timeout=` | Prevents indefinite blocking |

### Contract Field

All SKILL.md files include:

```yaml
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: true
  forbids_background_tasks: true
```

### Runtime Gate

The `SyncCeleryGate` in `runtime/executor.py` validates generated code for code-implement, code-convert, and node-scaffold skills. Violations emit a structured artifact:

```json
{
  "gate": "sync_celery_compatibility",
  "passed": false,
  "violations": [{"line": 5, "pattern": "async_def", ...}],
  "remediation": ["Replace async def with def", ...]
}
```

### CLI Validation

```bash
# Check file
python scripts/validate_sync_celery_compat.py path/to/file.py

# Check directory (recursive)
python scripts/validate_sync_celery_compat.py src/

# Strict mode (warnings as errors)
python scripts/validate_sync_celery_compat.py --strict src/

# JSON output
python scripts/validate_sync_celery_compat.py --json report.json src/
```

## License

MIT

## Related

- [BaseNode Contract](contracts/BASENODE_CONTRACT.md)
- [Skill Contract Schema](contracts/skill_contract.py)
- [Hybrid Backbone Architecture](docs/hybrid_backbone_architecture.md)
- [Agent Capabilities MVP](docs/agent_capabilities_mvp.md)
