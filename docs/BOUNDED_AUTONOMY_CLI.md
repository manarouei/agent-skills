# Bounded Autonomy CLI Guide

Complete guide for using the bounded autonomy system from the terminal.

## Overview

The bounded autonomy system enforces P0/P1/P2 rules to prevent LLM hallucinations, scope creep, and contract breakage. Access all features via the CLI:

```bash
python -m agentic_system.cli <command> [options]
```

Or use Make shortcuts:

```bash
make <command> [VARIABLES]
```

---

## Quick Start

### 1. Generate a Planning Prompt (A0)

```bash
# Using CLI
python -m agentic_system.cli prompt --template A0 --task "Add caching to summarize skill"

# Using Make
make prompt-A0
```

Copy the output and paste into Copilot Chat.

### 2. Generate an Implementation Prompt (A1)

```bash
# Using CLI
python -m agentic_system.cli prompt --template A1 \
  --plan plan.txt \
  --files "src/agentic_system/skills/summarize.py,tests/unit/test_summarize_skill.py"

# Using Make
make prompt-A1
```

### 3. Check Code Compliance

```bash
# Using CLI
python -m agentic_system.cli check-compliance \
  --pr-files "src/agentic_system/skills/new_skill.py,tests/unit/test_new_skill.py" \
  --planned-files "src/agentic_system/skills/new_skill.py,tests/unit/test_new_skill.py" \
  --pr-description "Added NewSkill for XYZ"

# Using Make
make check-compliance FILES="src/agentic_system/skills/new_skill.py,tests/unit/test_new_skill.py"
```

Output:
```
============================================================
BOUNDED AUTONOMY COMPLIANCE CHECK
============================================================

Status: COMPLIANT
Files Modified: 2
Lines Changed: ~120

✅ All checks passed! Ready to merge.
```

---

## Commands Reference

### `prompt` - Generate Prompt Templates

Generate gold prompts with built-in guardrails.

**Syntax:**
```bash
python -m agentic_system.cli prompt --template <name> [options]
```

**Templates:**
- `A0` - Planning + questions (no code)
- `A1` - Implementation + tests
- `A1-reliability` - Reliability/security/database changes
- `bugfix` - Quick bug fix
- `new-skill` - New skill creation
- `new-agent` - New agent creation
- `refactor` - Code refactoring
- `docs` - Documentation update

**Examples:**

```bash
# Generate A0 planning prompt
python -m agentic_system.cli prompt --template A0 \
  --task "Add Redis caching to summarize skill"

# Generate A1 implementation prompt
python -m agentic_system.cli prompt --template A1 \
  --plan "approved_plan.txt" \
  --files "src/skills/summarize.py,tests/unit/test_summarize.py"

# Generate bugfix prompt
python -m agentic_system.cli prompt --template bugfix \
  --bug "Timeout in LLM Gateway after 30s" \
  --error "$(cat error.log)"

# Generate new skill prompt
python -m agentic_system.cli prompt --template new-skill \
  --name "cache_skill" \
  --purpose "Cache LLM responses in Redis" \
  --side-effects "stateful" \
  --timeout 30

# Generate new agent prompt
python -m agentic_system.cli prompt --template new-agent \
  --name "code_reviewer" \
  --purpose "Review code for P0/P1/P2 compliance" \
  --steps "1. Read files 2. Check rules 3. Generate report"
```

---

### `check-compliance` - Check P0/P1/P2 Rules

Validate code changes against bounded autonomy rules.

**Syntax:**
```bash
python -m agentic_system.cli check-compliance \
  --pr-files "file1.py,file2.py" \
  [--planned-files "file1.py"] \
  [--pr-description "PR text"]
```

**Options:**
- `--pr-files` (required): Comma-separated list of modified files
- `--planned-files` (optional): Comma-separated list of planned files (for scope check)
- `--pr-description` (optional): PR description text (for symbol citation check)

**Output:**
- ✅ `compliant`: All checks passed
- ⚠️ `warnings`: P1 violations (recommended fixes)
- ❌ `violations`: P0 violations (BLOCKING)

**Example:**
```bash
python -m agentic_system.cli check-compliance \
  --pr-files "src/agentic_system/skills/cache.py,tests/unit/test_cache_skill.py" \
  --planned-files "src/agentic_system/skills/cache.py,tests/unit/test_cache_skill.py" \
  --pr-description "Added CacheSkill with get/set methods. Modified \`CacheSkill._execute()\` in src/agentic_system/skills/cache.py"
```

**Checks Performed:**
- **P0-2**: Scope control (unplanned files)
- **P0-3**: Hallucination detection (suspicious imports)
- **P0-4**: Symbol citations in PR description
- **P0-5**: Test coverage (tests for code files)
- **P1-6**: Contract preservation (API/model changes)
- **P1-7**: Docstrings (new functions/classes)
- **P1-8**: LLM gateway enforcement (direct API calls)
- **P2-9**: Incremental changes (<500 lines)

---

### `plan` - Generate Plan with Context Gating

Validate context requirements before coding.

**Syntax:**
```bash
python -m agentic_system.cli plan \
  --task "Task description" \
  [--files "file1.py,file2.py"]
```

**Options:**
- `--task` (required): Task description
- `--files` (optional): Comma-separated list of visible files

**Output:**
- Status: `ready`, `needs_clarification`, or `blocked`
- Questions (up to 5)
- Missing context
- Assumptions
- Required files

**Example:**
```bash
python -m agentic_system.cli plan \
  --task "Add Redis caching to summarize skill with 1-hour TTL" \
  --files "src/agentic_system/skills/summarize.py"
```

Output:
```
============================================================
CONTEXT GATE ANALYSIS
============================================================

Status: NEEDS_CLARIFICATION
Can Proceed: ❌ No

QUESTIONS (3):

  Q1 [CRITICAL]:
      Which files am I allowed to modify for this task?
      Reason: P0-2 Scope Control: Need explicit file allowlist

  Q2 [HIGH]:
      Where should the cache be stored (Redis, in-memory, filesystem)? What is the TTL?
      Reason: Implementation details needed

  Q3 [HIGH]:
      What are the current schemas/contracts I need to preserve?
      Reason: P1-6 Preserve Contracts: Need to know existing contracts

ASSUMPTIONS:
  - Working with files: src/agentic_system/skills/summarize.py
  - No breaking changes allowed (P1-6)
  - Tests will be added/updated (P0-5)
```

---

### `review` - Review Code Changes

Run bounded autonomy agent in review mode.

**Syntax:**
```bash
python -m agentic_system.cli review \
  --files "file1.py,file2.py" \
  [--pr-description "PR text"]
```

**Options:**
- `--files` (required): Comma-separated list of modified files
- `--pr-description` (optional): PR description text

**Example:**
```bash
python -m agentic_system.cli review \
  --files "src/agentic_system/skills/cache.py,tests/unit/test_cache_skill.py" \
  --pr-description "Added CacheSkill"
```

---

## Make Commands

Convenient shortcuts for common tasks.

### Prompt Generation

```bash
make prompt-A0              # Generate A0 (planning) prompt
make prompt-A1              # Generate A1 (implementation) prompt
```

### Compliance Checking

```bash
make check-compliance FILES="file1.py,file2.py"
```

### Planning

```bash
make plan TASK="Your task description"
```

### Review

```bash
make review FILES="file1.py,file2.py"
```

### Documentation

```bash
make show-rules             # Display LLM_RULES.md
make show-templates         # Display LLM_TASK_TEMPLATES.md
```

### Git Integration

```bash
make validate-changes       # Validate uncommitted git changes
```

---

## Workflow Examples

### Example 1: Add New Skill

**Step 1: Generate planning prompt**
```bash
python -m agentic_system.cli prompt --template new-skill \
  --name "translation_skill" \
  --purpose "Translate text using LLM Gateway" \
  --side-effects "idempotent" \
  --timeout 60
```

Copy output, paste into Copilot Chat, answer questions.

**Step 2: After implementation, check compliance**
```bash
make check-compliance FILES="src/agentic_system/skills/translation.py,tests/unit/test_translation_skill.py"
```

**Step 3: If compliant, commit and create PR**
```bash
git add src/agentic_system/skills/translation.py tests/unit/test_translation_skill.py
git commit -m "Add TranslationSkill"
git push origin feature/translation-skill
```

Use `.github/pull_request_template.md` for PR.

---

### Example 2: Bug Fix

**Step 1: Generate bugfix prompt**
```bash
python -m agentic_system.cli prompt --template bugfix \
  --bug "LLM Gateway timeout after 30 seconds" \
  --error "$(cat error.log)"
```

**Step 2: After fix, validate**
```bash
make check-compliance FILES="src/agentic_system/skills/llm_gateway.py,tests/unit/test_llm_gateway_skill.py"
```

---

### Example 3: Refactor

**Step 1: Plan with context gating**
```bash
make plan TASK="Extract duplicate retry logic into helper function"
```

Answer questions, get file allowlist.

**Step 2: Generate refactor prompt**
```bash
python -m agentic_system.cli prompt --template refactor \
  --goal "Extract retry logic into _retry_with_backoff() helper"
```

**Step 3: After refactor, check compliance**
```bash
make check-compliance FILES="src/agentic_system/skills/llm_gateway.py,tests/unit/test_llm_gateway_skill.py"
```

Verify tests still pass:
```bash
make test
```

---

## Integration with Git

### Pre-commit Hook

Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
# Validate changes before commit

CHANGED_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' | tr '\n' ',')

if [ -n "$CHANGED_FILES" ]; then
    echo "Checking bounded autonomy compliance..."
    python -m agentic_system.cli check-compliance --pr-files "$CHANGED_FILES"
    
    if [ $? -ne 0 ]; then
        echo "❌ Compliance check failed. Fix violations before committing."
        exit 1
    fi
fi
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

---

## Troubleshooting

### "Import could not be resolved"

Lint errors are expected until dependencies are installed:
```bash
make dev
```

### "No module named agentic_system"

Install package:
```bash
pip install -e .
```

### "File not found" in check-compliance

Ensure file paths are correct and files exist:
```bash
ls -la src/agentic_system/skills/your_skill.py
```

### CLI returns non-zero exit code

- Exit code `0`: Success
- Exit code `1`: Failure (e.g., P0 violations)

Check output for specific errors.

---

## Advanced Usage

### Custom Templates

Edit `/docs/LLM_TASK_TEMPLATES.md` to add custom templates.

### Programmatic Usage

```python
from agentic_system.runtime import ExecutionContext, get_skill_registry
from agentic_system.skills import CodeReviewSkill

skill_registry = get_skill_registry()
skill_registry.register(CodeReviewSkill())

context = ExecutionContext(
    trace_id="custom-review",
    job_id="job-123",
    agent_id="cli"
)

result = skill_registry.execute(
    name="code_review",
    input_data={
        "modified_files": ["file.py"],
        "file_diffs": {"file.py": "..."},
    },
    context=context
)

print(result["compliance_status"])
```

---

## Next Steps

1. **Read the rules**: `make show-rules`
2. **See templates**: `make show-templates`
3. **Try planning**: `make plan TASK="your task"`
4. **Check compliance**: `make check-compliance FILES="your files"`
5. **Review PR template**: `.github/pull_request_template.md`

For questions, see `/docs/LLM_RULES.md` or `/docs/LLM_TASK_TEMPLATES.md`.
