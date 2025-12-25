# 🎯 Bounded Autonomy - Quick Start Guide

**Your New Workflow for Agent-Skills Development**

---

## What Is This?

**Bounded Autonomy** = AI coding with **safety rails** that prevent:
- ❌ Hallucinating imports/APIs that don't exist
- ❌ Breaking existing contracts/APIs
- ❌ Modifying files outside scope
- ❌ Skipping tests
- ❌ Making assumptions without asking

---

## The Three Components

```
┌─────────────────────────────────────────┐
│  📚 RULES (P0/P1/P2)                    │
│  Your bible: docs/LLM_RULES.md          │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  🤖 ENFORCEMENT                          │
│  - ContextGateSkill: Ask before code    │
│  - CodeReviewSkill: Check after code    │
│  - BoundedAutonomyAgent: Orchestrate    │
└─────────────────────────────────────────┘
              ↓
┌─────────────────────────────────────────┐
│  🖥️  ACCESS                              │
│  - make commands                         │
│  - Python CLI                            │
│  - Git hooks                             │
└─────────────────────────────────────────┘
```

---

## Your New Workflow (3 Steps)

### BEFORE Coding: Plan

```bash
# Generate a rules-enforced prompt
make prompt-A1

# OR validate you have enough context
make plan TASK="Add Redis caching to summarize skill"
```

**What this does**: Asks clarifying questions to prevent assumptions

### DURING Coding: Follow Rules

Read the rules once: `make show-rules`

**P0 (MUST follow - blocking)**:
1. **Context Gating**: Ask questions before coding (max 5)
2. **Scope Control**: Only modify allowed files
3. **No Hallucination**: Never invent imports/APIs
4. **Output Discipline**: Cite exact symbols in PRs
5. **Two-Pass Workflow**: Plan → Code → Test → Rollback plan

**P1 (SHOULD follow - warnings)**:
6. **Preserve Contracts**: No breaking API changes
7. **Strategic Docstrings**: Document all new code
8. **LLM Gateway**: All LLM calls through `LLMGatewaySkill`

**P2 (NICE to have)**:
9. **Incremental Changes**: Keep PRs under 500 lines

### AFTER Coding: Check

```bash
# Check compliance before committing
make check-compliance FILES="src/skills/summarize.py tests/unit/test_summarize.py"

# Full review (checks scope too)
make review FILES="src/skills/new.py" PLANNED="src/skills/new.py"

# Run tests
make test
```

**What this does**: Validates your code follows P0/P1/P2 rules

---

## Real Example: Adding a Feature

```bash
# 1. PLAN: Generate prompt with rules baked in
make prompt-A1
# Copy output, send to LLM with your task description

# 2. CODE: LLM follows rules, makes changes
# - Asks questions first (P0-1: Context Gating)
# - Only modifies allowed files (P0-2: Scope Control)
# - Cites exact symbols (P0-4: Output Discipline)
# - Includes tests (P0-5: Two-Pass Workflow)

# 3. CHECK: Validate compliance before commit
make check-compliance FILES="src/skills/summarize.py tests/unit/test_summarize.py"

# Output:
# ✅ Compliance Status: compliant
# 
# Files analyzed: 2
# Lines changed: 87
# P0 violations: 0 (blocking)
# P1 violations: 0 (warnings)
# P2 suggestions: 0

# 4. TEST & COMMIT
make test
git add src/skills/summarize.py tests/unit/test_summarize.py
git commit -m "feat: Add Redis caching to SummarizeSkill

Modified \`SummarizeSkill._execute()\` to check cache before
LLM call. Added \`CacheManager.get()\` and \`CacheManager.set()\`.
Updated \`test_summarize_skill.py\` with cache tests.

No breaking changes."
```

---

## The Make Commands You'll Use Daily

```bash
# PROMPT GENERATION (use these to start tasks)
make prompt-A0          # Emergency hotfix prompt
make prompt-A1          # Feature implementation prompt
make prompt-bugfix      # Bug fix prompt
make show-rules         # Read the rules
make show-templates     # See all prompt templates

# PLANNING (use before coding)
make plan TASK="Your task description"

# COMPLIANCE CHECKING (use before committing)
make check-compliance FILES="file1.py file2.py"

# FULL REVIEW (use for PRs)
make review FILES="modified_files" PLANNED="planned_files"

# TESTING
make test               # Run all tests
make dev                # Install in editable mode
```

---

## What Each Tool Does

### ContextGateSkill (Planning)

**When**: Before you write any code  
**Purpose**: Validate you have enough context  
**Command**: `make plan TASK="..."`

**Example Output**:
```
❓ Questions:
1. [CRITICAL] Which files am I allowed to modify?
2. [HIGH] Where should cache be stored? (Redis/in-memory)
3. [HIGH] What is the TTL for cached data?
4. [HIGH] What's the cache key format?
5. [HIGH] What's the cache invalidation strategy?

Status: needs_clarification
Missing: file_allowlist, cache_implementation
Can proceed: false ❌
```

### CodeReviewSkill (Checking)

**When**: After you've made changes  
**Purpose**: Validate P0/P1/P2 compliance  
**Command**: `make check-compliance FILES="..."`

**Example Output**:
```
✅ Compliance Status: compliant

Files analyzed: 2
Lines changed: 87
P0 violations: 0 (blocking)
P1 violations: 0 (warnings)  
P2 suggestions: 1

💡 P2-9: Consider breaking this into smaller PRs (currently 87 lines)
```

### BoundedAutonomyAgent (Orchestration)

**When**: Full workflow automation  
**Purpose**: Orchestrate planning + review  
**Modes**: `plan`, `review`, `validate`

**Use via Python**:
```python
from agentic_system.runtime import get_agent_registry

registry = get_agent_registry()
result = registry.run(
    agent_id="bounded_autonomy",
    input_data={
        "mode": "plan",
        "task_description": "Add caching",
        "visible_files": ["src/skills/summarize.py"]
    },
    context=context
)
```

---

## File Locations

```
docs/
├── LLM_RULES.md                    ← THE RULES (read this!)
├── LLM_TASK_TEMPLATES.md           ← 8 gold prompts
├── BOUNDED_AUTONOMY_CLI.md         ← CLI usage
└── HOW_IT_WORKS.md                 ← Detailed explanation

src/agentic_system/
├── skills/
│   ├── code_review.py              ← Compliance checker
│   └── context_gate.py             ← Context validator
├── agents/
│   └── bounded_autonomy.py         ← Orchestrator
└── cli.py                          ← Terminal commands

.github/
└── pull_request_template.md        ← PR checklist
```

---

## Integration with Your IDE

### VS Code Tasks

Add to `.vscode/tasks.json`:

```json
{
  "tasks": [
    {
      "label": "Bounded Autonomy: Check",
      "type": "shell",
      "command": "make check-compliance FILES='${file}'",
      "group": "test"
    },
    {
      "label": "Bounded Autonomy: Plan",
      "type": "shell",
      "command": "make plan TASK='${input:task}'",
      "group": "build"
    }
  ]
}
```

### Git Pre-commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
staged=$(git diff --cached --name-only --diff-filter=ACM | grep "\.py$")
if [ -n "$staged" ]; then
    make check-compliance FILES="$staged" || exit 1
fi
```

---

## Common Questions

### Q: Do I need to run checks on every file?
**A**: No, only on Python files you modified. Use `make check-compliance FILES="file1.py file2.py"`

### Q: What if I get a P0 violation?
**A**: Fix it immediately. P0 = BLOCKING. Code cannot be merged with P0 violations.

### Q: Can I skip the planning step?
**A**: Not recommended. Planning takes 30 seconds, saves hours of debugging.

### Q: What if I need to modify an extra file?
**A**: Ask first. Don't silently expand scope (P0-2 violation).

### Q: How do I know if an import exists?
**A**: If you didn't see it in the provided context, ASK. Don't guess (P0-3).

---

## Success Checklist

Before committing ANY code:

- [ ] Generated prompt with rules (`make prompt-A1`)
- [ ] Ran planning if needed (`make plan`)
- [ ] Only modified approved files (P0-2)
- [ ] No hallucinated imports (P0-3)
- [ ] Added/updated tests (P0-5)
- [ ] Checked compliance (`make check-compliance`)
- [ ] All tests pass (`make test`)
- [ ] PR description cites exact symbols (P0-4)

---

## The Mental Shift

### Before Bounded Autonomy:
```
Task → Code → Hope it works → Debug for hours → Ship
```

### With Bounded Autonomy:
```
Task → Plan → Ask questions → Code with guardrails → 
Check compliance → Ship confidently ✅
```

---

## Key Insight

**Bounded autonomy doesn't slow you down—it prevents you from going down the wrong path.**

- 30 seconds planning > 2 hours debugging
- 10 seconds checking > 1 hour fixing production
- 5 minutes reading rules > 1 day rewriting code

---

## Next Steps

1. **Read the rules**: `make show-rules`
2. **Try a prompt**: `make prompt-A1`
3. **Check a file**: `make check-compliance FILES="src/skills/summarize.py"`
4. **Read detailed guide**: `docs/HOW_IT_WORKS.md`

---

## Remember

> "The fastest way to finish is to not have to do it twice."

Bounded autonomy ensures you do it right the first time. 🎯

**Welcome to safer, faster, better AI-assisted development!** 🚀
