# Bounded Autonomy Agent - Behavior Guide

This guide demonstrates how the bounded autonomy agent responds to different inputs and scenarios. Use this as a reference to understand what to expect from each agent mode.

## Table of Contents
- [Context Gate (Plan Mode)](#context-gate-plan-mode)
- [Code Review Mode](#code-review-mode)
- [Compliance Check Mode](#compliance-check-mode)
- [Understanding Exit Codes](#understanding-exit-codes)

---

## Context Gate (Plan Mode)

The Context Gate validates that you have enough context before starting work. It enforces P0-1: "Always ask for required context".

### Scenario 1: Simple Task with Proper Context ✅

**Command:**
```bash
make plan TASK="Add a simple logging statement to summarize skill" \
  FILES="src/agentic_system/skills/summarize.py"
```

**Input Analysis:**
- Task: Simple modification (add logging)
- Files specified: Yes
- Context needed: Minimal

**Output:**
```
Status: READY
Can Proceed: ✅ Yes

ASSUMPTIONS:
  - Working with files: src/agentic_system/skills/summarize.py
  - No breaking changes allowed (P1-6)
  - Tests will be added/updated (P0-5)
  - All LLM calls will go through LLMGatewaySkill (P1-8)

REQUIRED FILES:
  - src/agentic_system/skills/*.py

✅ Ready to proceed with implementation!
```

**Behavior:** Agent approves immediately because:
- File allowlist is provided
- Task is straightforward
- No sensitive areas touched (DB, security, APIs)

---

### Scenario 2: Database Task Without Context ❌

**Command:**
```bash
make plan TASK="Add database migration for new user authentication table"
```

**Input Analysis:**
- Task: Database + security related
- Files specified: No
- Context needed: Critical (schema, security model)

**Output:**
```
Status: NEEDS_CLARIFICATION
Can Proceed: ❌ No

QUESTIONS (4):

  Q1 [CRITICAL]:
      Which files am I allowed to modify for this task?
      Reason: P0-2 Scope Control: Need explicit file allowlist

  Q2 [HIGH]:
      What are the exact signatures of the APIs/functions I need to use?
      Reason: P0-3 No Hallucination: Need to verify APIs exist

  Q3 [CRITICAL]:
      What is the current database schema? Are there existing migrations?
      Reason: Database changes require schema knowledge

  Q4 [CRITICAL]:
      What is the current security model (authentication, authorization)?
      Reason: Security changes require understanding current posture

MISSING CONTEXT:
  - file_allowlist
  - api_signatures
  - database_schema
  - security_model

❌ Answer questions before proceeding.
```

**Behavior:** Agent blocks work because:
- No file allowlist (P0-2 violation)
- Database keyword triggers schema question
- Authentication keyword triggers security question
- Multiple critical questions raised

**How to fix:**
```bash
# Provide files and answer the questions
make plan TASK="Add database migration for new user authentication table" \
  FILES="migrations/001_add_auth.sql,src/models/user.py"
  
# Then provide context in your IDE or via comments
```

---

### Scenario 3: Cache Implementation ⚠️

**Command:**
```bash
make plan TASK="Add Redis cache to improve performance" \
  FILES="src/agentic_system/skills/summarize.py"
```

**Input Analysis:**
- Task: Cache implementation
- Files specified: Yes
- Context needed: Implementation details

**Output:**
```
Status: NEEDS_CLARIFICATION
Can Proceed: ❌ No

QUESTIONS (1):

  Q1 [HIGH]:
      Where should the cache be stored (Redis, in-memory, filesystem)? What is the TTL?
      Reason: Implementation details needed

MISSING CONTEXT:
  - cache_implementation

ASSUMPTIONS:
  - Working with files: src/agentic_system/skills/summarize.py
  - No breaking changes allowed (P1-6)
  - Tests will be added/updated (P0-5)

❌ Answer questions before proceeding.
```

**Behavior:** Agent asks for details because:
- "cache" keyword detected
- Need to know storage location and TTL
- Even though files are provided, implementation details missing

**How to provide context:**
```bash
# Include cache details in your task description:
make plan TASK="Add Redis cache with 1 hour TTL stored in redis://localhost:6379" \
  FILES="src/agentic_system/skills/summarize.py"
```

---

### Scenario 4: API Call Without Verification 🚫

**Command:**
```bash
make plan TASK="Call the new process_data function from external library" \
  FILES="src/agentic_system/skills/summarize.py"
```

**Input Analysis:**
- Task: Call external API
- Files specified: Yes
- Context needed: API signature (hallucination prevention)

**Output:**
```
Status: NEEDS_CLARIFICATION
Can Proceed: ❌ No

QUESTIONS (1):

  Q1 [HIGH]:
      What are the exact signatures of the APIs/functions I need to use?
      Reason: P0-3 No Hallucination: Need to verify APIs exist

MISSING CONTEXT:
  - api_signatures

ASSUMPTIONS:
  - Working with files: src/agentic_system/skills/summarize.py
  - No breaking changes allowed (P1-6)
  - Tests will be added/updated (P0-5)

❌ Answer questions before proceeding.
```

**Behavior:** Agent enforces P0-3 (No Hallucination):
- "call" keyword triggers API check
- Must verify function exists before use
- Prevents importing non-existent functions

**How to provide context:**
```python
# Open the library file first to verify the signature:
# src/external_lib.py shows:
#   def process_data(input: str, timeout: int = 30) -> dict

# Then in your task or comment:
# "Call process_data(input, timeout) from external_lib"
```

---

## Code Review Mode

The Code Review agent checks P0/P1/P2 compliance on changed files.

### Scenario 5: Code Without Tests ❌

**Command:**
```bash
make review FILES="src/agentic_system/config/settings.py,src/agentic_system/cli.py"
```

**Output:**
```
❌ 2 P0 violations (BLOCKING)

NEXT STEPS:
FIX P0 VIOLATIONS (blocking):
  - [P0-5] No test file modified for src/agentic_system/config/settings.py
  - [P0-5] No test file modified for src/agentic_system/cli.py

Recommendations:
  - Add/update tests in tests/unit/test_cli.py
  - Add/update tests in tests/unit/test_settings.py
```

**Behavior:** Detects missing tests (P0-5)

**How to fix:**
```bash
# Create or update test files, then:
make review FILES="src/agentic_system/config/settings.py,\
src/agentic_system/cli.py,\
tests/unit/test_settings.py,\
tests/unit/test_cli.py"
```

---

### Scenario 6: Compliant Code ✅

**Command:**
```bash
make review FILES="src/agentic_system/config/settings.py,\
src/agentic_system/cli.py,\
tests/unit/test_settings.py,\
tests/unit/test_cli.py"
```

**Output:**
```
✅ No violations found

All P0/P1/P2 rules satisfied:
  ✓ P0-5: Tests included
  ✓ No hallucinated imports
  ✓ Scope controlled
```

**Behavior:** Passes when tests are included

---

## Compliance Check Mode

Direct compliance check without agent orchestration.

### Scenario 7: Full Compliance Check ✅

**Command:**
```bash
make check-compliance FILES="src/agentic_system/config/settings.py,\
src/agentic_system/cli.py,\
tests/unit/test_settings.py,\
tests/unit/test_cli.py"
```

**Output:**
```
Status: COMPLIANT
Files Modified: 4
Lines Changed: ~5

✅ All checks passed! Ready to merge.
```

**Behavior:** Comprehensive check of all P0/P1/P2 rules

---

## Understanding Exit Codes

The bounded autonomy system uses exit codes to communicate status:

| Exit Code | Meaning | When It Happens |
|-----------|---------|-----------------|
| 0 | Success | Context is complete, no violations |
| 1 | Needs clarification | Context gate has questions |
| 2 | Violations found | P0/P1/P2 violations detected |

### Using Exit Codes in CI/CD

```bash
# In GitHub Actions or GitLab CI:
make check-compliance FILES="$CHANGED_FILES" || exit 1

# This will fail the build if there are violations
```

---

## Common Patterns

### Pattern 1: Start with Context Gate

**Workflow:**
```bash
# 1. Validate you have context
make plan TASK="Add feature X" FILES="src/feature.py"

# 2. If questions, answer them and retry
# 3. Once READY, proceed with implementation
```

### Pattern 2: Review Before Commit

**Workflow:**
```bash
# After making changes:
make review FILES="$(git diff --name-only HEAD)"

# Fix any violations
# Re-review until clean
```

### Pattern 3: Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

CHANGED_FILES=$(git diff --cached --name-only | tr '\n' ',')
make check-compliance FILES="$CHANGED_FILES"
```

---

## Trigger Words Reference

The context gate looks for specific keywords to determine what questions to ask:

### File Allowlist Triggers
- modify, change, update, add

### API Signature Triggers
- call, use, invoke, execute

### Schema Triggers
- model, schema, field, contract, api

### Database Triggers
- database, migration, schema, table, sql

### Security Triggers
- security, auth, permission, access

### Cache Triggers
- cache

---

## Tips for Success

### ✅ DO:
- Always specify FILES when you know what to modify
- Include test files in your file list
- Be specific in task descriptions
- Answer all critical questions before proceeding

### ❌ DON'T:
- Skip the context gate
- Ignore P0 violations
- Commit without running review
- Hallucinate API signatures

---

## Testing the Agent

You can test the agent's behavior with any task:

```bash
# Simple task
make plan TASK="Fix typo in README" FILES="README.md"

# Complex task
make plan TASK="Refactor authentication system with OAuth2"

# Cache task
make plan TASK="Add Redis cache with 5 min TTL" FILES="src/api.py"
```

Watch how the agent responds to different keywords and contexts!

---

## Next Steps

- Read [HOW_IT_WORKS.md](./HOW_IT_WORKS.md) for architecture details
- Read [QUICK_START.md](./QUICK_START.md) for daily workflow
- See [LLM_RULES.md](./LLM_RULES.md) for complete P0/P1/P2 rules
