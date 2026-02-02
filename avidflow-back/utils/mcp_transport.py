"""
MCP Transport Layer

Pluggable transport implementations for different MCP server types.
"""

import logging
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod
import httpx

logger = logging.getLogger(__name__)


class MCPTransport(ABC):
    """Base class for MCP transport implementations"""
    
    @abstractmethod
    def send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Send MCP JSON-RPC request and return response"""
        pass
    
    @abstractmethod
    def is_alive(self) -> bool:
        """Check if connection is still alive"""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Close the connection"""
        pass


class GenericSSETransport(MCPTransport):
    """Standard MCP SSE transport (uses /message endpoint)"""
    
    def __init__(self, url: str, client: httpx.Client, timeout: int = 30):
        self.url = url
        self.client = client
        self.timeout = timeout
        self.message_id = 1
        self.message_endpoint = f"{url}/message"
    
    def send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        request = {
            "jsonrpc": "2.0",
            "id": self.message_id,
            "method": method,
            "params": params
        }
        self.message_id += 1
        
        logger.debug(f"Generic SSE - Sending {method} to {self.message_endpoint}")
        
        response = self.client.post(
            self.message_endpoint,
            json=request,
            timeout=self.timeout,
            follow_redirects=True
        )
        response.raise_for_status()
        
        result = response.json()
        if "error" in result:
            raise ValueError(f"MCP error: {result['error']}")
        
        return result
    
    def is_alive(self) -> bool:
        return self.client is not None
    
    def close(self) -> None:
        if self.client:
            self.client.close()


class ShopifySSETransport(MCPTransport):
    """
    Shopify-specific MCP SSE transport.
    
    Key differences:
    - No /message suffix (endpoint is just /api/mcp)
    - Requires password authentication flow
    - Cookie-based session management
    """
    
    def __init__(
        self, 
        url: str, 
        client: httpx.Client, 
        headers: Dict[str, str],
        store_password: Optional[str] = None,
        timeout: int = 30
    ):
        self.url = url
        self.client = client
        self.headers = headers
        self.timeout = timeout
        self.message_id = 1
        
        # Shopify uses base URL directly (no /message suffix)
        self.message_endpoint = url
        
        # Authenticate if needed
        self._authenticate(store_password)
    
    def _authenticate(self, password: Optional[str]) -> None:
        """Handle Shopify password protection"""
        from utils.shopify_mcp_handler import ShopifyMCPHandler
        
        handler = ShopifyMCPHandler(self.client, self.headers)
        handler.authenticate_store(self.url, password)
        
        # Test endpoint (base URL, not /message)
        logger.debug(f"Shopify SSE - Testing endpoint: {self.url}")
        test_request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1
        }
        
        response = self.client.post(
            self.url,  # Direct to base URL
            json=test_request,
            timeout=self.timeout,
            follow_redirects=True
        )
        
        if response.status_code != 200:
            raise ValueError(f"Shopify MCP endpoint test failed: {response.status_code}")
        
    
    def send_request(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        request = {
            "jsonrpc": "2.0",
            "id": self.message_id,
            "method": method,
            "params": params
        }
        self.message_id += 1
        
        logger.debug(f"Shopify SSE - Sending {method} to {self.message_endpoint}")
        
        response = self.client.post(
            self.message_endpoint,  # Uses base URL directly
            json=request,
            timeout=self.timeout,
            follow_redirects=True
        )
        
        # Check for password redirect
        if '/password' in str(response.url):
            raise ValueError(
                "Session expired - redirected to password page. "
                "Password cookie may have expired."
            )
        
        response.raise_for_status()
        
        if not response.text or response.text.strip() == "":
            raise ValueError(f"Empty response from Shopify MCP for {method}")
        
        result = response.json()
        if "error" in result:
            raise ValueError(f"Shopify MCP error: {result['error']}")
        
        return result
    
    def is_alive(self) -> bool:
        return self.client is not None
    
    def close(self) -> None:
        if self.client:
            self.client.close()


def create_sse_transport(
    url: str,
    headers: Dict[str, str],
    store_password: Optional[str] = None,
    timeout: int = 30
) -> MCPTransport:
    """
    Factory function to create appropriate SSE transport.
    
    Auto-detects Shopify stores and uses ShopifySSETransport.
    """
    # Create HTTP client
    cookies = httpx.Cookies()
    client = httpx.Client(
        timeout=timeout,
        headers=headers,
        follow_redirects=True,
        cookies=cookies,
        trust_env=False
    )
    
    # Detect Shopify
    if 'myshopify.com' in url.lower():
        logger.debug("MCP Transport - Detected Shopify store, using ShopifySSETransport")
        return ShopifySSETransport(url, client, headers, store_password, timeout)
    else:
        logger.debug("MCP Transport - Using GenericSSETransport")
        return GenericSSETransport(url, client, timeout)