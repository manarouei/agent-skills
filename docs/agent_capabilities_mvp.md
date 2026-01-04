# Agent Capabilities MVP

## Executive Summary

This document describes the minimal viable changes to evolve the agent-skills repo from "skills-as-tools" (synchronous call, binary success/fail) toward "skills-as-agent-capabilities" (persistent identity, message-based interaction, multi-turn support).

**Key Constraint**: All execution remains within a single synchronous Celery task. "Long-lived" means persisted state + resumable turns, NOT daemon threads.

**Related**: See [hybrid_backbone_architecture.md](hybrid_backbone_architecture.md) for the deterministic backbone + bounded AI advisor pattern that controls when AI reasoning is invoked.

---

## 1. What Changed (Foundational)

### 1.1 New Runtime Modules

| File | Purpose | LOC |
|------|---------|-----|
| `runtime/protocol.py` | Message types: `TaskState`, `MessageType`, `AgentResponse`, `InputRequest` | ~250 |
| `runtime/state_store.py` | SQLite-backed state persistence: events, facts, summaries | ~450 |
| `runtime/adapter.py` | Hybrid adapter wrapping `SkillExecutor` for agent semantics | ~250 |

### 1.2 Extended Contracts

| File | Change |
|------|--------|
| `contracts/skill_contract.py` | Added `InteractionOutcomes` model and `interaction_outcomes` field on `SkillContract` |
| `skills/schema-infer/SKILL.md` | Added `interaction_outcomes` block declaring `input_required` as allowed intermediate state |

### 1.3 Agentified Skill

`skills/schema-infer/impl.py` - Full implementation with multi-turn flow:
- Turn 1: Validates inputs, returns `INPUT_REQUIRED` if missing `parsed_sections` or `source_type`
- Turn 2+: Resumes from `StateStore`, completes inference

---

## 2. Hybrid Model: Tool-like vs Message-driven

### 2.1 Degenerate Case (One-Shot Tool)

For simple skills that always complete in one turn:

```python
# Existing pattern - still works
result = executor.execute("node-normalize", inputs, correlation_id)
# result.status is SUCCESS or FAILED
```

The `AgentAdapter` wraps this and returns `AgentResponse(state=COMPLETED, outputs=...)`.

### 2.2 Multi-Turn Agent Pattern

For skills needing interaction:

```python
adapter = create_agent_adapter(executor)

# Turn 1 - may return INPUT_REQUIRED
response = adapter.invoke("schema-infer", {}, context_id)
if response.state == TaskState.INPUT_REQUIRED:
    # Response contains input_request with missing_fields
    # Caller provides missing data...
    
# Turn 2 - resume with additional inputs
response = adapter.invoke(
    "schema-infer",
    {"parsed_sections": {...}, "source_type": "TYPE1"},
    context_id,
    resume=True,
)
# response.state is COMPLETED
```

### 2.3 State Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                          Celery Task                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐                                               │
│  │ AgentAdapter │                                               │
│  └──────┬───────┘                                               │
│         │                                                        │
│         ▼                                                        │
│  ┌──────────────┐    INPUT_REQUIRED    ┌────────────────┐       │
│  │   Turn 1     │───────────────────►  │  StateStore    │       │
│  │  (validate)  │                      │  (SQLite)      │       │
│  └──────────────┘                      └────────────────┘       │
│                                               │                  │
│  [Celery task ends, state persisted]          │                  │
│                                               │                  │
│  ════════════════════════════════════════════════════════════   │
│                                               │                  │
│  [New Celery task, same context_id]           │                  │
│                                               ▼                  │
│  ┌──────────────┐    load state        ┌────────────────┐       │
│  │   Turn 2     │◄─────────────────────│  StateStore    │       │
│  │  (complete)  │                      │  (SQLite)      │       │
│  └──────┬───────┘                      └────────────────┘       │
│         │                                                        │
│         ▼                                                        │
│      COMPLETED                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Sync Celery Compatibility

### 3.1 How Multi-Turn Works Under Celery

1. **No long-lived threads**: Each turn is a separate Celery task invocation
2. **State persists via SQLite**: `StateStore` writes to `artifacts/{context_id}/.state.db`
3. **Resume via context_id**: Caller passes same `context_id` to continue
4. **Turn limit enforced**: `max_turns` (default 8) prevents infinite loops

### 3.2 What's NOT Allowed

- `async def` / `await` in skill implementations
- Background threads that outlive task
- HTTP calls without `timeout=`
- Event loop dependencies

### 3.3 How This Differs from "Real" Agent Runtimes

| Real Agent Runtime | Our Approach |
|-------------------|--------------|
| Agent runs continuously | Agent is stateless; state is in StateStore |
| Agent holds conversation in memory | Conversation persisted to SQLite |
| Agent can spawn background work | All work synchronous within Celery task |
| Agent identity is a running process | Agent identity is `context_id` + `StateStore` |

---

## 4. TaskState Enum (Extended from ExecutionStatus)

| State | Terminal? | Resumable? | Description |
|-------|-----------|------------|-------------|
| `PENDING` | No | No | Not started |
| `IN_PROGRESS` | No | No | Currently executing |
| `COMPLETED` | Yes | No | Success |
| `FAILED` | Yes | No | Terminal failure |
| `TIMEOUT` | Yes | No | Exceeded time limit |
| `BLOCKED` | Yes | No | Blocked by gate |
| `ESCALATED` | Yes | No | Exceeded iterations, needs human |
| `INPUT_REQUIRED` | No | **Yes** | Awaiting caller input |
| `DELEGATING` | No | **Yes** | Handed off to another agent |
| `PAUSED` | No | **Yes** | Explicitly paused |

### 4.1 Backward Compatibility

`execution_status_to_task_state()` and `task_state_to_execution_status_value()` provide bidirectional mapping. Non-terminal states map to `"blocked"` in ExecutionStatus space.

---

## 5. StateStore Design

### 5.1 Tables

| Table | Purpose | Retention |
|-------|---------|-----------|
| `context_state` | Current turn, task state, summary | Per-context |
| `conversation_events` | Append-only event log | Max 100 per context |
| `pocket_facts` | Structured facts by bucket/key | Max 50 per bucket |

### 5.2 "Pocket Facts" vs Event Log

- **Pocket Facts**: Small structured data (inputs, outputs, config). Upsert semantics.
- **Event Log**: Chronological record of what happened. Append-only, bounded.
- **Summary**: Periodic text summary of conversation state.

### 5.3 Retention Knobs

```python
MAX_EVENTS_PER_CONTEXT = 100
MAX_POCKET_FACTS_PER_BUCKET = 50
MAX_SUMMARY_SIZE_CHARS = 10000
```

---

## 6. Contract Extension: InteractionOutcomes

Skills declare multi-turn capability in SKILL.md frontmatter:

```yaml
interaction_outcomes:
  allowed_intermediate_states: [input_required, delegating]
  max_turns: 4
  supports_resume: true
  input_request_schema:
    - name: source_type
      type: string
      description: "TYPE1 or TYPE2"
      required: true
```

### 6.1 Schema

```python
class InteractionOutcomes(BaseModel):
    allowed_intermediate_states: List[IntermediateState]
    max_turns: int = 8  # Hard cap: 20
    supports_resume: bool = True
    input_request_schema: List[InputFieldSchema] = []
```

### 6.2 Runtime Enforcement

- If skill returns `INPUT_REQUIRED` but contract doesn't allow it → `BLOCKED`
- If turn exceeds `max_turns` → `ESCALATED`

---

## 7. Anti-Pattern List (What NOT to Do)

### 7.1 Agents-as-Tools Anti-Pattern

❌ **Bad**: Treating "needs input" as an error
```python
if missing_inputs:
    raise ValueError("Missing inputs")  # WRONG
```

✅ **Good**: Return structured INPUT_REQUIRED
```python
if missing_inputs:
    return AgentResponse(
        state=TaskState.INPUT_REQUIRED,
        input_request=InputRequest(missing_fields=missing),
    )
```

### 7.2 Long-Lived Process Anti-Pattern

❌ **Bad**: Background thread waiting for input
```python
def execute(ctx):
    thread = Thread(target=wait_for_input)
    thread.start()  # WRONG - outlives Celery task
```

✅ **Good**: Persist state and exit
```python
def execute(ctx):
    state_store.put_state(ctx.correlation_id, current_state)
    return AgentResponse(state=TaskState.INPUT_REQUIRED)
    # Caller invokes again with resume=True
```

### 7.3 Orchestrator-First Anti-Pattern

❌ **Bad**: Giant if/else in orchestrator deciding everything
```python
if skill == "schema-infer":
    if not has_parsed_sections:
        return "need parsed_sections"  # WRONG - orchestrator knows too much
```

✅ **Good**: Skill decides what it needs
```python
# In schema-infer/impl.py
if not inputs.get("parsed_sections"):
    return AgentResponse(
        state=TaskState.INPUT_REQUIRED,
        input_request=InputRequest(missing_fields=[...])
    )
```

### 7.4 Memory Bloat Anti-Pattern

❌ **Bad**: Append-only log without bounds
```python
events.append(event)  # Grows forever
```

✅ **Good**: Bounded retention
```python
store.append_event(...)  # Internally trims to MAX_EVENTS_PER_CONTEXT
```

---

## 8. What's Optional/Evolutionary

### 8.1 Not in MVP (Future Work)

| Feature | Status | Notes |
|---------|--------|-------|
| Agent-to-agent delegation | Deferred | `DELEGATING` state exists but no router |
| Summary generation | Deferred | Schema exists, no auto-summarization |
| Vector search for memory | Excluded | Use pocket facts instead |
| WebSocket for real-time | Excluded | Poll or webhook pattern instead |

### 8.2 Production Hardening (Implemented)

| Feature | Status | Implementation |
|---------|--------|----------------|
| Pluggable backend | ✅ Done | `STATE_STORE_BACKEND` env var (sqlite/postgres) |
| PostgresStateStore | ✅ Done | Full implementation with psycopg2 (requires `pip install psycopg2-binary`) |
| Message deduplication | ✅ Done | `message_id` tracking, `DuplicateMessageError` |
| Optimistic concurrency | ✅ Done | `context_version` CAS on updates |
| Resume token validation | ✅ Done | `generate_resume_token()`, `validate_resume_token()` in adapter |
| Sensitive data redaction | ✅ Done | `redact_sensitive()` before persistence |
| State persistence policy | ✅ Done | `StatePersistenceLevel` enum in contracts |
| Input JSON Schema validation | ✅ Done | `input_request_jsonschema` in SkillContract |
| Semantic state preservation | ✅ Done | `ResponseMetadata` model in AgentResponse |
| Contract enforcement | ✅ Done | `_validate_intermediate_state()` in adapter |
| DELEGATING rejection | ✅ Done | `ROUTER_ENABLED` flag blocks delegation without router |

### 8.3 Next Incremental Steps

1. **Agentify more skills**: `code-fix` is natural next candidate
2. **Message router**: Simple facilitator that routes `DELEGATE` messages (enables DELEGATING state)
3. **Auto-summary**: Periodic LLM summarization of event log

---

## 9. Production Deployment Guide

### 9.1 Backend Configuration

The StateStore backend is selected via environment variable:

```bash
# Development (default) - SQLite per context_id
export STATE_STORE_BACKEND=sqlite

# Production - PostgreSQL for distributed workers
export STATE_STORE_BACKEND=postgres
export DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

**Backend comparison:**

| Aspect | SQLite | PostgreSQL |
|--------|--------|------------|
| Setup | Zero-config | Requires connection string |
| Concurrency | Single writer | Multi-writer safe |
| Distribution | Single-node only | Multi-worker safe |
| Use case | Dev, testing | Production |

### 9.2 PostgreSQL Schema

When using `STATE_STORE_BACKEND=postgres`, run this migration:

```sql
-- Agent context state (main record per conversation)
CREATE TABLE agent_context_state (
    context_id VARCHAR(255) PRIMARY KEY,
    current_turn INTEGER DEFAULT 1,
    task_state VARCHAR(50) DEFAULT 'pending',
    summary TEXT,
    version INTEGER DEFAULT 1,
    resume_token VARCHAR(64),
    agent_state_detail VARCHAR(50),
    input_request_payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Conversation events (bounded append-only log)
CREATE TABLE agent_conversation_events (
    id SERIAL PRIMARY KEY,
    context_id VARCHAR(255) NOT NULL 
        REFERENCES agent_context_state(context_id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    turn_number INTEGER NOT NULL,
    agent_id VARCHAR(255),
    message_id VARCHAR(255),
    UNIQUE(context_id, message_id)
);
CREATE INDEX idx_agent_events_context 
    ON agent_conversation_events(context_id, timestamp DESC);
CREATE INDEX idx_agent_events_message 
    ON agent_conversation_events(context_id, message_id) 
    WHERE message_id IS NOT NULL;

-- Pocket facts (structured key-value store with TTL)
CREATE TABLE agent_pocket_facts (
    context_id VARCHAR(255) NOT NULL 
        REFERENCES agent_context_state(context_id) ON DELETE CASCADE,
    bucket VARCHAR(100) NOT NULL,
    key VARCHAR(255) NOT NULL,
    value JSONB NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    ttl_seconds INTEGER,
    expires_at TIMESTAMPTZ,
    PRIMARY KEY (context_id, bucket, key)
);
CREATE INDEX idx_agent_facts_bucket 
    ON agent_pocket_facts(context_id, bucket);
CREATE INDEX idx_agent_facts_expires 
    ON agent_pocket_facts(expires_at) 
    WHERE expires_at IS NOT NULL;
```

### 9.3 Concurrency & Idempotency

**Message Deduplication**: Prevents duplicate processing when messages are retried.

```python
from runtime.state_store import create_state_store, DuplicateMessageError

store = create_state_store(context_id)
try:
    store.record_message(message_id="msg-123")
except DuplicateMessageError:
    # Already processed - return cached result
    pass
```

**Optimistic Concurrency Control**: Prevents lost updates in multi-worker scenarios.

```python
from runtime.state_store import VersionConflictError

# Read current version
state = store.get_state()
current_version = state.context_version

# Update with CAS
try:
    store.put_state(new_state, expected_version=current_version)
except VersionConflictError:
    # Another worker updated - reload and retry
    pass
```

### 9.4 Resume Token Pattern

Resume tokens encode context + version for safe continuation:

```python
from runtime.state_store import generate_resume_token, validate_resume_token

# After completing a turn
token = generate_resume_token(context_id, version=3, turn=2)
# Returns: "ctx-abc:3:2"

# Before resuming
is_valid = validate_resume_token(token, store)
if not is_valid:
    # State has changed since token was issued
    raise ConflictError("State modified, please refresh")
```

### 9.5 Sensitive Data Redaction

All values are scrubbed before persistence:

```python
from runtime.state_store import redact_sensitive

# Automatic patterns redacted:
# - api_key=sk-xxx → api_key=***REDACTED***
# - Authorization: Bearer xxx → Authorization: Bearer ***REDACTED***
# - password=xxx → password=***REDACTED***
# - OpenAI-style keys (sk-*, pk-*, rk-*) → ***REDACTED***

data = {"config": {"api_key": "sk-1234567890abcdefghij"}}
safe_data = redact_sensitive(data)
# {"config": {"api_key": "***REDACTED***"}}
```

### 9.6 State Persistence Policy

Skills declare their persistence requirements:

```yaml
# In SKILL.md frontmatter
state_persistence: facts_only  # Options: none, facts_only, full_events
```

| Level | Persists | Use Case |
|-------|----------|----------|
| `none` | Nothing | Stateless one-shot skills |
| `facts_only` | Pocket facts only | Lightweight multi-turn |
| `full_events` | Facts + event log | Full audit trail |

### 9.7 Input Validation with JSON Schema

Skills can declare JSON Schema for input validation:

```yaml
# In SKILL.md frontmatter
input_request_jsonschema:
  type: object
  properties:
    correlation_id:
      type: string
    source_type:
      type: string
      enum: [TYPE1, TYPE2]
  required: [correlation_id]
```

Runtime validates inputs against schema before execution.

### 9.8 Production Anti-Patterns

#### ❌ Storing Secrets in State

```python
# WRONG - secrets persisted to disk/DB
store.put_fact("config", "api_key", os.environ["API_KEY"])
```

```python
# CORRECT - use redact_sensitive or don't store
store.put_fact("config", "api_key_hint", "sk-...last4")
```

#### ❌ Ignoring Version Conflicts

```python
# WRONG - overwrites concurrent updates
store.put_state(new_state)
```

```python
# CORRECT - use CAS
store.put_state(new_state, expected_version=current_version)
```

#### ❌ Unbounded Retries Without Dedupe

```python
# WRONG - reprocesses same message on retry
result = process(message)
```

```python
# CORRECT - dedupe on message_id
try:
    store.record_message(message.id)
    result = process(message)
except DuplicateMessageError:
    result = get_cached_result(message.id)
```

#### ❌ Resume Without Token Validation

```python
# WRONG - resumes without checking state consistency
response = adapter.invoke(skill, inputs, context_id, resume=True)
```

```python
# CORRECT - validate resume token first
if not validate_resume_token(token, store):
    raise ConflictError("State changed, please refresh")
response = adapter.invoke(skill, inputs, context_id, resume=True)
```

---

## 10. File List and Changes

### New Files

| File | Purpose |
|------|---------|
| `runtime/protocol.py` | Message types, AgentResponse, ResponseMetadata |
| `runtime/state_store.py` | Pluggable persistence (SQLite/Postgres), dedupe, CAS, redaction |
| `runtime/adapter.py` | Hybrid adapter with resume token support |
| `skills/schema-infer/impl.py` | Agentified schema inference |
| `tests/test_agent_capabilities.py` | Tests for agent capabilities (43 tests) |
| `docs/agent_capabilities_mvp.md` | This document |
| `docs/hybrid_backbone_architecture.md` | Deterministic backbone + bounded AI advisor pattern |

### Modified Files

| File | Change |
|------|--------|
| `contracts/skill_contract.py` | Added `InteractionOutcomes`, `IntermediateState`, `StatePersistenceLevel`, `input_request_jsonschema`, `SkillExecutionMode` enum |
| `contracts/__init__.py` | Export new types including `StatePersistenceLevel`, `SkillExecutionMode`, `SKILL_EXECUTION_MODES` |
| `runtime/__init__.py` | Export new modules including `RuntimeConfig`, `AdvisorOutputValidator` |
| `runtime/executor.py` | Register schema-infer implementation, added `RuntimeConfig`, `AdvisorOutputValidator`, execution mode logging |
| `skills/schema-infer/SKILL.md` | Added `interaction_outcomes`, `state_persistence`, `input_request_jsonschema` |

---

## 11. Validation Commands

```bash
# Validate skill contracts (includes new interaction_outcomes)
python3 scripts/validate_skill_contracts.py

# Run all tests including new agent capability tests
python3 -m pytest -q

# Validate sync-Celery safety
python3 scripts/validate_sync_celery_compat.py runtime/
python3 scripts/validate_sync_celery_compat.py skills/schema-infer/impl.py
```

---

## 12. Quick Reference: Using the Adapter

```python
from runtime import create_executor, create_agent_adapter, TaskState

# Create executor and adapter
executor = create_executor(repo_root)
adapter = create_agent_adapter(executor)

# Invoke skill
response = adapter.invoke("schema-infer", inputs, "my-context-id")

# Check state
if response.state == TaskState.INPUT_REQUIRED:
    # Get missing fields
    for field in response.input_request.missing_fields:
        print(f"Need: {field.name} ({field.description})")
    
    # Resume with additional inputs
    response = adapter.invoke(
        "schema-infer",
        {"parsed_sections": {...}, "source_type": "TYPE1"},
        "my-context-id",
        resume=True,
    )

elif response.state == TaskState.COMPLETED:
    print(response.outputs)

elif response.state == TaskState.FAILED:
    print(response.errors)
```
