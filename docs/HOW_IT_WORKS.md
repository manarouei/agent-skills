# How Bounded Autonomy Works - Complete Guide

**Date**: December 20, 2025  
**Your Agent-Skills Workflow from Now On**

---

## 🎯 The Problem We Solved

Before bounded autonomy, LLMs would:
- ❌ Hallucinate imports/functions that don't exist
- ❌ Modify files outside the task scope
- ❌ Break existing contracts without realizing it
- ❌ Skip writing tests
- ❌ Make assumptions without asking questions

**Result**: Broken code, wasted time debugging, production incidents.

---

## ✅ The Solution: Bounded Autonomy System

A **three-layer enforcement system** that acts as guardrails for AI-assisted development:

```
┌────────────────────────────────────────────────────────┐
│  📚 RULES LAYER                                        │
│  - P0 (Priority 0): BLOCKING rules - must follow      │
│  - P1 (Priority 1): STRONG recommendations            │
│  - P2 (Priority 2): Nice-to-have suggestions          │
└────────────────────────────────────────────────────────┘
                      ↓
┌────────────────────────────────────────────────────────┐
│  🤖 ENFORCEMENT LAYER                                  │
│  - ContextGateSkill: Ask questions BEFORE coding      │
│  - CodeReviewSkill: Validate compliance AFTER coding  │
│  - BoundedAutonomyAgent: Orchestrate everything       │
└────────────────────────────────────────────────────────┘
                      ↓
┌────────────────────────────────────────────────────────┐
│  🖥️  ACCESS LAYER                                      │
│  - Terminal commands (Make)                            │
│  - Python CLI                                          │
│  - Integrated into your workflow                       │
└────────────────────────────────────────────────────────┘
```

---

## 📋 The P0/P1/P2 Rules (Your New Bible)

### P0 Rules - MUST FOLLOW (Blocking)

#### **P0-1: Context Gating**
- **Rule**: Ask up to 5 clarifying questions BEFORE starting work
- **Why**: Prevents assumptions and hallucinations
- **Example**: 
  ```bash
  # Task: "Add caching to summarize skill"
  # Questions:
  # 1. Where should cache be stored? (Redis/in-memory/filesystem)
  # 2. What's the TTL?
  # 3. Which files am I allowed to modify?
  # 4. Should cache be skill-level or system-wide?
  # 5. What's the cache invalidation strategy?
  ```

#### **P0-2: Scope Control**
- **Rule**: ONLY modify files explicitly allowed
- **Why**: Prevents scope creep and unexpected side effects
- **Example**: 
  ```bash
  # Planned: ["src/skills/summarize.py"]
  # Modified: ["src/skills/summarize.py", "src/api/main.py"]  ❌ VIOLATION
  ```

#### **P0-3: No Hallucination**
- **Rule**: Never invent imports, functions, or APIs
- **Why**: Prevents broken code that looks correct
- **Example**:
  ```python
  from some_made_up_library import magic_function  ❌ VIOLATION
  # Must verify ALL imports actually exist
  ```

#### **P0-4: Output Discipline**
- **Rule**: PR descriptions must cite exact symbols: `ClassName.method_name`
- **Why**: Makes changes traceable and reviewable
- **Example**:
  ```markdown
  # Good PR Description:
  Modified `SummarizeSkill._execute()` to add caching via 
  `CacheManager.get()` and `CacheManager.set()`. Updated 
  `test_summarize_skill.py` with `test_caching_behavior()`.
  ```

#### **P0-5: Two-Pass Workflow**
- **Rule**: Plan → Patch → Tests → Rollback plan
- **Why**: Ensures reversibility and test coverage
- **Example**:
  ```bash
  # Pass 1: PLAN (use context gate)
  make plan TASK="Add caching to summarize"
  
  # Pass 2: IMPLEMENT (make changes)
  # Edit files...
  
  # Pass 3: VALIDATE (check compliance)
  make review FILES="src/skills/summarize.py"
  ```

### P1 Rules - STRONGLY RECOMMENDED (Warnings)

#### **P1-6: Preserve Contracts**
- **Rule**: Never break existing public APIs without migration path
- **Why**: Prevents breaking downstream consumers
- **Example**:
  ```python
  # Before (contract file):
  class SummarizeInput(BaseModel):
      text: str
      max_words: int
  
  # After - ❌ VIOLATION (breaking change):
  class SummarizeInput(BaseModel):
      text: str
      max_words: int
      required_new_field: str  # ← breaks existing callers!
  
  # After - ✅ SAFE (backwards compatible):
  class SummarizeInput(BaseModel):
      text: str
      max_words: int
      optional_new_field: str | None = None  # ← safe!
  ```

#### **P1-7: Strategic Docstrings**
- **Rule**: All new functions/classes need docstrings with Context/Contract
- **Why**: Makes code maintainable and AI-readable
- **Example**:
  ```python
  def summarize_text(text: str, max_words: int) -> str:
      """
      Summarize text to a maximum word count.
      
      Context: Uses LLMGatewaySkill for actual summarization.
      Contract: Input text must be non-empty; max_words must be > 0.
      Side Effects: Makes network call via LLM Gateway.
      
      Args:
          text: The text to summarize (non-empty)
          max_words: Maximum words in summary (> 0)
      
      Returns:
          Summarized text
      
      Raises:
          ValueError: If text is empty or max_words <= 0
      """
  ```

#### **P1-8: LLM Gateway**
- **Rule**: ALL LLM calls must go through `LLMGatewaySkill`
- **Why**: Centralized cost tracking, rate limiting, monitoring
- **Example**:
  ```python
  # ❌ WRONG:
  import anthropic
  client = anthropic.Anthropic(api_key=key)
  response = client.messages.create(...)
  
  # ✅ CORRECT:
  from agentic_system.runtime import get_skill_registry
  registry = get_skill_registry()
  result = registry.execute(
      name="llm.anthropic_gateway",
      input_data={
          "messages": [{"role": "user", "content": "..."}],
          "max_tokens": 1000
      },
      context=context
  )
  ```

### P2 Rules - NICE TO HAVE (Suggestions)

#### **P2-9: Incremental Changes**
- **Rule**: Keep PRs under 500 lines
- **Why**: Easier to review, test, and rollback
- **Example**: Break a 1000-line feature into 3 smaller PRs

---

## 🛠️ How to Use It: Your New Workflow

### Workflow 1: Adding a New Feature

```bash
# Step 1: Generate a properly scoped prompt with built-in rules
make prompt-A1

# Output:
# === TASK A1: Feature Implementation with Existing Patterns ===
# You must ask 3-5 clarifying questions about:
# - Which files you're allowed to modify
# - What existing patterns to follow
# - Where tests should go
# 
# [Copy this prompt and use it with your LLM]

# Step 2: Get answers to questions, then validate context BEFORE coding
make plan TASK="Add Redis caching to SummarizeSkill"

# Output (from ContextGateSkill):
# ❓ Questions:
# 1. [CRITICAL] Which files am I allowed to modify?
# 2. [HIGH] Where should cache be stored? (Redis/in-memory/filesystem)
# 3. [HIGH] What is the TTL for cached summaries?
# 4. [HIGH] Should cache key include user context or be global?
# 5. [HIGH] What's the cache invalidation strategy?
#
# Status: needs_clarification
# Missing: file_allowlist, cache_implementation
# Can proceed: false

# Step 3: Provide answers, update task description, run plan again
make plan TASK="Add Redis caching to SummarizeSkill. Modify only src/skills/summarize.py and tests/. Use Redis with 1hr TTL."

# Output:
# Status: ready ✅
# Assumptions:
# - Working with files: src/skills/summarize.py
# - No breaking changes allowed (P1-6)
# - Tests will be added/updated (P0-5)
# Can proceed: true

# Step 4: Make your changes
# Edit src/skills/summarize.py...
# Edit tests/unit/test_summarize_skill.py...

# Step 5: Check compliance BEFORE committing
make check-compliance FILES="src/skills/summarize.py tests/unit/test_summarize_skill.py"

# Output:
# ✅ Compliance Status: compliant
# 
# Files analyzed: 2
# Lines changed: 87
# P0 violations: 0 (blocking)
# P1 violations: 0 (warnings)
# P2 suggestions: 0
# 
# Recommendations: None - looks good!

# Step 6: Run tests
make test

# Step 7: Commit with proper PR description (P0-4)
git commit -m "feat: Add Redis caching to SummarizeSkill

Modified \`SummarizeSkill._execute()\` to check \`CacheManager.get()\` 
before LLM call and \`CacheManager.set()\` after. Added Redis client 
to \`__init__()\`. Updated \`test_summarize_skill.py\` with 
\`test_cache_hit()\` and \`test_cache_miss()\`.

Files changed:
- src/skills/summarize.py: Added caching logic
- tests/unit/test_summarize_skill.py: Added cache tests

No breaking changes. Cache key: 'summarize:{text_hash}'
TTL: 1 hour"
```

### Workflow 2: Fixing a Bug

```bash
# Step 1: Use bugfix prompt template
make prompt-bugfix

# Step 2: Quick compliance check on changed files
make check-compliance FILES="src/skills/problematic.py"

# Output might show:
# ⚠️ P1-7: New function \`_helper_method()\` missing docstring
# 💡 Recommendation: Add docstring to new code

# Step 3: Fix the issues, check again
make check-compliance FILES="src/skills/problematic.py"

# Output:
# ✅ All checks passed
```

### Workflow 3: Reviewing a PR (Manual)

```bash
# Check if PR follows rules
make review FILES="src/skills/new_feature.py src/skills/helper.py" \
            PLANNED="src/skills/new_feature.py"

# Output:
# ❌ P0-2 VIOLATION: Scope control
# Unplanned files modified: src/skills/helper.py
# 
# ❌ P0-5 VIOLATION: No test file modified
# No test found for src/skills/new_feature.py
#
# ⚠️ P1-8 WARNING: Direct LLM call detected
# Found in src/skills/new_feature.py
#
# 💡 Recommendations:
# - Only modify files in approved allowlist
# - Add/update tests in tests/unit/test_new_feature.py
# - Route LLM calls through skill_registry.execute('llm.anthropic_gateway')
```

---

## 🎨 The Skills and Agent

### ContextGateSkill

**Purpose**: Validate you have enough context BEFORE coding

**When to use**: At the start of every task

```bash
# Via CLI
python -m agentic_system.cli plan \
    --task "Add OAuth2 authentication to API" \
    --files "src/api/auth.py"

# Via Make
make plan TASK="Add OAuth2 authentication"
```

**What it does**:
1. Analyzes task description for keywords (database, cache, API, security, etc.)
2. Checks if you have required context in `available_context`
3. Generates up to 5 prioritized questions (critical → high → medium → low)
4. Makes explicit assumptions if context is sufficient
5. Returns status: `ready` / `needs_clarification` / `blocked`

**Example output**:
```json
{
  "status": "needs_clarification",
  "questions": [
    {
      "priority": "critical",
      "question": "What is the current security model (authentication, authorization)?",
      "reason": "Security changes require understanding current posture"
    },
    {
      "priority": "high",
      "question": "What are the current schemas/contracts I need to preserve?",
      "reason": "P1-6 Preserve Contracts: Need to know existing contracts"
    }
  ],
  "missing_context": ["security_model", "schemas"],
  "assumptions": [],
  "can_proceed": false
}
```

### CodeReviewSkill

**Purpose**: Validate compliance with P0/P1/P2 rules AFTER coding

**When to use**: Before committing changes

```bash
# Via CLI
python -m agentic_system.cli check-compliance \
    --files src/skills/summarize.py tests/unit/test_summarize.py

# Via Make
make check-compliance FILES="src/skills/summarize.py tests/"
```

**What it does**:
1. Analyzes file diffs for suspicious patterns
2. Checks for missing tests (P0-5)
3. Detects scope violations (P0-2)
4. Flags direct LLM API calls (P1-8)
5. Warns on large changes >500 lines (P2-9)
6. Validates docstrings on new code (P1-7)
7. Detects potential contract breakage (P1-6)
8. Returns detailed compliance report

**Example output**:
```json
{
  "compliance_status": "warnings",
  "p0_violations": [],
  "p1_violations": [
    {
      "rule_id": "P1-7",
      "severity": "P1",
      "file": "src/skills/summarize.py",
      "message": "New function _build_cache_key() without docstring"
    }
  ],
  "p2_suggestions": [],
  "total_files_modified": 2,
  "total_lines_changed": 87,
  "recommendations": [
    "Add docstring to new code in src/skills/summarize.py"
  ]
}
```

### BoundedAutonomyAgent

**Purpose**: Orchestrate enforcement across different modes

**Modes**:
- `plan`: Uses ContextGateSkill for planning phase
- `review`: Uses CodeReviewSkill for review phase  
- `validate`: Uses both (full validation)

```python
# Via Python
from agentic_system.runtime import get_agent_registry

registry = get_agent_registry()
result = registry.run(
    agent_id="bounded_autonomy",
    input_data={
        "mode": "plan",
        "task_description": "Add caching to summarize skill",
        "visible_files": ["src/skills/summarize.py"]
    },
    context=execution_context
)
```

---

## 🗂️ File Organization

```
agent-skills/
├── docs/
│   ├── LLM_RULES.md                    ← THE RULES (your bible)
│   ├── LLM_TASK_TEMPLATES.md           ← 8 gold prompts
│   ├── BOUNDED_AUTONOMY_CLI.md         ← CLI usage guide
│   └── HOW_IT_WORKS.md                 ← This file!
│
├── src/agentic_system/
│   ├── skills/
│   │   ├── code_review.py              ← P0/P1/P2 checker
│   │   ├── context_gate.py             ← Context validator
│   │   ├── summarize.py                ← Example skill
│   │   └── __init__.py
│   │
│   ├── agents/
│   │   ├── bounded_autonomy.py         ← Orchestrator agent
│   │   ├── simple_summarizer.py        ← Example agent
│   │   └── __init__.py
│   │
│   ├── cli.py                          ← Terminal commands
│   └── integrations/
│       └── tasks.py                    ← Celery + registry
│
├── tests/
│   └── unit/
│       ├── test_code_review_skill.py   ← Tests for compliance checker
│       ├── test_context_gate_skill.py  ← Tests for context gate
│       └── ...
│
├── .github/
│   └── pull_request_template.md        ← PR template with P0/P1/P2 checklist
│
├── agent-skills-bounded-autonomy-spec.yaml  ← Planner/registry spec
├── Makefile                             ← Quick commands
└── pyproject.toml                       ← Package config
```

---

## 🚀 Quick Reference: Make Commands

```bash
# PROMPT GENERATION
make prompt-A0          # Generate emergency hotfix prompt
make prompt-A1          # Generate feature implementation prompt
make show-rules         # Show LLM_RULES.md
make show-templates     # Show all prompt templates

# PLANNING (Context Gating)
make plan TASK="Your task description"
# Example: make plan TASK="Add Redis caching to summarize skill"

# COMPLIANCE CHECKING
make check-compliance FILES="file1.py file2.py"
# Example: make check-compliance FILES="src/skills/summarize.py tests/"

# FULL REVIEW
make review FILES="file1.py file2.py" PLANNED="file1.py"
# Example: make review FILES="src/skills/new.py src/skills/helper.py" PLANNED="src/skills/new.py"

# GIT INTEGRATION
make validate-changes   # Check compliance on git diff (staged files)

# TESTING
make test              # Run all tests
make test-cov          # Run tests with coverage

# DEVELOPMENT
make dev               # Install in editable mode
make lint              # Run linter
make lint-fix          # Auto-fix linting issues
```

---

## 🎯 Your Mental Model Going Forward

### Before Bounded Autonomy:
```
LLM → "Sure, I'll add caching!" → Modifies 10 files → 
Invents CacheManager class → Breaks 3 contracts → No tests → 
💥 Production broken
```

### With Bounded Autonomy:
```
LLM → Reads P0/P1/P2 rules → Asks 5 questions → 
Gets answers → Plans changes (make plan) → 
Codes ONLY allowed files → Checks compliance (make check-compliance) → 
Adds tests → ✅ Production safe
```

---

## 🔧 Integration with Existing Tools

### 1. Git Pre-commit Hook

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
# Run compliance check on staged files

staged_files=$(git diff --cached --name-only --diff-filter=ACM | grep "\.py$")

if [ -n "$staged_files" ]; then
    echo "🔍 Running bounded autonomy compliance check..."
    python -m agentic_system.cli check-compliance --files $staged_files
    
    if [ $? -ne 0 ]; then
        echo "❌ Compliance check failed. Fix violations before committing."
        exit 1
    fi
    
    echo "✅ Compliance check passed!"
fi
```

### 2. CI/CD Pipeline

Add to `.github/workflows/pr-check.yml`:

```yaml
name: PR Compliance Check

on:
  pull_request:
    branches: [main, develop]

jobs:
  compliance:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -e ".[dev]"
      
      - name: Check P0/P1/P2 Compliance
        run: |
          changed_files=$(git diff --name-only origin/main...HEAD | grep "\.py$")
          if [ -n "$changed_files" ]; then
            python -m agentic_system.cli check-compliance --files $changed_files
          fi
```

### 3. VS Code Integration

Add to `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Check Bounded Autonomy Compliance",
      "type": "shell",
      "command": "make check-compliance FILES='${file}'",
      "group": "test",
      "presentation": {
        "reveal": "always",
        "panel": "new"
      }
    },
    {
      "label": "Plan with Context Gate",
      "type": "shell",
      "command": "make plan TASK='${input:taskDescription}'",
      "group": "build",
      "presentation": {
        "reveal": "always",
        "panel": "new"
      }
    }
  ],
  "inputs": [
    {
      "id": "taskDescription",
      "type": "promptString",
      "description": "Enter task description"
    }
  ]
}
```

---

## 📊 Metrics to Track

Monitor these to measure bounded autonomy effectiveness:

```yaml
Effectiveness Metrics:
  - P0 violations per PR (target: 0)
  - P1 violations per PR (target: <2)
  - PRs blocked by violations (track trend)
  - Time saved debugging hallucinations
  - Production incidents from agent-modified code

Usage Metrics:
  - `make plan` invocations per week
  - `make check-compliance` invocations per PR
  - CLI commands usage distribution
  - Context gate question → answer → proceed rate

Quality Metrics:
  - Test coverage on agent-modified code
  - Contract breakage incidents (should be 0)
  - Scope violations caught (prevented issues)
  - Average PR size (should be <500 lines)
```

---

## 🎓 Learning Resources

1. **Start Here**: Read `docs/LLM_RULES.md` (229 lines, the foundation)
2. **Templates**: Review `docs/LLM_TASK_TEMPLATES.md` (8 gold prompts)
3. **CLI Guide**: Check `docs/BOUNDED_AUTONOMY_CLI.md` (terminal usage)
4. **Examples**: Look at test files to see skills in action
5. **PR Template**: Use `.github/pull_request_template.md` for all PRs

---

## 🚨 Common Pitfalls & How to Avoid Them

### Pitfall 1: Skipping Context Gating
**Problem**: Jump straight to coding without running `make plan`  
**Result**: Make assumptions, hallucinate APIs, waste time  
**Solution**: ALWAYS run `make plan` first. It takes 30 seconds and saves hours.

### Pitfall 2: Ignoring P0 Violations
**Problem**: Commit code with P0 violations thinking "I'll fix it later"  
**Result**: Broken production, debugging nightmares  
**Solution**: P0 = BLOCKING. Fix immediately before committing.

### Pitfall 3: Not Using Prompt Templates
**Problem**: Write custom prompts without rules enforcement  
**Result**: LLM forgets rules, makes mistakes  
**Solution**: Use `make prompt-A1` etc. Templates have rules baked in.

### Pitfall 4: Vague PR Descriptions
**Problem**: "Fixed bug" without citing exact symbols  
**Result**: Violates P0-4, makes code unreviewable  
**Solution**: Always cite exact `ClassName.method_name` in PRs.

### Pitfall 5: Large Atomic PRs
**Problem**: 1000+ line "add feature X" PR  
**Result**: Hard to review, test, rollback. High risk.  
**Solution**: Break into 3-4 PRs of <500 lines each (P2-9).

---

## 🎉 Success Stories (What You Can Now Do)

✅ **Add a new skill** with 100% confidence it won't break existing code  
✅ **Refactor safely** knowing contracts are preserved (P1-6)  
✅ **Review AI-generated code** in 2 minutes with `make check-compliance`  
✅ **Onboard new devs** with clear rules and automated checks  
✅ **Ship faster** because you catch issues before production  

---

## 🔮 Future Enhancements

Potential additions to the system:

1. **Auto-fix mode**: `make check-compliance --fix` to auto-add docstrings
2. **Learning mode**: Train on your codebase to improve detection
3. **IDE plugins**: Real-time compliance checking in VS Code/PyCharm
4. **Cost tracking**: Monitor LLM usage via gateway
5. **Dependency tracking**: Detect when imports might be hallucinated
6. **Semantic analysis**: AST-based contract change detection

---

## 💡 Pro Tips

1. **Alias the commands** in your shell:
   ```bash
   alias ba-plan='make plan TASK='
   alias ba-check='make check-compliance FILES='
   alias ba-review='make review FILES='
   ```

2. **Set up shell prompt** to show compliance status:
   ```bash
   # In .bashrc/.zshrc
   function git_prompt() {
       if git diff --cached --quiet 2>/dev/null; then
           echo ""
       else
           echo " [✓ run: ba-check]"
       fi
   }
   PS1='$(git_prompt) $ '
   ```

3. **Create task-specific allowlists** in project root:
   ```bash
   # .allowlists/feature-caching.txt
   src/skills/summarize.py
   tests/unit/test_summarize_skill.py
   ```

4. **Use tmux/split terminals** for workflow:
   - Terminal 1: Edit code
   - Terminal 2: Run `make plan` / `make check-compliance`
   - Terminal 3: Run `make test`

---

## 🆘 Troubleshooting

### "Import errors when running CLI"
```bash
# Solution: Make sure you installed in dev mode
make dev
```

### "make plan returns empty questions"
```bash
# Solution: Provide more specific task description
# BAD:  make plan TASK="fix bug"
# GOOD: make plan TASK="Fix off-by-one error in SummarizeSkill._execute() text truncation"
```

### "Compliance check passes but code still broken"
```bash
# The checker only validates P0/P1/P2 rules, not correctness!
# Solution: Always run tests: make test
```

### "Too many questions from context gate"
```bash
# Solution: Provide available_context via CLI:
python -m agentic_system.cli plan \
    --task "..." \
    --context '{"file_allowlist": ["src/skills/x.py"], "cache_implementation": "Redis 1hr TTL"}'
```

---

## 📞 Getting Help

1. **Documentation**: Check `docs/` folder first
2. **Examples**: Look at test files for usage patterns
3. **CLI Help**: Run `python -m agentic_system.cli --help`
4. **Rule Clarification**: Read `docs/LLM_RULES.md` carefully

---

## ✨ The Bottom Line

**Bounded autonomy** transforms AI coding from "hope it works" to "know it works":

- 🛡️ **Safety**: P0 rules prevent production disasters
- 🎯 **Precision**: Context gating eliminates assumptions
- ⚡ **Speed**: Automated compliance checking saves hours
- 📚 **Knowledge**: Documentation that's actually followed
- 🤝 **Collaboration**: Clear contracts between human and AI

**Your new mantra**: 
> "Plan → Code → Check → Test → Ship" 

Every time. No exceptions.

---

**Ready to start?** 

```bash
# 1. Read the rules
make show-rules

# 2. Try your first planned task
make plan TASK="Add logging to healthcheck skill"

# 3. Make changes, then check
make check-compliance FILES="src/skills/healthcheck.py"

# 4. Ship with confidence! 🚀
```

**Welcome to bounded autonomy. Your code will thank you.** ✅
