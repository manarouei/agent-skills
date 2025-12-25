# LLM-Assisted Development Rules (Bounded Autonomy)

**Version**: 1.0.0  
**Last Updated**: 2025-12-20  
**Status**: Authoritative (this document overrides verbal instructions)

---

## Purpose

This document defines **non-negotiable rules** for LLM-assisted coding in the `agent-skills` project. These rules enforce **bounded autonomy**: the LLM is a powerful tool, but operates within strict guardrails to prevent hallucinations, scope creep, and contract breakage.

---

## Rule Hierarchy

- **P0 (MUST)**: Violation blocks PR merge. Non-negotiable.
- **P1 (SHOULD)**: Strongly encouraged. Exceptions require justification.
- **P2 (NICE-TO-HAVE)**: Optional improvements.

**P0 rules override everything else.**

---

## Core Rules

### P0-1: Context Gating

**Before proposing any code changes, verify you have the required context.**

- If context is missing, ask **up to 5 clarifying questions** (prioritized by blocking severity).
- After 5 questions, if context is still incomplete: **STOP**. Output "BLOCKED: <reason>".
- Do NOT guess. Do NOT proceed with assumptions.

**Examples of required context**:
- Which files are allowed to be modified?
- Does API/function X exist? What is its signature?
- What is the current schema for data structure Y?

**Why**: Prevents hallucinated APIs and out-of-scope changes.

---

### P0-2: Scope Control

**Touch ONLY explicitly allowed files.**

- User must provide a file allowlist (e.g., "modify src/agentic_system/skills/summarize.py only").
- If no allowlist provided, ask for it (counts toward 5 questions).
- If you need to touch an additional file, **ask first**. Do not expand scope silently.

**Forbidden without explicit approval**:
- Renaming exported symbols (functions, classes, endpoints)
- Changing Pydantic model fields (breaks contracts)
- Modifying HTTP endpoint paths or methods
- Altering Celery task signatures
- Changing database schemas or persisted data formats

**Why**: Prevents breaking changes and maintains contract stability.

---

### P0-3: No Hallucination

**Never claim a file, function, class, or API exists unless it is explicitly stated in the provided context.**

- If you reference a symbol, **cite its exact name and file path**.
- If you're unsure whether something exists, **ask** (counts toward 5 questions).

**Bad**: "We can call `workflow_service.execute()` to run the workflow."  
**Good**: "Does `WorkflowService.execute()` exist in `src/agentic_system/services/workflow.py`? If so, what is its signature?"

**Why**: Prevents undefined name errors and import failures.

---

### P0-4: Output Discipline

**All code change proposals MUST follow this format (in order):**

1. **PLAN** (if not already approved)
   - Steps to implement
   - Required files/symbols (with citations)
   - Assumptions
   - Blockers (if any)

2. **PATCHES** (file-by-file)
   - Minimal diffs for each file
   - Preserve existing code structure
   - Include file path as header

3. **TESTS**
   - New test cases for new functionality
   - Updated test cases for modified functionality
   - Regression tests for bug fixes

4. **RISKS & ROLLBACK**
   - What could break (who is affected)
   - How to detect breakage
   - How to roll back (`git revert` + manual steps)

5. **SYMBOLS MODIFIED**
   - Exact citations: `ClassName.method_name` in `path/to/file.py`

**Why**: Enforces reviewability, testability, and safe deployment.

---

### P0-5: Two-Pass Workflow

Use this workflow for non-trivial changes:

**Pass 1 (A0)**: Planning + Questions
- Input: User request + visible context
- Output: Plan, questions (max 5), assumptions, blockers
- **NO CODE GENERATION** in this pass

**Pass 2 (A1)**: Implementation + Tests
- Input: Approved plan + file allowlist
- Output: Patches, tests, risks, rollback, symbol citations
- **Code generation allowed** once plan is approved

**Why**: Separates planning from implementation; reduces wasted effort on wrong assumptions.

---

### P1-6: Preserve Contracts

**Public APIs are contracts. Breaking changes require migration plans.**

Public API surfaces in this project:
- **Pydantic models** (Input/Output schemas): Field renames/removals are breaking
- **FastAPI endpoints**: Path or method changes are breaking
- **Celery tasks**: Signature changes are breaking
- **Skill.execute() signatures**: Input/output model changes are breaking
- **Agent.run() signatures**: Input/output model changes are breaking

**If you must make a breaking change**:
1. Document the break in RISKS section
2. Provide migration path (e.g., "add new field, deprecate old field")
3. Update semantic version (bump major version)
4. Get explicit approval

**Why**: Downstream consumers (API clients, other agents, scheduled jobs) rely on contracts.

---

### P1-7: Strategic Docstrings

**Add/update docstrings at architectural choke points.**

Choke points in this codebase:
- `Skill.execute()` implementations (document side effects, idempotency, timeout behavior)
- `Agent.run()` implementations (document step orchestration)
- Registry methods (`SkillRegistry.execute()`, etc.)
- Queue operations (if applicable: `QueueService.publish()`, message handlers)
- LLM Gateway Skill (document budget controls, retry semantics)

**Docstring template**:
```python
"""
One-line summary.

Context: Why this exists, what problem it solves.
Contract: Input/output types, side effects (read-only/idempotent/stateful).
Invariants: What must always be true (e.g., "budget checked before API call").
Edge cases: Nulls, empty lists, timeouts.

Example:
    >>> result = skill.execute(input_data, context)
    >>> assert result["status"] == "success"
"""
```

**Why**: Documents runtime contracts directly in code; reduces context-gathering overhead.

---

### P1-8: LLM Gateway Enforcement

**ALL Anthropic API calls MUST go through `LLMGatewaySkill`.**

Direct API usage (e.g., `httpx.post("https://api.anthropic.com/...")`) is **forbidden** unless:
1. You are modifying `LLMGatewaySkill` itself, OR
2. You have explicit approval with documented rationale.

**Correct pattern**:
```python
from agentic_system.runtime import get_skill_registry

skill_registry = get_skill_registry()
result = skill_registry.execute(
    name="llm.anthropic_gateway",
    input_data={
        "messages": [{"role": "user", "content": "..."}],
        "max_tokens": 100,
        "budget": {"max_cost_usd": 0.01}
    },
    context=execution_context
)
```

**Why**: Centralized budget controls, logging, retry logic, observability.

---

### P2-9: Incremental Changes

**Prefer small, reviewable PRs.**

- Aim for <500 lines changed per PR.
- Large refactors should be staged across multiple PRs.
- Each PR should have a single, clear purpose.

**Why**: Easier to review, test, and roll back.

---

## Context Requirements by Task Type

### Bug Fix
- Required: Bug description, error trace, reproduction steps
- Optional: Related PRs, recent changes to affected file

### New Feature
- Required: Feature description, acceptance criteria, affected files
- Optional: Similar existing features (for pattern reference)

### Refactor
- Required: Refactor goal, files to change, contract preservation rules
- Optional: Performance benchmarks (if optimization)

### New Skill
- Required: Skill name, purpose, side effect type (read-only/idempotent/stateful), timeout requirement
- Optional: Dependencies on other skills

### New Agent
- Required: Agent name, workflow steps, input/output models, step limit
- Optional: Skills the agent will call

---

## Uncertainty Behavior

**If you encounter any of the following, STOP and ask:**

1. **Missing file/symbol**: "Does `X` exist? If so, where?"
2. **Unclear requirement**: "Should this feature do A or B?"
3. **Ambiguous contract**: "Is `field_name` required or optional?"
4. **Hidden dependency**: "Does this code depend on service X being available?"
5. **Undefined scope**: "Which files am I allowed to modify?"

**After 5 questions, if still unclear**: Output "BLOCKED: <reason>" and wait for user input.

---

## Enforcement Mechanisms

1. **PR Template**: Checklist includes P0 compliance items.
2. **Code Review**: Reviewers check for hallucinations, scope creep, contract breaks.
3. **Automated Tests**: CI fails if imports are broken or tests don't pass.
4. **Gold Prompts**: Standard prompts (see `/docs/LLM_TASK_TEMPLATES.md`) enforce these rules.
5. **Bounded Autonomy Agent**: Automated validation of changes against rules.

---

## Examples

### ✅ Good: Context-gated planning
```
User: "Add a cache to the summarize skill."
LLM: "I see SummarizeSkill in src/agentic_system/skills/summarize.py. 
      Questions before proceeding:
      1. What should be cached? (input text, output summary, or both?)
      2. Where should cache be stored? (Redis, in-memory, filesystem?)
      3. What is the cache TTL?
      4. Which files am I allowed to modify?
      After you answer, I'll provide a plan."
```

### ❌ Bad: Scope creep without asking
```
User: "Add a cache to the summarize skill."
LLM: "I'll add a CacheService class, modify summarize.py, update main.py 
      to initialize the cache, and add cache.py..."
[Violates P0-2: expanded scope without asking]
```

### ✅ Good: Symbol citation
```
Modified `SummarizeSkill._execute()` in src/agentic_system/skills/summarize.py
to call `CacheService.get()` before LLM Gateway.
```

### ❌ Bad: Hallucinated API
```
Call workflow_service.execute_async() to run the workflow.
[Violates P0-3: execute_async not proven to exist]
```

---

## Terminal Commands

Access bounded autonomy features via CLI:

```bash
# Validate code changes against rules
make validate-changes

# Run bounded autonomy agent on a file
python -m agentic_system.cli review --file src/path/to/file.py

# Check P0/P1/P2 compliance
python -m agentic_system.cli check-compliance --pr-files "file1.py,file2.py"

# Generate A0 plan
python -m agentic_system.cli plan --task "Add caching to summarize skill"

# Validate context before coding
python -m agentic_system.cli validate-context --files "file1.py,file2.py"
```

---

## Revision History

| Version | Date       | Changes                              |
|---------|------------|--------------------------------------|
| 1.0.0   | 2025-12-20 | Initial bounded autonomy rules       |

---

**When in doubt, ask. When still in doubt after 5 questions, stop.**
