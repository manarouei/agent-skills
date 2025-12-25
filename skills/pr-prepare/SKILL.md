---
name: pr-prepare
description: Prepare implementation for pull request submission. Generates PR description, changelog entry, and final documentation. Performs final checks before submission. Use when implementation is validated and ready for review.
---

# PR Prepare

Prepare implementation for submission.

## When to use this skill

Use this skill when:
- All validation passes
- Implementation is complete
- Ready to submit for review
- Need PR artifacts

## Preparation steps

### 1. Final validation
- Run full validation suite
- Confirm all checks pass
- No outstanding issues

### 2. Generate PR description
Create PR template with:
- Summary of changes
- Implementation approach
- Breaking changes (if any)
- Testing performed
- Related issues/tickets

### 3. Update changelog
Add entry with:
- Node name and version
- New operations added
- Dependencies added
- Breaking changes

### 4. Generate documentation
- Update node documentation
- Add usage examples
- Document configuration options

### 5. Pre-submission checklist
- [ ] All tests pass
- [ ] No linting errors
- [ ] Types checked
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] PR description complete

## Output artifacts

Generate in artifacts directory:
```
artifacts/
├── pr_description.md
├── changelog_entry.md
└── submission_checklist.md
```

## PR description template

```markdown
## Summary
Brief description of the node implementation.

## Changes
- Added {NodeName} node with operations: ...
- Added credential type: ...

## Implementation Notes
- Source type: Type1/Type2
- Approach: Conversion/LLM implementation

## Testing
- Unit tests: X passing
- Coverage: X%

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] Changelog updated
```
