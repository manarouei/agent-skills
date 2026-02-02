"""
WooCommerce API credential for accessing WooCommerce stores.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class WooCommerceApiCredential(BaseCredential):
    """WooCommerce API credential implementation"""
    
    name = "wooCommerceApi"
    display_name = "WooCommerce API"
    properties = [
        {
            "name": "consumerKey",
            "displayName": "Consumer Key",
            "type": "password",
            "required": True,
            "description": "Your WooCommerce Consumer Key"
        },
        {
            "name": "consumerSecret",
            "displayName": "Consumer Secret",
            "type": "password",
            "required": True,
            "description": "Your WooCommerce Consumer Secret"
        },
        {
            "name": "url",
            "displayName": "WooCommerce URL",
            "type": "string",
            "required": True,
            "description": "The URL of your WooCommerce store",
            "placeholder": "https://example.com"
        },
        {
            "name": "includeCredentialsInQuery",
            "displayName": "Include Credentials in Query",
            "type": "boolean",
            "default": False,
            "required": False,
            "description": "Whether credentials should be included in the query. Occasionally, some servers may not parse the Authorization header correctly (if you see a \"Consumer key is missing\" error when authenticating over SSL, you have a server issue). In this case, you may provide the consumer key/secret as query string parameters instead."
        }
    ]
    
    def get_consumer_key(self) -> str:
        """
        Get the Consumer Key
        
        Returns:
            Consumer Key string
        """
        return self.data.get("consumerKey", "")
    
    def get_consumer_secret(self) -> str:
        """
        Get the Consumer Secret
        
        Returns:
            Consumer Secret string
        """
        return self.data.get("consumerSecret", "")
    
    def get_base_url(self) -> str:
        """
        Get the base URL for WooCommerce API requests
        
        Returns:
            Base URL string
        """
        url = self.data.get("url", "").rstrip('/')
        return f"{url}/wp-json/wc/v3"
    
    def get_auth(self) -> Dict[str, str]:
        """
        Get the auth credentials for WooCommerce API requests
        
        Returns:
            Auth dictionary (username/password)
        """
        return {
            "username": self.get_consumer_key(),
            "password": self.get_consumer_secret()
        }
    
    def should_include_in_query(self) -> bool:
        """
        Check if credentials should be included in query parameters
        
        Returns:
            Boolean indicating whether to include creds in query
        """
        return self.data.get("includeCredentialsInQuery", False)
    
    def get_query_params(self) -> Dict[str, str]:
        """
        Get credentials as query parameters if needed
        
        Returns:
            Query parameters dictionary or empty dict
        """
        if self.should_include_in_query():
            return {
                "consumer_key": self.get_consumer_key(),
                "consumer_secret": self.get_consumer_secret()
            }
        return {}
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the WooCommerce API credential by making a simple request
        
        Returns:
            Dictionary with test results
        """
        # Validate required fields first
        validation = self.validate()
        if not validation["valid"]:
            return {
                "success": False,
                "message": validation["message"]
            }
        
        try:
            # Get base URL and auth info
            base_url = self.get_base_url()
            auth = self.get_auth()
            query_params = self.get_query_params()
            
            async with aiohttp.ClientSession() as session:
                # Test by listing product categories - simple endpoint that should work on all WooCommerce stores
                url = f"{base_url}/products/categories"
                
                # Use basic auth or query params based on settings
                if self.should_include_in_query():
                    async with session.get(url, params=query_params) as response:
                        return await self._process_response(response)
                else:
                    async with session.get(url, auth=aiohttp.BasicAuth(auth["username"], auth["password"])) as response:
                        return await self._process_response(response)
                        
        except aiohttp.ClientConnectorError:
            return {
                "success": False,
                "message": "Connection error: Could not reach WooCommerce API"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing credential: {str(e)}"
            }
    
    async def _process_response(self, response):
        """Helper to process API response"""
        if response.status == 200:
            data = await response.json()
            categories_count = len(data)
            return {
                "success": True,
                "message": f"Authentication successful. Found {categories_count} product categories."
            }
        else:
            error_text = await response.text()
            try:
                error_json = await response.json()
                error_message = error_json.get('message', error_text)
            except:
                error_message = error_text
                
            return {
                "success": False,
                "message": f"API error {response.status}: {error_message}"
            }
