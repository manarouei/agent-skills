#!/usr/bin/env python3
"""
HTTP REST Backend Converter

Converts HTTP/REST API nodes (GitHub, GitLab, Slack, Discord, etc.)
to Python BaseNode implementations.

This is the original conversion logic, now isolated as a backend.
"""

from __future__ import annotations
import re
from string import Template
from typing import Any, Dict, List


# Known base URLs for common services
KNOWN_BASE_URLS: Dict[str, str] = {
    "github": "https://api.github.com",
    "gitlab": "https://gitlab.com/api/v4",
    "slack": "https://slack.com/api",
    "discord": "https://discord.com/api/v10",
    "trello": "https://api.trello.com/1",
    "twitter": "https://api.twitter.com/2",
    "bitly": "https://api-ssl.bitly.com",
    "airtable": "https://api.airtable.com/v0",
    "shopify": "",  # From credentials
    "openproject": "https://community.openproject.org/api/v3",
    "wordpress": "",  # From credentials
    "woocommerce": "",  # From credentials
    "linkedin": "https://api.linkedin.com/v2",
}


def convert_http_rest_node(
    node_name: str,
    node_schema: Dict[str, Any],
    ts_code: str,
    properties: List[Dict[str, Any]],
    execution_contract: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert an HTTP/REST API node to Python.
    
    Args:
        node_name: Node type name
        node_schema: Complete inferred schema
        ts_code: Raw TypeScript source code
        properties: Node parameters
        execution_contract: The node's execution contract
    
    Returns:
        Dict with python_code, imports, helpers, conversion_notes
    """
    node_name_lower = node_name.lower().replace("-", "").replace("_", "")
    http_config = execution_contract.get("http_config", {})
    credentials = execution_contract.get("credentials", {})
    
    # Determine base URL
    base_url = http_config.get("base_url") or KNOWN_BASE_URLS.get(node_name_lower, "")
    base_url_from_credentials = http_config.get("base_url_from_credentials", False)
    
    if not base_url and not base_url_from_credentials:
        # Try to extract from TypeScript
        uri_match = re.search(r"uri:\s*['\"`]([^'\"$`]+)", ts_code)
        if uri_match:
            base_url = uri_match.group(1)
        else:
            url_match = re.search(r"url:\s*['\"]([^'\"]+)['\"]", ts_code)
            if url_match:
                base_url = url_match.group(1)
    
    if not base_url and not base_url_from_credentials:
        base_url_from_credentials = True  # Fallback to credentials
    
    # Determine auth type
    auth_header = http_config.get("auth_header", "bearer")
    has_auth_selector = any(p.get("name") == "authentication" for p in properties)
    
    # Build credential code
    cred_type = credentials.get("type", f"{node_name_lower}Api")
    if has_auth_selector:
        credential_code = f'''
        # Respect authentication selector
        auth_type = self.get_node_parameter('authentication', 0)
        if auth_type == 'oAuth2':
            credentials = self.get_credentials("{node_name_lower}OAuth2Api")
        else:
            credentials = self.get_credentials("{cred_type}")'''
    else:
        credential_code = f'''
        credentials = self.get_credentials("{cred_type}")'''
    
    # Build URL construction code
    if base_url_from_credentials:
        url_code = '''
        base_url = credentials.get("server", credentials.get("baseUrl", ""))
        if not base_url:
            raise ValueError("Base URL not found in credentials")
        url = f"{base_url}{endpoint}"'''
    else:
        url_code = f'''
        url = f"{{self.BASE_URL}}{{endpoint}}"'''
    
    # Build auth header code
    if auth_header == "bearer":
        auth_code = '''
        token = credentials.get("accessToken", credentials.get("token", credentials.get("apiKey", "")))
        headers["Authorization"] = f"Bearer {token}"'''
    elif auth_header == "token":
        auth_code = '''
        token = credentials.get("accessToken", credentials.get("token", credentials.get("apiKey", "")))
        headers["Authorization"] = f"token {token}"'''
    else:
        auth_code = '''
        token = credentials.get("accessToken", credentials.get("token", credentials.get("apiKey", "")))
        headers["Authorization"] = f"Bearer {token}"'''
    
    # Generate helper methods
    helpers = f'''
    # API Base URL
    BASE_URL = "{base_url}"
    
    def _api_request(
        self,
        method: str,
        endpoint: str,
        body: Dict[str, Any] | None = None,
        query: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated API request.
        
        SYNC-CELERY SAFE: Uses requests with timeout.
        """
        import requests
        {credential_code}
        
        headers = {{"Accept": "application/json", "Content-Type": "application/json"}}
        {auth_code}
        {url_code}
        
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=body,
            params=query,
            timeout=30,
        )
        response.raise_for_status()
        
        if response.content:
            return response.json()
        return {{}}
    
    def _api_request_all_items(
        self,
        method: str,
        endpoint: str,
        body: Dict[str, Any] | None = None,
        query: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """
        Make paginated API request, returning all items.
        
        SYNC-CELERY SAFE: Uses requests with timeout.
        """
        all_items = []
        query = query or {{}}
        page = 1
        per_page = 100
        
        while True:
            query["page"] = page
            query["per_page"] = per_page
            
            response = self._api_request(method, endpoint, body, query)
            
            # Handle different pagination formats
            if isinstance(response, list):
                items = response
            elif isinstance(response, dict):
                items = response.get("items", response.get("data", []))
            else:
                break
            
            if not items:
                break
            
            all_items.extend(items)
            
            if len(items) < per_page:
                break
            
            page += 1
        
        return all_items
'''
    
    # Generate imports
    imports = [
        "import requests",
        "from typing import Any, Dict, List",
        "from urllib.parse import quote",
    ]
    
    conversion_notes = [
        f"Using http_rest backend for {node_name}",
        f"Base URL: {base_url or 'from credentials'}",
        f"Auth type: {auth_header}",
        f"Credential type: {cred_type}",
    ]
    
    return {
        "python_code": "",  # Operation handlers generated separately
        "imports": imports,
        "helpers": helpers,
        "conversion_notes": conversion_notes,
        "base_url": base_url,
        "credential_type": cred_type,
    }
