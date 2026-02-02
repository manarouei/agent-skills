"""
Credential Provision Skill Implementation

Provisions credential instances for scenario testing via platform API.
DETERMINISTIC: No AI - pure API calls.
SYNC-CELERY SAFE: Uses synchronous HTTP client with timeouts.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from runtime.executor import ExecutionContext

from runtime.platform_client import PlatformClient, PlatformClientError, create_client_from_env
from runtime.protocol import AgentResponse, TaskState


def _resolve_env_var(value: str) -> str:
    """
    Resolve environment variable references in credential values.
    
    Supports:
    - ${VAR_NAME} - Required, fails if missing
    - ${VAR_NAME:-default} - Optional with default
    
    Args:
        value: String potentially containing env var references
    
    Returns:
        Resolved string
    
    Raises:
        ValueError: If required env var is missing
    """
    # Pattern: ${VAR_NAME} or ${VAR_NAME:-default}
    pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'
    
    def replacer(match):
        var_name = match.group(1)
        default_value = match.group(2)
        
        env_value = os.getenv(var_name)
        
        if env_value is not None:
            return env_value
        elif default_value is not None:
            return default_value
        else:
            raise ValueError(f"Required environment variable not set: {var_name}")
    
    return re.sub(pattern, replacer, value)


def _resolve_credential_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve all env var references in credential data."""
    resolved = {}
    
    for key, value in data.items():
        if isinstance(value, str):
            resolved[key] = _resolve_env_var(value)
        elif isinstance(value, dict):
            resolved[key] = _resolve_credential_data(value)
        elif isinstance(value, list):
            resolved[key] = [
                _resolve_env_var(item) if isinstance(item, str) else item
                for item in value
            ]
        else:
            resolved[key] = value
    
    return resolved


def _sanitize_credential(credential: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove sensitive data from credential for artifact storage.
    
    Keeps metadata, removes actual credential values.
    """
    sanitized = {
        "name": credential.get("name"),
        "type": credential.get("type"),
        "id": credential.get("id"),
        "created_at": credential.get("created_at"),
        "fields": list(credential.get("data", {}).keys()) if "data" in credential else [],
    }
    
    # Add any non-sensitive metadata
    for key in ["display_name", "description", "client_id"]:
        if key in credential:
            sanitized[key] = credential[key]
    
    return sanitized


def run(ctx: "ExecutionContext") -> dict[str, Any]:
    """
    Provision credential instances for scenario testing.
    
    Reads from:
    - inputs: credential_instances, platform_config
    - env vars: credential field values
    
    Writes to:
    - artifacts/{correlation_id}/credentials_provisioned.json
    """
    inputs = ctx.inputs
    correlation_id = inputs["correlation_id"]
    credential_instances = inputs["credential_instances"]
    platform_config = inputs.get("platform_config", {})
    force = inputs.get("force", False)
    
    ctx.log("credential_provision_start", {
        "correlation_id": correlation_id,
        "instance_count": len(credential_instances),
        "force": force,
    })
    
    # Setup paths
    artifact_base = ctx.artifact_root / correlation_id
    artifact_base.mkdir(parents=True, exist_ok=True)
    cache_file = artifact_base / "credentials_provisioned.json"
    
    # Check cache (idempotency)
    cached_credentials = {}
    if not force and cache_file.exists():
        try:
            cache_data = json.loads(cache_file.read_text())
            cached_credentials = {
                c["name"]: c for c in cache_data.get("credentials", [])
            }
            ctx.log("credential_cache_found", {
                "cached_count": len(cached_credentials),
            })
        except Exception as e:
            ctx.log("credential_cache_load_error", {"error": str(e)})
    
    # Initialize platform client
    try:
        if platform_config:
            client = PlatformClient(
                base_url=platform_config["base_url"],
                auth_token=platform_config["auth_token"],
                timeout=platform_config.get("timeout", 30),
            )
        else:
            # Try to create from env
            client = create_client_from_env()
    except Exception as e:
        ctx.log("platform_client_init_error", {"error": str(e)})
        return {
            "credentials_provisioned": [],
            "credentials_failed": [
                {
                    "name": "all",
                    "reason": f"Platform client initialization failed: {str(e)}"
                }
            ],
        }
    
    provisioned = []
    failed = []
    
    for instance in credential_instances:
        instance_name = instance["name"]
        instance_type = instance["type"]
        instance_data = instance["data"]
        
        try:
            # Check cache first
            if instance_name in cached_credentials:
                ctx.log("credential_using_cached", {
                    "name": instance_name,
                    "type": instance_type,
                })
                cached_cred = cached_credentials[instance_name]
                provisioned.append({
                    "name": instance_name,
                    "type": instance_type,
                    "id": cached_cred["id"],
                    "cached": True,
                })
                continue
            
            # Resolve env var references
            try:
                resolved_data = _resolve_credential_data(instance_data)
            except ValueError as e:
                ctx.log("credential_resolve_error", {
                    "name": instance_name,
                    "error": str(e),
                })
                failed.append({
                    "name": instance_name,
                    "reason": f"Environment variable resolution failed: {str(e)}"
                })
                continue
            
            # Create credential via API
            ctx.log("credential_creating", {
                "name": instance_name,
                "type": instance_type,
            })
            
            result = client.credentials.create(
                name=instance_name,
                credential_type=instance_type,
                data=resolved_data,
            )
            
            credential_id = result.get("id") or result.get("credential_id")
            
            if not credential_id:
                raise ValueError("No credential ID in response")
            
            ctx.log("credential_created", {
                "name": instance_name,
                "id": credential_id,
            })
            
            provisioned.append({
                "name": instance_name,
                "type": instance_type,
                "id": credential_id,
                "cached": False,
            })
            
        except PlatformClientError as e:
            ctx.log("credential_provision_error", {
                "name": instance_name,
                "error": str(e),
            })
            failed.append({
                "name": instance_name,
                "reason": f"Platform API error: {str(e)}"
            })
        except Exception as e:
            ctx.log("credential_provision_unexpected_error", {
                "name": instance_name,
                "error": str(e),
            })
            failed.append({
                "name": instance_name,
                "reason": f"Unexpected error: {str(e)}"
            })
    
    # Write cache/output file
    output_data = {
        "correlation_id": correlation_id,
        "timestamp": datetime.utcnow().isoformat(),
        "credentials": [
            {
                "name": p["name"],
                "type": p["type"],
                "id": p["id"],
                "cached": p.get("cached", False),
                "created_at": datetime.utcnow().isoformat(),
            }
            for p in provisioned
        ],
    }
    
    cache_file.write_text(json.dumps(output_data, indent=2))
    
    ctx.log("credential_provision_complete", {
        "provisioned": len(provisioned),
        "failed": len(failed),
    })
    
    return {
        "credentials_provisioned": provisioned,
        "credentials_failed": failed,
    }
