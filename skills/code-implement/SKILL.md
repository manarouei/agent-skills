---
name: code-implement
description: Implement node operations from documentation using LLM. For Type2 sources without existing code, generates implementation based on API documentation and schema. Use when implementing a node from documentation only.
---

# Code Implement

Generate node implementation from documentation.

## When to use this skill

Use this skill when:
- Source is Type2 (documentation only)
- Scaffold has been generated
- Schema defines all operations
- No existing code to convert

## Implementation process

### 1. For each operation
- Read operation definition from schema
- Review relevant documentation
- Identify API endpoint and method
- Determine request construction

### 2. Generate method implementation
- Build request URL with parameters
- Construct request body if needed
- Add authentication headers
- Handle response parsing

### 3. Add error handling
- HTTP error responses
- API-specific error formats
- Validation errors
- Timeout handling

### 4. Support features
- Pagination where documented
- Rate limiting if specified
- Retry logic for transient errors

## Implementation guidelines

- Follow API documentation exactly
- Use documented error codes
- Implement all documented parameters
- Add TODO for undocumented behavior
- Request clarification for ambiguity

## Code quality

- Type hints for all parameters
- Docstrings with operation description
- Inline comments for complex logic
- Consistent error message format

## Output

Generate implementation in scaffold files:
- Methods in `{node_name}_methods.py`
- Types in `types.py` if needed
