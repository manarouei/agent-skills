---
name: schema-build
description: Build formal node schema from inferred data. Creates complete JSON schema defining node interface, parameters, operations, and validation rules. Use when inference is complete and you need a formal schema specification.
---

# Schema Build

Create formal node schema from inferred structure.

## When to use this skill

Use this skill when:
- Schema inference is complete
- Need formal JSON schema for code generation
- Need to validate node interface design
- Preparing for scaffold and implementation

## Schema structure

Build complete node schema with:

### Node metadata
```yaml
name: string (kebab-case)
display_name: string
version: string (semver)
description: string
category: string
```

### Authentication
```yaml
auth:
  type: api_key | oauth2 | basic | none
  credential_name: string
  fields:
    - name: string
      type: string
      required: boolean
```

### Operations
```yaml
operations:
  - name: string
    display_name: string
    description: string
    parameters:
      - name: string
        type: string | number | boolean | array | object
        required: boolean
        default: any
        options: array (if enum)
```

### Input/Output
```yaml
inputs:
  - name: main
    type: any
outputs:
  - name: main  
    type: any
```

## Validation

Validate schema for:
- Required fields present
- Valid types used
- Consistent naming
- No duplicate operations
- Auth type compatibility
