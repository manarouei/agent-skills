---
name: repo-ground
version: "1.1.0"
description: Produce repo_facts.json and target_repo_layout.json by reading canonical sources. Required before code-generation skills.

# Contract
autonomy_level: IMPLEMENT
side_effects: [fs]
timeout_seconds: 60
retry:
  policy: none
  max_retries: 0
idempotency:
  required: true
  key_spec: "correlation_id"
max_fix_iterations: 1

fs_scope: artifacts

sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
  requires_timeouts_on_external_calls: false
  forbids_background_tasks: true

input_schema:
  type: object
  required: [correlation_id, repo_root]
  properties:
    correlation_id:
      type: string
    repo_root:
      type: string

output_schema:
  type: object
  required: [repo_facts_path, repo_facts, target_repo_layout_path, target_repo_layout]
  properties:
    repo_facts_path:
      type: string
    repo_facts:
      type: object
    target_repo_layout_path:
      type: string
    target_repo_layout:
      type: object

required_artifacts:
  - name: repo_facts.json
    type: json
    description: Repository grounding facts
  - name: target_repo_layout.json
    type: json
    description: Target repository layout conventions

failure_modes: [validation_error, permission_denied]
depends_on: []
---

# Repo Ground

Produces repo_facts.json and target_repo_layout.json by reading canonical sources.
