---
name: code-validate
description: Validate node implementation against schema and quality standards. Runs static analysis, type checking, and test suite. Identifies issues requiring fixes. Use when implementation and tests are complete.
---

# Code Validate

Validate implementation against requirements.

## When to use this skill

Use this skill when:
- Implementation is complete
- Tests have been generated
- Ready to verify quality
- Before code-fix phase

## Validation checks

### Schema compliance
- All operations from schema implemented
- All parameters handled
- Auth type matches schema
- Types match schema definitions

### Code quality
- Python syntax valid
- Type hints present
- No undefined names
- Imports resolved

### Static analysis
- Run pylint/ruff checks
- No critical issues
- Complexity within limits
- Consistent style

### Type checking
- Run mypy/pyright
- No type errors
- Proper generic usage
- Return types correct

### Test execution
- All tests pass
- No skipped required tests
- Coverage meets threshold

## Validation output

Generate validation report:
```yaml
validation_result:
  passed: boolean
  checks:
    schema_compliance:
      passed: boolean
      issues: list
    code_quality:
      passed: boolean
      issues: list
    static_analysis:
      passed: boolean
      issues: list
    type_checking:
      passed: boolean
      issues: list
    tests:
      passed: boolean
      failed_tests: list
      coverage: number
```

## Issue severity

- CRITICAL: Must fix before proceeding
- WARNING: Should fix, may proceed
- INFO: Suggestion only
