# LLM Task Templates (Gold Prompts)

**Version**: 1.0.0  
**Last Updated**: 2025-12-20  
**Purpose**: Copy-paste prompts for common tasks with built-in guardrails

---

## How to Use

1. Copy the template for your task type.
2. Fill in the `{placeholders}` with your specific context.
3. Paste into Copilot Chat or use via CLI: `python -m agentic_system.cli prompt --template A0`
4. Follow the two-pass workflow (A0 → A1) for non-trivial changes.

**All templates enforce the rules in `/docs/LLM_RULES.md`.**

---

## Template Index

1. [A0 - Planning + Questions](#template-a0-planning--questions)
2. [A1 - Patch + Tests](#template-a1-patch--tests)
3. [A1 - Reliability/Security/DB](#template-a1-reliability-security-db)
4. [Quick Bugfix](#template-quick-bugfix)
5. [New Skill](#template-new-skill)
6. [New Agent](#template-new-agent)
7. [Refactor](#template-refactor)
8. [Documentation Update](#template-documentation-update)

---

## Template A0: Planning + Questions

**Use for**: Non-trivial changes where you need to verify context first.

**CLI**: `python -m agentic_system.cli prompt --template A0 --task "your task"`

```
You are a careful coding assistant following bounded autonomy rules (see /docs/LLM_RULES.md).

TASK: {Describe what you want to accomplish}

RULES:
- P0: Ask up to 5 questions if context is missing, then STOP
- P0: Do NOT generate code in this pass
- P0: Do NOT assume files/APIs exist—cite exact names from context

CONTEXT AVAILABLE:
{List files you've opened, symbols you can see, etc.}

OUTPUT REQUIRED:
1. **PLAN** (numbered steps to implement the task)
2. **QUESTIONS** (up to 5, prioritized by blocking severity)
3. **ASSUMPTIONS** (explicit list of what you're assuming)
4. **REQUIRED FILES/SYMBOLS** (with citations: "X in path/to/file.py")
5. **BLOCKERS** (if any context is missing after questions)

If you cannot create a complete plan after 5 questions, output "BLOCKED: <reason>" and stop.
```

---

## Template A1: Patch + Tests

**Use for**: Implementing an approved plan.

**CLI**: `python -m agentic_system.cli prompt --template A1 --plan plan.txt --files "file1.py,file2.py"`

```
You are implementing an approved plan following bounded autonomy rules (see /docs/LLM_RULES.md).

APPROVED PLAN:
{Paste the plan from A0 pass here}

RULES:
- P0: Touch ONLY these files: {List allowed files, e.g., "src/agentic_system/skills/summarize.py, tests/unit/test_summarize_skill.py"}
- P0: Preserve public contracts (APIs, Pydantic models, endpoints)
- P0: Cite exact symbols modified (ClassName.method_name)
- P0: Include tests for every change

OUTPUT REQUIRED (in order):
1. **PATCHES** (file-by-file, minimal diffs with file path headers)
2. **TESTS** (new/updated test cases)
3. **RISKS** (what could break; who is affected)
4. **ROLLBACK** (git revert steps + any manual fixes needed)
5. **SYMBOLS MODIFIED** (exact citations)

Example symbol citation: "Modified `LLMGatewaySkill._check_budget_pre_call()` in `src/agentic_system/skills/llm_gateway.py`"

If you need to touch a file not in the allowlist, STOP and ask.
```

---

## Template A1: Reliability, Security, or DB

**Use for**: Changes to error handling, security, or data persistence.

**CLI**: `python -m agentic_system.cli prompt --template A1-reliability --task "your task"`

```
You are implementing a reliability/security/database change following strict rules (see /docs/LLM_RULES.md).

TASK: {Describe the reliability/security/DB change}

RULES:
- P0: Touch ONLY these files: {List allowed files}
- P0: Preserve data formats and migration paths
- P0: Include rollback procedure tested on staging data
- P0: Security changes require threat model update
- P1: Add observability (logs, metrics, traces)

CONTEXT:
- Database schema: {Provide schema or say "N/A"}
- Current error rates: {Provide metrics or say "Unknown"}
- Security posture: {Describe current auth/authz or say "N/A"}

OUTPUT REQUIRED:
1. **THREAT/FAILURE ANALYSIS** (what could go wrong)
2. **PATCHES** (file-by-file, with extra safety checks)
3. **TESTS** (including negative cases, edge cases)
4. **OBSERVABILITY** (log statements, metrics added)
5. **ROLLBACK** (tested procedure, data migration reversal if applicable)
6. **STAGING VERIFICATION** (checklist before production deploy)

If you lack critical context (schema, error rates, security model), ask up to 5 questions then STOP.
```

---

## Template: Quick Bugfix

**Use for**: Minimal scope bug fixes.

**CLI**: `python -m agentic_system.cli prompt --template bugfix --error "error trace"`

```
BUGFIX MODE: Minimal change, maximum safety (see /docs/LLM_RULES.md).

BUG REPORT: {Describe the bug}
ERROR TRACE: {Paste error stacktrace or logs}

RULES:
- P0: Touch ONLY the file containing the bug (or ask if multiple files involved)
- P0: Preserve public API
- P0: Add regression test that fails before fix, passes after

OUTPUT:
1. **ROOT CAUSE** (one sentence)
2. **MINIMAL PATCH** (exact line changes, file path header)
3. **REGRESSION TEST** (test case that reproduces the bug)
4. **RISK ASSESSMENT** (could this break anything else?)

If root cause is unclear after analyzing the error trace, ask up to 3 questions about reproduction steps.
```

---

## Template: New Skill

**Use for**: Adding a new skill to the agent-skills system.

**CLI**: `python -m agentic_system.cli prompt --template new-skill --name "skill_name"`

```
NEW SKILL CREATION following agent-skills patterns (see /docs/LLM_RULES.md).

SKILL REQUEST: {Describe the skill's purpose and behavior}

RULES:
- P0: Follow existing skill pattern (see src/agentic_system/skills/llm_gateway.py as reference)
- P0: Define Input/Output Pydantic models
- P0: Implement Skill base class with _execute() method
- P0: Register in src/agentic_system/integrations/tasks.py
- P1: Create skills/{skill_name}/SKILL.md documentation
- P1: Add tests/unit/test_{skill_name}_skill.py

REQUIRED CONTEXT:
- Skill name and purpose: {skill_name and description}
- Side effects: {read-only / idempotent / stateful}
- Timeout requirement: {timeout_s}
- Dependencies on other skills: {list skill names or "none"}

OUTPUT:
1. **PLAN** (files to create/modify)
2. **INPUT/OUTPUT MODELS** (Pydantic schemas with validation rules)
3. **SKILL IMPLEMENTATION** (with docstrings following P1-7 template)
4. **REGISTRATION** (changes to tasks.py)
5. **TESTS** (unit test file with at least 3 test cases)
6. **DOCUMENTATION** (SKILL.md content following existing format)

If side effect type or dependencies are unclear, ask before proceeding.
```

---

## Template: New Agent

**Use for**: Adding a new agent to orchestrate skills.

**CLI**: `python -m agentic_system.cli prompt --template new-agent --name "agent_name"`

```
NEW AGENT CREATION following agent-skills patterns (see /docs/LLM_RULES.md).

AGENT REQUEST: {Describe the agent's workflow and purpose}

RULES:
- P0: Follow existing agent pattern (see src/agentic_system/agents/simple_summarizer.py)
- P0: Define Input/Output Pydantic models
- P0: Implement Agent base class with _run() method
- P0: Register in src/agentic_system/integrations/tasks.py
- P1: Document step orchestration in docstring

REQUIRED CONTEXT:
- Agent name: {agent_id}
- Workflow steps: {list steps the agent will execute}
- Skills to call: {list skill names}
- Step limit: {max number of steps, default 10}
- Input/output: {describe expected input and output}

OUTPUT:
1. **PLAN** (files to create/modify)
2. **INPUT/OUTPUT MODELS** (Pydantic schemas)
3. **AGENT IMPLEMENTATION** (with docstrings)
4. **REGISTRATION** (changes to tasks.py)
5. **TESTS** (tests/unit/test_{agent_name}_agent.py)

If workflow steps are ambiguous, ask up to 5 questions.
```

---

## Template: Refactor

**Use for**: Code refactoring without behavior changes.

**CLI**: `python -m agentic_system.cli prompt --template refactor --goal "refactor goal"`

```
REFACTOR MODE: Improve code structure without changing behavior (see /docs/LLM_RULES.md).

REFACTOR GOAL: {What are you improving? E.g., "Extract duplicate logic into helper", "Rename variables for clarity"}

RULES:
- P0: Touch ONLY these files: {List allowed files}
- P0: Preserve public contracts (no API changes)
- P0: Preserve behavior (tests must still pass without modification)
- P1: Update docstrings if signatures change

OUTPUT:
1. **PLAN** (refactor steps)
2. **PATCHES** (file-by-file diffs)
3. **TEST VERIFICATION** (confirm existing tests still pass)
4. **SYMBOLS MODIFIED** (exact citations)

Run existing tests after refactor to confirm behavior preserved.
```

---

## Template: Documentation Update

**Use for**: Updating README, docstrings, or SKILL.md files.

**CLI**: `python -m agentic_system.cli prompt --template docs --files "file1.md,file2.md"`

```
DOCUMENTATION UPDATE (see /docs/LLM_RULES.md).

TASK: {What documentation needs updating?}

RULES:
- P0: Do not modify code while updating docs
- P0: Preserve existing document structure (headings, sections)
- P1: Use examples from actual codebase (cite file paths)

CONTEXT:
- Files to document: {List files}
- Current gaps: {What's missing or outdated?}

OUTPUT:
1. **UPDATED DOCUMENTATION** (markdown with code examples)
2. **FILES MODIFIED** (list of .md files changed)

Cite code examples with file paths (e.g., "See `src/agentic_system/skills/llm_gateway.py`").
```

---

## Tips for Effective Prompt Usage

1. **Always reference `/docs/LLM_RULES.md`** in your prompts to ground the LLM in project rules.
2. **Provide explicit file allowlists** in A1 prompts to prevent scope creep.
3. **Use A0 → A1 workflow** for changes >50 lines or touching >2 files.
4. **Include visible context** (files you've opened) to reduce hallucinations.
5. **Track question count**: If you hit 5 questions, stop and reassess with the team.
6. **Use CLI tool**: `python -m agentic_system.cli prompt --template <name>` for quick access.

---

## CLI Examples

```bash
# Generate A0 planning prompt
python -m agentic_system.cli prompt --template A0 --task "Add caching to summarize skill"

# Generate A1 implementation prompt with file allowlist
python -m agentic_system.cli prompt --template A1 \
  --plan plan.txt \
  --files "src/agentic_system/skills/summarize.py,tests/unit/test_summarize_skill.py"

# Generate bugfix prompt with error trace
python -m agentic_system.cli prompt --template bugfix \
  --bug "Timeout in LLM Gateway" \
  --error "$(cat error.log)"

# Generate new skill prompt
python -m agentic_system.cli prompt --template new-skill \
  --name "cache_skill" \
  --purpose "Cache LLM responses" \
  --side-effects "stateful" \
  --timeout 30

# Generate new agent prompt
python -m agentic_system.cli prompt --template new-agent \
  --name "code_reviewer" \
  --steps "1. Read code 2. Check rules 3. Generate report"
```

---

**Revision History**

| Version | Date       | Changes                              |
|---------|------------|--------------------------------------|
| 1.0.0   | 2025-12-20 | Initial template library             |
