# Pull Request: [Brief Title]

## Summary
<!-- One-paragraph description of what this PR does and why. -->

## Type of Change
<!-- Check one -->
- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New feature (non-breaking change adding functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Refactor (code improvement without behavior change)
- [ ] Documentation update
- [ ] Reliability/security/database change

---

## Bounded Autonomy Compliance

### P0 Checklist (Blocking)
<!-- All items MUST be checked before merge -->

- [ ] **P0-1: Context Gating** — Required context was verified before coding (or N/A for doc-only changes)
- [ ] **P0-2: Scope Control** — Only planned files were modified (list below)
- [ ] **P0-3: No Hallucination** — All imports resolve; no undefined names or APIs
- [ ] **P0-4: Output Discipline** — PR includes: patches + tests + risks + rollback plan
- [ ] **P0-5: Tests Added/Updated** — All code changes have corresponding test updates

**Files Modified** (must match plan):
<!-- List all files changed in this PR -->
- `path/to/file1.py`
- `path/to/file2.py`

**Symbols Modified** (cite exact names):
<!-- Example: "Modified `LLMGatewaySkill._check_budget_pre_call()` in src/agentic_system/skills/llm_gateway.py" -->
- 

---

## Plan → Patch → Tests → Rollback

### 1. Plan
<!-- Reference approved A0 plan if applicable, or describe steps taken -->

**Steps implemented**:
1. 
2. 
3. 

**Assumptions**:
- 

**Blockers resolved**:
- 

### 2. Patches
<!-- High-level summary; detailed diffs are in "Files changed" tab -->

**Key changes by file**:
- `file1.py`: [one-line summary]
- `file2.py`: [one-line summary]

### 3. Tests
<!-- Describe test coverage -->

**Tests added/updated**:
- `tests/unit/test_X.py`: [what is tested]
- `tests/integration/test_Y.py`: [what is tested]

**Test results**:
```
<!-- Paste pytest output or CI link -->
```

### 4. Risks & Rollback

**What could break**:
- [ ] API clients (if endpoint/model changed)
- [ ] Scheduled jobs (if task signature changed)
- [ ] Other agents (if skill contract changed)
- [ ] Database (if schema changed)
- [ ] None (safe change)

**Affected users/systems**:
<!-- Who needs to be notified? -->

**Rollback procedure**:
```bash
# Step 1: Revert this PR
git revert <commit-sha>

# Step 2: Manual fixes (if any)
# ...
```

**Rollback tested**: [ ] Yes [ ] No [ ] N/A

---

## P1 Checklist (Recommended)

- [ ] **P1-6: Contracts Preserved** — No breaking changes to public APIs, or migration plan provided
- [ ] **P1-7: Docstrings Updated** — Docstrings added/updated at architectural choke points
- [ ] **P1-8: LLM Gateway Enforced** — All LLM calls go through `LLMGatewaySkill` (or N/A)

**Contract changes** (if any):
<!-- Describe breaking changes and migration path -->

---

## P2 Checklist (Optional)

- [ ] **P2-9: Incremental Change** — PR is <500 lines (or staged refactor with follow-up plan)

**Lines changed**: <!-- Auto-filled by GitHub; note if >500 -->

---

## Observability

**Logs added**:
<!-- List new log statements with trace context -->
- 

**Metrics added**:
<!-- List new metrics or N/A -->
- 

---

## Screenshots / Output
<!-- For UI changes or CLI output, paste screenshots or logs -->

```
<!-- Paste example output here -->
```

---

## Related Issues
<!-- Link to GitHub issues or Jira tickets -->

Closes #
Relates to #

---

## Reviewer Notes
<!-- Anything specific you want reviewers to focus on? -->

**Focus areas**:
- 
- 

**Questions for reviewers**:
- 
- 

---

## Pre-Merge Checklist (Reviewer)

- [ ] All P0 items checked
- [ ] Tests pass in CI
- [ ] No hallucinated APIs (imports resolve)
- [ ] Scope matches plan (no unexpected files)
- [ ] Rollback plan is clear
- [ ] Documentation updated if needed

---

## Compliance Validation

**Validated by CLI** (optional):
```bash
# Run bounded autonomy validation
python -m agentic_system.cli check-compliance --pr-files "file1.py,file2.py"
```

```
<!-- Paste CLI validation output here -->
```

---

**Reviewer Sign-Off**:
<!-- Assign reviewers and await approval -->
