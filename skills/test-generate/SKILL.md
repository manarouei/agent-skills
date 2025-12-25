---
name: test-generate
description: Generate unit and integration tests for node implementation. Creates test cases covering operations, error handling, and edge cases. Use when implementation is complete and you need test coverage.
---

# Test Generate

Create tests for node implementation.

## When to use this skill

Use this skill when:
- Node implementation is complete
- Need unit tests for operations
- Need integration test patterns
- Preparing for validation phase

## Test structure

Generate test files:
```
tests/
├── test_{node_name}.py       # Unit tests
├── test_{node_name}_integration.py  # Integration tests
└── conftest.py              # Fixtures
```

## Unit tests

For each operation, generate:

### Happy path tests
- Valid input produces expected output
- All parameters handled correctly
- Response properly parsed

### Error handling tests
- Invalid input raises appropriate error
- API errors handled correctly
- Missing required fields detected

### Edge cases
- Empty responses
- Large data sets
- Special characters in input
- Boundary values

## Integration tests

Generate patterns for:
- Live API testing (skipped by default)
- Mock server testing
- Credential handling

## Test guidelines

- Use pytest framework
- Mock external API calls in unit tests
- Use fixtures for common setup
- Parametrize similar tests
- Clear test names describing scenario

## Fixtures

Generate fixtures for:
- Mock credentials
- Sample input data
- Expected responses
- Error responses
