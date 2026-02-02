"""
Shopify MCP Handler

Handles Shopify-specific authentication and MCP protocol implementation
for password-protected dev stores.
"""

import logging
from typing import Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)


class ShopifyMCPHandler:
    """
    Handler for Shopify MCP server connections with password protection support
    """
    
    def __init__(self, client: httpx.Client, headers: Dict[str, str]):
        """
        Initialize Shopify MCP handler
        
        Args:
            client: httpx.Client instance with cookie jar
            headers: Authentication headers
        """
        self.client = client
        self.headers = headers
        self._authenticated = False
    
    def authenticate_store(self, url: str, password: Optional[str] = None) -> bool:
        """
        Authenticate with Shopify password-protected store
        
        Args:
            url: MCP endpoint URL
            password: Store password (if protected)
            
        Returns:
            True if authentication successful or not needed
            
        Raises:
            ValueError: If authentication fails
        """
        try:
            # Extract base URL from MCP endpoint
            base_url = url.rsplit('/api/', 1)[0] if '/api/' in url else url.rsplit('/', 1)[0]
            
            logger.debug(f"Shopify MCP - Testing store access: {base_url}")
            
            # Try to access the store root
            test_response = self.client.get(base_url, follow_redirects=True)
            
            # Check if we landed on the password page
            is_password_page = (
                '/password' in str(test_response.url) or 
                'password' in test_response.text.lower()[:500]
            )
            
            if is_password_page:
                logger.debug("Shopify MCP - Store password protection detected")
                
                if not password:
                    raise ValueError(
                        "Store has password protection but no password provided. "
                        "Add 'storePassword' to options or disable password protection in Shopify admin."
                    )
                

                password_response = self.client.post(
                    f"{base_url}/password",
                    data={
                        "password": password,
                        "form_type": "storefront_password"
                    },
                    headers={
                        **self.headers,
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    follow_redirects=True
                )
                
                # Check if authentication succeeded
                if password_response.status_code == 200:
                    # Verify we're not still on the password page
                    if '/password' not in str(password_response.url):
                        logger.debug("Shopify MCP - Successfully authenticated with store password")
                        logger.debug(f"Shopify MCP - Cookies: {list(self.client.cookies.jar)}")
                        self._authenticated = True
                        return True
                    else:
                        raise ValueError(
                            "Failed to authenticate with store password. "
                            "Password may be incorrect."
                        )
                else:
                    raise ValueError(
                        f"Failed to authenticate with store password: HTTP {password_response.status_code}"
                    )
            else:
                logger.debug("Shopify MCP - No password protection detected")
                self._authenticated = True
                return True
                
        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Shopify MCP - Authentication error: {e}", exc_info=True)
            raise ValueError(f"Store authentication failed: {str(e)}")
    
    def test_mcp_endpoint(self, url: str) -> bool:
        """
        Test MCP endpoint accessibility using POST with tools/list
        
        Args:
            url: MCP endpoint URL
            
        Returns:
            True if endpoint is accessible
            
        Raises:
            ValueError: If endpoint is not accessible
        """
        try:
            logger.debug(f"Shopify MCP - Testing MCP endpoint: {url}")
            
            # MCP endpoints expect POST with JSON-RPC payload
            test_request = {
                "jsonrpc": "2.0",
                "method": "tools/list",
                "id": 1
            }
            
            response = self.client.post(
                url,
                json=test_request,
                follow_redirects=True,
                timeout=10.0
            )
            
            # Log response details
            logger.debug(f"Shopify MCP - Test response URL: {response.url}")
            logger.debug(f"Shopify MCP - Test response status: {response.status_code}")
            logger.debug(f"Shopify MCP - Test response preview: {response.text[:200]}")
            
            # Check if we got redirected back to password page
            if '/password' in str(response.url):
                raise ValueError(
                    "MCP endpoint redirected to password page. "
                    "Store password may be incorrect or cookies expired."
                )
            
            # Check status code
            if response.status_code == 404:
                raise ValueError(
                    f"MCP endpoint not found at {url}. "
                    "Please verify the endpoint URL is correct. "
                    "Shopify MCP endpoints typically use POST, not GET."
                )
            elif response.status_code == 401:
                raise ValueError(
                    "MCP endpoint authentication failed (401 Unauthorized). "
                    "Please check your access token."
                )
            elif response.status_code == 403:
                raise ValueError(
                    "MCP endpoint access forbidden (403 Forbidden). "
                    "Please check your API permissions."
                )
            
            response.raise_for_status()
            
            # Try to parse JSON response
            try:
                result = response.json()
                
                # Check for JSON-RPC error
                if "error" in result:
                    logger.warning(f"Shopify MCP - JSON-RPC error: {result['error']}")
                    # This is actually OK - it means the endpoint exists and responds
                    return True
                
                # Check for successful tools/list response
                if "result" in result:
                    logger.debug("Shopify MCP - Endpoint test successful")
                    return True
                
                logger.warning(f"Shopify MCP - Unexpected response format: {result}")
                return True  # Endpoint responds, even if format is unexpected
                
            except Exception as json_err:
                logger.error(f"Shopify MCP - Invalid JSON response: {response.text}")
                raise ValueError(
                    f"MCP endpoint returned invalid JSON: {str(json_err)}. "
                    f"Response: {response.text[:200]}"
                )
            
        except ValueError:
            raise
        except httpx.HTTPStatusError as e:
            raise ValueError(
                f"HTTP error testing MCP endpoint: "
                f"{e.response.status_code} {e.response.reason_phrase}"
            )
        except httpx.RequestError as e:
            raise ValueError(f"Network error testing MCP endpoint: {str(e)}")
        except Exception as e:
            logger.error(f"Shopify MCP - Endpoint test error: {e}", exc_info=True)
            raise ValueError(f"Failed to test MCP endpoint: {str(e)}")