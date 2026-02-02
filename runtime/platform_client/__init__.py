"""
Platform Client - Sync HTTP Client for Back Project APIs

Provides synchronous (Celery-safe) interface to:
- Credential management (/api/credentials)
- Workflow management (/api/workflows)
- Workflow execution (REST + WebSocket)

SYNC-CELERY SAFE: Uses requests library with explicit timeouts.
NO async/await patterns.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests


@dataclass
class PlatformConfig:
    """Configuration for platform client."""
    base_url: str
    auth_token: str
    timeout: int = 30
    verify_ssl: bool = True


class PlatformClientError(Exception):
    """Base exception for platform client errors."""
    pass


class CredentialClient:
    """Client for credential management APIs."""
    
    def __init__(self, config: PlatformConfig):
        self.config = config
        self.base_url = config.base_url.rstrip("/")
    
    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Dict[str, Any] | None = None,
        params: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to platform."""
        url = urljoin(self.base_url, endpoint)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.auth_token}",
        }
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise PlatformClientError(f"Request timeout after {self.config.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise PlatformClientError(f"Connection error: {e}")
        except requests.exceptions.HTTPError as e:
            raise PlatformClientError(f"HTTP error {e.response.status_code}: {e.response.text}")
    
    def create(
        self,
        name: str,
        credential_type: str,
        data: Dict[str, Any],
        client_id: str | None = None,
    ) -> Dict[str, Any]:
        """
        Create a new credential instance.
        
        Args:
            name: Credential instance name
            credential_type: Credential type (e.g., "bitlyApi")
            data: Credential field values
            client_id: Optional client ID
        
        Returns:
            Created credential with id
        """
        payload = {
            "name": name,
            "type": credential_type,
            "data": data,
        }
        
        if client_id:
            payload["client_id"] = client_id
        
        return self._request("POST", "/api/credentials", json_data=payload)
    
    def get(self, credential_id: str) -> Dict[str, Any]:
        """Get credential by ID."""
        return self._request("GET", f"/api/credentials/{credential_id}")
    
    def list(self, credential_type: str | None = None) -> List[Dict[str, Any]]:
        """List credentials, optionally filtered by type."""
        params = {"type": credential_type} if credential_type else None
        result = self._request("GET", "/api/credentials", params=params)
        return result.get("credentials", [])
    
    def test(self, credential_id: str) -> Dict[str, Any]:
        """Test a credential."""
        return self._request("POST", f"/api/credentials/{credential_id}/test")
    
    def delete(self, credential_id: str) -> Dict[str, Any]:
        """Delete a credential."""
        return self._request("DELETE", f"/api/credentials/{credential_id}")


class WorkflowClient:
    """Client for workflow management and execution APIs."""
    
    def __init__(self, config: PlatformConfig):
        self.config = config
        self.base_url = config.base_url.rstrip("/")
    
    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Dict[str, Any] | None = None,
        params: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Make authenticated request to platform."""
        url = urljoin(self.base_url, endpoint)
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.auth_token}",
        }
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            raise PlatformClientError(f"Request timeout after {self.config.timeout}s")
        except requests.exceptions.ConnectionError as e:
            raise PlatformClientError(f"Connection error: {e}")
        except requests.exceptions.HTTPError as e:
            raise PlatformClientError(f"HTTP error {e.response.status_code}: {e.response.text}")
    
    def create(
        self,
        name: str,
        workflow_data: Dict[str, Any],
        active: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a new workflow.
        
        Args:
            name: Workflow name
            workflow_data: Workflow definition (nodes, connections)
            active: Whether workflow is active
        
        Returns:
            Created workflow with id
        """
        payload = {
            "name": name,
            "workflow": workflow_data,
            "active": active,
        }
        
        return self._request("POST", "/api/workflows", json_data=payload)
    
    def get(self, workflow_id: str) -> Dict[str, Any]:
        """Get workflow by ID."""
        return self._request("GET", f"/api/workflows/{workflow_id}")
    
    def list(self) -> List[Dict[str, Any]]:
        """List all workflows."""
        result = self._request("GET", "/api/workflows")
        return result.get("workflows", [])
    
    def execute_rest(
        self,
        workflow_id: str,
        input_data: Dict[str, Any] | None = None,
        wait_for_completion: bool = True,
        timeout: int | None = None,
    ) -> Dict[str, Any]:
        """
        Execute workflow via REST API.
        
        Args:
            workflow_id: Workflow ID to execute
            input_data: Optional input data for trigger node
            wait_for_completion: If True, poll until completion
            timeout: Max wait time in seconds
        
        Returns:
            Execution result
        """
        payload = {"input_data": input_data or {}}
        
        # Start execution
        result = self._request("POST", f"/api/workflows/{workflow_id}/execute", json_data=payload)
        execution_id = result.get("execution_id")
        
        if not wait_for_completion or not execution_id:
            return result
        
        # Poll for completion
        max_wait = timeout or 60
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            status = self._request("GET", f"/api/executions/{execution_id}")
            
            if status.get("status") in ["completed", "error", "failed"]:
                return status
            
            time.sleep(1)
        
        raise PlatformClientError(f"Execution timeout after {max_wait}s")
    
    def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """Get execution status and results."""
        return self._request("GET", f"/api/executions/{execution_id}")
    
    def delete(self, workflow_id: str) -> Dict[str, Any]:
        """Delete a workflow."""
        return self._request("DELETE", f"/api/workflows/{workflow_id}")


class PlatformClient:
    """
    Main platform client providing access to all APIs.
    
    SYNC-CELERY SAFE: All methods are synchronous with explicit timeouts.
    """
    
    def __init__(
        self,
        base_url: str,
        auth_token: str,
        timeout: int = 30,
        verify_ssl: bool = True,
    ):
        """
        Initialize platform client.
        
        Args:
            base_url: Base URL of platform (e.g., "http://localhost:8000")
            auth_token: Authentication token
            timeout: Default request timeout in seconds
            verify_ssl: Whether to verify SSL certificates
        """
        self.config = PlatformConfig(
            base_url=base_url,
            auth_token=auth_token,
            timeout=timeout,
            verify_ssl=verify_ssl,
        )
        
        self.credentials = CredentialClient(self.config)
        self.workflows = WorkflowClient(self.config)
    
    def health_check(self) -> Dict[str, Any]:
        """Check platform health."""
        url = urljoin(self.config.base_url, "/health")
        
        try:
            response = requests.get(
                url,
                timeout=self.config.timeout,
                verify=self.config.verify_ssl,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise PlatformClientError(f"Health check failed: {e}")


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_client_from_env() -> PlatformClient:
    """
    Create platform client from environment variables.
    
    Expected env vars:
    - PLATFORM_BASE_URL (default: http://localhost:8000)
    - PLATFORM_AUTH_TOKEN (required)
    - PLATFORM_TIMEOUT (default: 30)
    - PLATFORM_VERIFY_SSL (default: true)
    """
    import os
    
    base_url = os.getenv("PLATFORM_BASE_URL", "http://localhost:8000")
    auth_token = os.getenv("PLATFORM_AUTH_TOKEN")
    
    if not auth_token:
        raise ValueError("PLATFORM_AUTH_TOKEN environment variable required")
    
    timeout = int(os.getenv("PLATFORM_TIMEOUT", "30"))
    verify_ssl = os.getenv("PLATFORM_VERIFY_SSL", "true").lower() == "true"
    
    return PlatformClient(
        base_url=base_url,
        auth_token=auth_token,
        timeout=timeout,
        verify_ssl=verify_ssl,
    )


def create_client_from_config(config_path: Path) -> PlatformClient:
    """
    Create platform client from JSON config file.
    
    Config format:
    {
        "base_url": "http://localhost:8000",
        "auth_token": "token",
        "timeout": 30,
        "verify_ssl": true
    }
    """
    config_data = json.loads(config_path.read_text())
    
    return PlatformClient(
        base_url=config_data["base_url"],
        auth_token=config_data["auth_token"],
        timeout=config_data.get("timeout", 30),
        verify_ssl=config_data.get("verify_ssl", True),
    )
