---
name: code-fix
description: Fix issues identified during validation. Addresses code quality, type errors, and test failures. Iterates until validation passes. Use when validation has identified issues to fix.
---

# Code Fix

Fix issues from validation.

## When to use this skill

Use this skill when:
- Validation has completed
- Issues were identified
- Need to iterate on fixes
- Preparing for final validation

## Fix process

### 1. Prioritize issues
- CRITICAL issues first
- Then WARNING issues
- INFO issues if time permits

### 2. For each issue

#### Code quality issues
- Fix syntax errors
- Add missing imports
- Resolve undefined names
- Add type hints

#### Static analysis issues
- Reduce complexity
- Fix style violations
- Address security warnings
- Remove unused code

#### Type errors
- Fix type mismatches
- Add proper type hints
- Use correct generics
- Handle Optional types

#### Test failures
- Debug failing tests
- Fix implementation bugs
- Update test expectations if wrong
- Add missing test cases

### 3. Re-validate
- Run validation after each fix
- Confirm issue resolved
- Check for new issues introduced

## Fix guidelines

- One issue at a time
- Minimal changes per fix
- Document non-obvious fixes
- Don't introduce new issues
- Preserve existing behavior

## Iteration limits

- Maximum 3 fix iterations per issue
- Escalate if still failing
- Flag issues needing human review
