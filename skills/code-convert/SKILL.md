---
name: code-convert
description: Convert TypeScript node code to Python implementation. For Type1 sources with existing n8n TypeScript code, performs language conversion while preserving logic. Use when implementing a node with existing TypeScript source.
---

# Code Convert

Convert n8n TypeScript node code to Python.

## When to use this skill

Use this skill when:
- Source is Type1 (existing TypeScript node)
- Scaffold has been generated
- Need to convert TypeScript logic to Python
- NOT for Type2 documentation-only sources

## Conversion process

### 1. Parse TypeScript structure
- Identify execute/trigger methods
- Map operation routing logic
- Extract API call patterns

### 2. Convert language constructs
- TypeScript interfaces → Python dataclasses/Pydantic
- async/await → Python async
- Type annotations → Python type hints
- Arrow functions → Python functions

### 3. Convert n8n patterns
- `this.helpers.request()` → httpx/requests calls
- `this.getNodeParameter()` → parameter access
- `this.getCredentials()` → credential loading
- Binary data handling → Python equivalent

### 4. Preserve logic
- Keep operation routing structure
- Maintain error handling patterns
- Preserve pagination logic
- Keep retry mechanisms

## Conversion guidelines

- Don't optimize during conversion
- Preserve original logic exactly
- Mark unclear patterns with TODO
- Keep same function names where possible
- Test conversion incrementally

## Output

Place converted code in scaffold files:
- Main logic in `{node_name}_methods.py`
- Update imports in `{node_name}.py`
