---
name: credential-provision
version: "1.0.0"
description: Provision credential instances for scenario testing. Creates credentials via platform API, handles idempotency, writes artifacts for later test use.

# Contract
autonomy_level: IMPLEMENT
side_effects: [net]
timeout_seconds: 60
retry:
  policy: exponential
  max_retries: 2
idempotency:
  required: true
  key_spec: "correlation_id + credential_type"
max_fix_iterations: 1

# Filesystem scope: ARTIFACT - writes to artifact directory only
fs_scope: artifact

# Sync Celery Constraints (MANDATORY)
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: true
  forbids_background_tasks: true

# Execution mode: DETERMINISTIC (no AI)
execution_mode: DETERMINISTIC

input_schema:
  type: object
  required: [correlation_id, credential_instances]
  properties:
    correlation_id:
      type: string
      description: Session correlation ID for artifact paths
    credential_instances:
      type: array
      items:
        type: object
        required: [name, type, data]
        properties:
          name:
            type: string
            description: Instance name (e.g., "test-bitly-001")
          type:
            type: string
            description: Credential type (e.g., "bitlyApi")
          data:
            type: object
            description: Credential field values
      description: List of credential instances to provision
    platform_config:
      type: object
      description: Platform connection config (base_url, auth_token)
    force:
      type: boolean
      default: false
      description: Force re-provisioning even if cached

output_schema:
  type: object
  required: [credentials_provisioned, credentials_failed]
  properties:
    credentials_provisioned:
      type: array
      items:
        type: object
        properties:
          name:
            type: string
          type:
            type: string
          id:
            type: string
          cached:
            type: boolean
    credentials_failed:
      type: array
      items:
        type: object
        properties:
          name:
            type: string
          reason:
            type: string

required_artifacts:
  - name: credentials_provisioned.json
    type: json
    description: Provisioned credential metadata (sanitized, no secrets)

failure_modes: [network_error, authentication_error, validation_error]
depends_on: [credential-convert]
---

# Credential Provision

Provision credential instances for scenario testing.

## Purpose

This skill:
1. Takes credential definitions with test values
2. Posts to platform /api/credentials endpoint
3. Handles idempotency (checks cache before creating)
4. Writes sanitized credential metadata (no secrets in artifacts)

## Input Format

```yaml
credential_instances:
  - name: "test-bitly-001"
    type: "bitlyApi"
    data:
      accessToken: "${BITLY_TEST_TOKEN}"  # from env
      baseUrl: "https://api-ssl.bitly.com/v4"
```

## Output Artifacts

```
artifacts/{correlation_id}/
├── credentials_provisioned.json
│   {
│     "credentials": [
│       {
│         "name": "test-bitly-001",
│         "type": "bitlyApi",
│         "id": "cred_abc123",
│         "created_at": "2025-01-06T...",
│         "fields": ["accessToken", "baseUrl"]
│       }
│     ]
│   }
```

## Environment Variables

Credentials can reference environment variables:
- `${VAR_NAME}` - Required, fails if missing
- `${VAR_NAME:-default}` - Optional with default

Common test credential env vars:
- `BITLY_TEST_TOKEN`
- `POSTGRES_TEST_URL`
- `DISCORD_TEST_TOKEN`
- `SLACK_TEST_TOKEN`

## Idempotency

If `credentials_provisioned.json` exists and `force=false`:
- Reuse existing credential IDs
- Skip API calls

## Security

- Never write secrets to artifact files
- Sanitize all credential data in output JSON
- Use platform's encryption for credential storage
