---
name: credential-convert
version: "1.0.0"
description: Convert n8n TypeScript credential definitions to Python credential types for the backend platform. Extracts fields, auth mechanisms, generates Python credential class matching golden patterns, prepares for registry update.

# Contract
autonomy_level: IMPLEMENT
side_effects: [fs]
timeout_seconds: 180
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id + credential_type"
max_fix_iterations: 2

# Filesystem scope: ARTIFACT - writes to artifact directory only
# The apply-credential skill will handle actual target repo writes
fs_scope: artifact

# Sync Celery Constraints (MANDATORY)
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: false
  forbids_background_tasks: true

# Execution mode: HYBRID (deterministic parsing + AI fallback)
execution_mode: HYBRID

input_schema:
  type: object
  required: [correlation_id, credential_types, source_bundle_path]
  properties:
    correlation_id:
      type: string
      description: Session correlation ID for artifact paths
    credential_types:
      type: array
      items:
        type: string
      description: List of credential type names to convert (e.g., ["bitlyApi"])
    source_bundle_path:
      type: string
      description: Path to source_bundle/ containing TS credential files
    back_project_path:
      type: string
      description: Optional path to back project for reading existing patterns
      default: ""

output_schema:
  type: object
  required: [credentials_converted, credentials_skipped]
  properties:
    credentials_converted:
      type: array
      items:
        type: object
        properties:
          name:
            type: string
          output_file:
            type: string
          fields:
            type: array
          auth_type:
            type: string
    credentials_skipped:
      type: array
      items:
        type: object
        properties:
          name:
            type: string
          reason:
            type: string
    registry_entries:
      type: array
      items:
        type: object
      description: Registry import/dict entries for apply step

required_artifacts:
  - name: credentials/
    type: directory
    description: Generated Python credential files
  - name: credential_conversion_log.json
    type: json
    description: Conversion decisions and mappings
  - name: credential_registry_entries.json
    type: json
    description: Import statements and dict entries for registry

failure_modes: [parse_error, validation_error, missing_source]
depends_on: [source-ingest, schema-infer]
---

# Credential Convert

Convert n8n TypeScript credential definitions to Python credential implementations.

## Purpose

This skill:
1. Parses n8n TS credential files from source_bundle/
2. Extracts properties (fields), auth mechanisms, test endpoints
3. Generates Python credential classes following BaseCredential patterns
4. Prepares registry entries for later application
5. Validates against KB auth patterns

## Input Sources

- **TYPE1 (TS credential file)**: Preferred - parse actual TS credential definition
- **Fallback (inferred schema)**: Extract credential requirements from node schema

## Output Structure

```
artifacts/{correlation_id}/
├── credentials/
│   ├── bitlyApi.py
│   └── postgresApi.py
├── credential_conversion_log.json
└── credential_registry_entries.json
```

## KB Patterns Used

- `auth-001`: BaseCredential Structure
- `auth-002`: OAuth2 Stateless Token Refresh
- `auth-004`: API Key Credential
- `auth-005`: Database Connection Credential

## Validation

Generated credentials must:
- Inherit from BaseCredential
- Define `name`, `display_name`, `properties` class attributes
- Implement `test()` method (async with timeout)
- Implement `validate()` method (inherited from base, may override)
- Have no async in synchronous paths (Celery-safe)
- All HTTP calls must have explicit timeouts

## Error Handling

- Missing TS credential file: Use inferred schema from node properties
- Unparseable TS: Log warning, attempt pattern matching
- Unknown auth mechanism: Default to generic API key pattern
- Duplicate credential type: Skip with warning
