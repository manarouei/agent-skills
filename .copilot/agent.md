# Copilot Agent Operating Rules — agent-skills

## Core constraints (non-negotiable)
1. Repo-grounded: read actual repo files before decisions (BaseNode, node registry, execution semantics).
2. Sync Celery constraint: nodes run inside one synchronous Celery task per workflow. No event-loop dependency.
3. Minimal diff: modify only files required for the current task. No refactors unrelated to the task.
4. Scope gate: all modified files must match an allowlist AND pass git-diff enforcement.
5. Traceability: any inferred schema field must have evidence in trace_map OR be explicit ASSUMPTION with VERIFY IN REPO.
6. Fix loop max=3: after 3 failed validation iterations, stop and write escalation artifacts.
7. Validation is non-bypassable: never weaken tests or skip checks to pass.
8. External calls require timeouts. No background threads/tasks that outlive node execution.
9. Retries only if safe + idempotent with dedupe key.

## Agent Capabilities Constraints (multi-turn support)
10. Max message turns per context: 8 (configurable per-skill up to 20).
11. Max persisted event log: 100 events per context (oldest trimmed).
12. Max pocket facts per bucket: 50 (oldest trimmed).
13. INPUT_REQUIRED is NOT an error: skills may pause and request input without failing.
14. State persistence required: all multi-turn state must be in StateStore, not in memory.
15. No daemon loops: "long-lived identity" is achieved via context_id + StateStore, not running processes.
16. DELEGATE state forbidden: skills MUST NOT return DELEGATING until runtime/router.py is implemented.
17. All persisted payloads MUST be redacted: use redact_sensitive() before storing facts/events.
18. Non-terminal states MUST include agent_state metadata: INPUT_REQUIRED, DELEGATING, PAUSED responses must set metadata.agent_state.
19. Resume token validation required: when resume=True with resume_token, validate before proceeding.
20. Contract enforcement: skills can only return intermediate states declared in interaction_outcomes.allowed_intermediate_states.

## When to proceed autonomously vs ask
Proceed autonomously if:
- change set is inside allowlist
- contracts/schemas validate
- tests + lint + typecheck pass
- no new dependencies
Ask for confirmation if:
- adding a new dependency
- changing BaseNode or node registration mechanisms
- modifying shared infrastructure outside node/tests/credentials/skill contracts
- expanding allowlist beyond node-scoped patterns

## Required artifacts per run
- request_snapshot.json
- source_bundle/
- inferred_schema.json
- trace_map.json (canonical schema)
- allowlist.json
- validation_logs.txt
- diff.patch
- escalation_report.md (only if escalation)
