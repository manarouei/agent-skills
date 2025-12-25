---
name: schema-infer
description: Infer node schema from ingested source materials. Analyzes TypeScript properties or API documentation to determine node structure, parameters, authentication, and operations. Use when source has been ingested and you need to understand the node interface.
---

# Schema Infer

Analyze ingested source to infer node schema structure.

## When to use this skill

Use this skill when:
- Source materials have been ingested
- Need to understand node parameters and options
- Need to identify authentication requirements
- Preparing to build formal schema

## Inference from TypeScript (Type1)

Extract from n8n TypeScript node:

### Properties
- Parameter definitions from `description.properties`
- Display options and conditional fields
- Default values and placeholders

### Operations
- Resources and operations arrays
- Method routing logic
- Request construction patterns

### Authentication
- Credential type references
- Auth header construction
- OAuth flow indicators

## Inference from Documentation (Type2)

Extract from API documentation:

### Endpoints
- HTTP methods and paths
- Path parameters
- Query parameters

### Request Bodies
- JSON schemas
- Required vs optional fields
- Field types and formats

### Authentication
- Auth type (API key, OAuth, Basic)
- Header or parameter location
- Token refresh patterns

## Output structure

Generate intermediate schema with:
- Operations list with parameters
- Authentication configuration
- Input/output schemas
- Validation rules
