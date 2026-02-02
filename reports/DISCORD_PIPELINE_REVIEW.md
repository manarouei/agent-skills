# Discord Pipeline Review

**Generated:** 2026-01-06  
**Correlation ID Reference:** `node-discord-v2test-4001e842`  
**Artifact Path:** `artifacts/node-discord-v2test-4001e842/converted/discord.py`

---

## Executive Summary

The pipeline is **structurally solid** - it correctly chains schema-infer → node-scaffold → code-convert → validate → package → apply → smoke-test. The core issue is **weak guardrails**: validation passes nodes with critical defects that would fail at runtime.

**Root Causes:**
1. Validation doesn't reject `NotImplementedError`, placeholder URLs, or TODO markers
2. Code generation produces ambiguous dispatch for multi-resource nodes (operation-only dispatch with duplicated branches)
3. Smoke-test is skipped by default and lacks static pre-runtime checks
4. `continue_on_fail` attribute access pattern doesn't match BaseNode

---

## 1. Architecture Verdict

### Clean Aspects
| Component | Status | Notes |
|-----------|--------|-------|
| Skill contract pattern | ✅ Clean | YAML frontmatter + clear inputs/outputs |
| Correlation ID tracing | ✅ Clean | Consistent across all artifacts |
| Sync Celery constraint | ✅ Clean | Enforced via `_check_async_patterns()` |
| Timeout check | ✅ Clean | `_check_timeout_on_requests()` catches missing timeouts |
| Artifact structure | ✅ Clean | Clear directory layout per correlation ID |

### Brittle Aspects (KISS Violations)
| Component | Issue | Location |
|-----------|-------|----------|
| **Validation gaps** | Allows NotImplementedError, placeholder URLs | `skills/node-validate/impl.py` |
| **Dispatch generation** | Operation-only dispatch for multi-resource nodes | `skills/code-convert/impl.py:1085-1130` |
| **continue_on_fail** | Uses `self.continue_on_fail` but BaseNode uses `self.node_data.continue_on_fail` | Generated code |
| **Smoke-test skipped** | Not in default pipeline path | `scripts/run_full_pipeline.py` |
| **Base URL extraction** | Falls back to `api.example.com` placeholder | `skills/code-convert/impl.py:1449` |

---

## 2. Pipeline Stage Mapping

### Stage: schema-infer
- **Input:** TypeScript source code (parsed_sections)
- **Output:** `inferred_schema.json`, `trace_map.json`
- **Invariants Enforced:** ✅ Trace map requires evidence
- **Gap:** None identified

### Stage: node-scaffold
- **Input:** `node_schema`, `normalized_name`
- **Output:** Scaffold Python files, `allowlist.json`, `scaffold_manifest.json`
- **Invariants Enforced:** ✅ Creates allowlist for scope gate
- **Gap:** None - this is superseded by code-convert for TYPE1

### Stage: code-convert
- **Input:** TypeScript source, `node_schema`, `normalized_name`
- **Output:** `converted/*.py` files
- **Invariants Enforced:** None
- **Gaps:**
  1. **No resource+operation dispatch** - generates flat operation-only dispatch even when resource exists
  2. **Falls back to placeholder URLs** - `api.example.com` and `/endpoint`
  3. **Generates TODO stubs** - leaves `NotImplementedError` for unconverted operations
  4. **`continue_on_fail` pattern wrong** - uses `self.continue_on_fail` instead of `self.node_data.continue_on_fail`

### Stage: node-validate
- **Input:** `package/` directory with Python files
- **Output:** `validation/results.json`
- **Invariants Enforced:**
  - ✅ Syntax check
  - ✅ AST parse
  - ✅ Import check (async imports)
  - ✅ Async pattern check
  - ✅ Node class check (type, execute)
  - ⚠️ Timeout check (warning only)
- **Gaps:**
  1. **Does NOT reject `NotImplementedError`** 
  2. **Does NOT reject placeholder URLs** (`api.example.com`)
  3. **Does NOT reject `/endpoint` placeholder**
  4. **Does NOT reject TODO markers**
  5. **Does NOT validate dispatch correctness** (resource+operation)
  6. **Does NOT validate `continue_on_fail` access pattern**

### Stage: node-smoke-test
- **Input:** `package/` + `target_repo_layout`
- **Output:** `smoke_test/results.json`
- **Invariants Enforced:** Import test, class exists, type attribute
- **Gaps:**
  1. **Skipped in run_full_pipeline.py** - never runs by default
  2. **No static checks** - only tests import, not code quality
  3. **Doesn't catch placeholder URLs** before hitting runtime
  4. **Doesn't catch NotImplementedError** before hitting runtime

---

## 3. Discord Parity Gaps

### Generated discord.py vs BaseNode Contract

| Aspect | discord.py | BaseNode/bale.py Pattern | Fix |
|--------|------------|--------------------------|-----|
| **Resource dispatch** | ❌ Operation-only dispatch | ✅ Resource+operation dispatch | Fix code-convert |
| **Duplicate branches** | ❌ `elif operation == "get":` appears 3× | ✅ Unique dispatch per (resource, op) | Fix code-convert |
| **continue_on_fail** | ❌ `self.continue_on_fail` | ✅ `self.node_data.continue_on_fail` | Fix code-convert |
| **API base URL** | ❌ `https://api.example.com` | ✅ Real service URL | Fix code-convert extraction |
| **NotImplementedError** | ❌ All 13 operations raise it | ✅ Implemented operations | Add validation gate |
| **Method duplication** | ❌ `_get`, `_getAll` defined 3× each | ✅ Unique method per operation | Fix code-convert |

### Generated discord.py Critical Issues

```python
# ISSUE 1: Operation-only dispatch (lines 103-127)
# "get" branch will NEVER reach message.get or member.get
if operation == "create":
    result = self._create(i, item_data)
elif operation == "get":
    result = self._get(i, item_data)  # Which resource??
elif operation == "get":  # UNREACHABLE
    result = self._get(i, item_data)
elif operation == "getAll":
    result = self._getAll(i, item_data)  # Which resource??
```

```python
# ISSUE 2: Wrong continue_on_fail access (line 141)
if self.continue_on_fail:  # ❌ Should be self.node_data.continue_on_fail
```

```python
# ISSUE 3: Placeholder URL (line 177)
url = f"https://api.example.com{endpoint}"  # ❌ Not Discord API
```

```python
# ISSUE 4: NotImplementedError (all operations)
raise NotImplementedError("create operation not implemented")  # ❌
```

```python
# ISSUE 5: Duplicate method definitions (lines 251, 327, 397)
def _get(self, ...):  # Defined 3 times
def _getAll(self, ...):  # Defined 3 times
```

---

## 4. Minimal Fix Set

### A. Fix Validation (MUST REJECT current discord.py)

**File:** `skills/node-validate/impl.py`

Add these checks:
1. `_check_not_implemented()` - Reject `raise NotImplementedError`
2. `_check_placeholder_urls()` - Reject `api.example.com`, `/endpoint`
3. `_check_resource_dispatch()` - If resource param exists, require resource+operation dispatch
4. `_check_continue_on_fail()` - Reject `self.continue_on_fail` (must use `self.node_data.continue_on_fail`)
5. Promote timeout check from warning to error

### B. Fix Code Generation (resource+operation dispatch)

**File:** `skills/code-convert/impl.py`

Change execute() generation:
1. If resource parameter exists → generate `resource = self.get_node_parameter("resource", i)`
2. Generate dispatch: `if resource == "channel" and operation == "create":`
3. Generate unique methods: `_channel_create()`, `_message_get()`, `_member_getAll()`
4. Fix `continue_on_fail` to use `self.node_data.continue_on_fail`

### C. Enable Smoke Test by Default

**Files:** 
- `skills/node-smoke-test/impl.py` - Add static checks
- `scripts/run_full_pipeline.py` - Include smoke-test in default flow

Add static checks:
1. No `NotImplementedError` in code
2. No `api.example.com` in code
3. No `/endpoint` placeholder in code

---

## 5. Test Coverage Required

New tests in `tests/test_node_validate.py`:

```python
def test_node_validate_rejects_notimplemented():
    """Validation must fail if NotImplementedError exists."""
    
def test_node_validate_rejects_placeholder_api():
    """Validation must fail if api.example.com exists."""
    
def test_node_validate_rejects_placeholder_endpoint():
    """Validation must fail if /endpoint placeholder exists."""

def test_node_validate_rejects_incorrect_dispatch():
    """Validation must fail if resource exists but dispatch is operation-only."""

def test_node_validate_rejects_wrong_continue_on_fail():
    """Validation must fail if self.continue_on_fail is used."""
```

---

## 6. Acceptance Criteria

After implementing fixes:

1. **Current discord.py MUST FAIL validation** for:
   - NotImplementedError (13 occurrences)
   - Placeholder URL (api.example.com)
   - Incorrect dispatch (operation-only with resource parameter)
   - Wrong continue_on_fail pattern

2. **Re-generated discord.py MUST PASS validation** with:
   - Resource+operation dispatch
   - No NotImplementedError
   - Real Discord API URL (`https://discord.com/api/v10`)
   - Correct `self.node_data.continue_on_fail`

3. **All new tests must pass**

---

## Files Changed by This Review

| File | Change Type | Purpose |
|------|-------------|---------|
| `skills/node-validate/impl.py` | MODIFY | Add 5 new validation checks |
| `skills/code-convert/impl.py` | MODIFY | Fix resource+operation dispatch generation |
| `skills/node-smoke-test/impl.py` | MODIFY | Add static pre-runtime checks |
| `scripts/run_full_pipeline.py` | MODIFY | Include smoke-test in default flow |
| `tests/test_node_validate.py` | CREATE | Tests for new validation invariants |
| `reports/DISCORD_PIPELINE_REVIEW.md` | CREATE | This document |
