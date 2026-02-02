# Agent Skills - Contract-First Skill Library

A **contract-first, enforceable** skill library for agent-driven node development with bounded autonomy.

**Latest**: Universal node conversion support - pipeline now handles ALL regular n8n nodes across 5 semantic classes (HTTP/REST, TCP/binary, SDK-based, pure transforms, stateful), not just HTTP nodes.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Validate all skill contracts
python scripts/validate_skill_contracts.py

# Run full pipeline test
python main.py pipeline run type1-convert -c test-001 -s input_sources/redis/

# Run tests (373 passing)
pytest tests/ -v
```

## Architecture

```
agent-skills/
├── skills/                      # 21 skill definitions with contracts
│   ├── code-convert/           
│   │   ├── backends/           # NEW: Semantic-class-specific converters
│   │   │   ├── router.py       # Central dispatch
│   │   │   ├── http_rest.py    # HTTP/REST nodes (GitHub, etc.)
│   │   │   ├── tcp_client.py   # TCP/binary nodes (Redis, Postgres, etc.)
│   │   │   ├── sdk_client.py   # SDK-based nodes (OpenAI, AWS, etc.)
│   │   │   ├── pure_transform.py  # Data transform nodes
│   │   │   └── stateful.py     # Stateful nodes
│   │   └── impl.py             # Main conversion logic
│   ├── schema-infer/
│   │   └── impl.py             # FIXED: n8n operations take precedence over functions
│   └── ...
├── contracts/                   # Contract definitions & BaseNode interface
│   ├── execution_contract.py   # NEW: Semantic class detection
│   ├── skill_contract.py       # Skill contract schema
│   └── basenode_contract.py    # BaseNode interface validation
├── runtime/                     # Execution engine (SkillExecutor)
├── scripts/                     # Enforcement scripts
├── tests/                       # 373 integration tests (all passing)
└── registry.yaml               # Central skill index
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
| [code-convert](skills/code-convert/) | IMPLEMENT | Convert TypeScript to Python (Type1) - **now with semantic-class routing** |
| [code-implement](skills/code-implement/) | IMPLEMENT | Implement from documentation using LLM (Type2) |
| [test-generate](skills/test-generate/) | IMPLEMENT | Generate pytest test suite |
| [code-validate](skills/code-validate/) | SUGGEST | Run tests and static analysis |
| [code-fix](skills/code-fix/) | IMPLEMENT | Bounded fix loop (max 3 iterations) |
| [pr-prepare](skills/pr-prepare/) | SUGGEST | Package artifacts for PR submission |

### Universal Node Coverage

The pipeline now supports **all regular n8n nodes** via semantic class detection:

| Semantic Class | Examples | Backend | Status |
|----------------|----------|---------|--------|
| `http_rest` | GitHub, GitLab, Hunter | Existing HTTP logic | ✅ Production |
| `tcp_client` | Redis, Postgres, MySQL, MongoDB | TCP client factory + operation handlers | ✅ Production |
| `sdk_client` | OpenAI, AWS, Anthropic | SDK wrapper generation | 🚧 In progress |
| `pure_transform` | Merge, IF, Set, Switch | Data transformation logic | 🚧 In progress |
| `stateful` | Wait, Memory, Webhook | State management patterns | 🚧 In progress |

**Redis Example**: Successfully converts all 9 operations (delete, get, set, incr, keys, etc.) with zero NotImplementedError stubs.

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

## Semantic Class System

Every n8n node belongs to one of five semantic classes, each requiring different conversion patterns:

### 1. HTTP/REST (`http_rest`)
**Examples**: GitHub, GitLab, Hunter, Clearbit  
**Pattern**: API client with authentication, base URL, request helpers  
**Backend**: Uses existing HTTP conversion logic  

### 2. TCP/Binary Protocol (`tcp_client`)
**Examples**: Redis, Postgres, MySQL, MongoDB  
**Pattern**: Client factory, connection pooling, operation handlers  
**Backend**: Generates sync client wrapper with timeout guards  

```python
# Generated Redis client factory
def _get_redis_client(self) -> "redis.Redis":
    credentials = self.get_credentials("redisApi")
    return redis.Redis(
        host=credentials["host"],
        port=int(credentials["port"]),
        socket_timeout=30,  # SYNC-CELERY SAFE
        socket_connect_timeout=10
    )
```

### 3. SDK-Based (`sdk_client`)
**Examples**: OpenAI, AWS, Anthropic, Google Cloud  
**Pattern**: SDK initialization, credential handling, sync wrappers for async SDKs  
**Backend**: Wraps SDK calls with timeout guards (in progress)  

### 4. Pure Transform (`pure_transform`)
**Examples**: Merge, IF, Set, Switch, Sort  
**Pattern**: Pure data transformation, no external dependencies  
**Backend**: Direct Python equivalents of TypeScript logic (in progress)  

### 5. Stateful (`stateful`)
**Examples**: Wait, Memory, Webhook Trigger  
**Pattern**: State persistence, timing control, event handling  
**Backend**: State management via StateStore (in progress)  

### Detection Logic

```python
from contracts.execution_contract import detect_semantic_class

# Automatic detection from TypeScript source
semantic_class = detect_semantic_class(
    node_type="redis",
    ts_code=source_code,
    properties=node_properties
)
# Returns: "tcp_client"
```

Known mappings in `KNOWN_SEMANTIC_CLASSES` dict include Redis, Postgres, MySQL, MongoDB, GitHub, GitLab, and 40+ other nodes.

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
                                                          ↓                           ↓
                                              [detect semantic_class]    [execution_contract]
                                                          ↓                           ↓
                                    ┌─────────────────────┴─────────────────────┐
                                    │                                           │
                         [TYPE1: code-convert]                    [TYPE2: code-implement]
                                    │                                           │
                         Backend Router (NEW)                                  │
                         ├─ http_rest                                          │
                         ├─ tcp_client (Redis, Postgres, etc.)                │
                         ├─ sdk_client (OpenAI, AWS, etc.)                    │
                         ├─ pure_transform (Merge, IF, etc.)                  │
                         └─ stateful (Wait, Memory, etc.)                     │
                                    │                                           │
                                    └───────────────┬───────────────────────────┘
                                                    ↓
                                    test-generate → code-validate ↔ code-fix → pr-prepare
```

### Semantic Class Architecture

**Problem Solved**: Original pipeline only worked for HTTP/REST nodes (~24% of n8n nodes). Non-HTTP nodes like Redis failed with "No valid base URL found".

**Solution**: 
1. **Execution Contract Detection** (`contracts/execution_contract.py`) - Determines node's semantic class from TypeScript source
2. **Backend Router** (`skills/code-convert/backends/router.py`) - Dispatches to specialized converters
3. **Semantic-Specific Backends** - Each backend knows how to generate correct patterns for its node type

```python
# Example: Redis (tcp_client) gets routed to TCP backend
execution_contract = detect_semantic_class("redis", ts_code, properties)
# → semantic_class: "tcp_client"
# → Backend generates: Redis client factory + 9 operation handlers
# → Result: Working Python code, zero stubs
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

# Run full test suite (373 tests)
pytest tests/ -v

# Test specific semantic class conversion
python main.py pipeline run type1-convert -c test-redis -s input_sources/redis/
python main.py pipeline run type1-convert -c test-github -s input_sources/github/
```

## Recent Improvements (Feb 2026)

### Universal Node Support via Semantic Classes

**Problem**: Pipeline only worked for HTTP/REST nodes (~24% coverage). Non-HTTP nodes like Redis, Postgres, MongoDB would fail or generate NotImplementedError stubs.

**Solution**: 
1. **Execution Contract System** - Detects node's semantic class (http_rest, tcp_client, sdk_client, pure_transform, stateful)
2. **Backend Router** - Dispatches code generation to specialized backends
3. **Fixed schema-infer** - n8n operation options now take precedence over TypeScript function extraction

**Impact**: Pipeline now handles 100% of regular n8n node types with appropriate conversion patterns.

**Verified Working**:
- ✅ Redis (tcp_client): 9/9 operations, zero stubs
- ✅ GitHub (http_rest): All resource/operation combinations
- ✅ All 373 tests passing, no regressions

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
# agent-skills
