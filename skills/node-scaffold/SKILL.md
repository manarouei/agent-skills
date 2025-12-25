---
name: node-scaffold
description: Generate node implementation scaffold from schema. Creates file structure, base classes, and boilerplate code for the node. Use when schema is complete and you need the basic implementation structure.
---

# Node Scaffold

Generate implementation scaffold from node schema.

## When to use this skill

Use this skill when:
- Formal schema is complete and validated
- Ready to create implementation files
- Need consistent file structure
- Preparing for code implementation

## Scaffold structure

Generate the following file structure:

```
nodes/{NodeName}/
├── __init__.py
├── {node_name}.py          # Main node class
├── {node_name}_methods.py  # Operation implementations
├── credentials.py          # Credential type definition
└── types.py               # Type definitions
```

## File templates

### Main node class
- Inherits from base node class
- Defines node properties
- Routes operations to methods

### Methods module
- One function per operation
- Stub implementations with TODO markers
- Type hints from schema

### Credentials
- Credential class matching auth type
- Field definitions
- Validation methods

### Types
- Pydantic models for parameters
- Enum definitions for options
- Response type definitions

## Scaffold guidelines

- Use schema exactly, don't add fields
- Include all operations from schema
- Add docstrings from descriptions
- Mark all implementation TODOs
- Follow target framework conventions
