"""
DeepSeek API credential for accessing DeepSeek AI services.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class DeepSeekApiCredential(BaseCredential):
    """DeepSeek API credential implementation"""
    
    name = "deepseekApi"
    display_name = "DeepSeek API"
    properties = [
        {
            "name": "apiKey",
            "displayName": "API Key",
            "type": "password",
            "required": True,
            "description": "Your DeepSeek API key (get it at platform.deepseek.com)"
        }
    ]
    
    def get_api_key(self) -> str:
        """
        Get the API key
        
        Returns:
            API key string
        """
        # Handle both direct access and nested 'data' structure
        if isinstance(self.data, dict):
            return self.data.get("apiKey", "")
        elif hasattr(self, "data") and isinstance(self.data, dict):
            return self.data.get("apiKey", "")
        return ""
    
    def get_base_url(self) -> str:
        """
        Get the base URL for API requests
        
        Returns:
            Base URL string (fixed for DeepSeek)
        """
        return "https://api.deepseek.com/v1"
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get the headers for API requests
        
        Returns:
            Dictionary of headers
        """
        api_key = self.get_api_key()
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the DeepSeek API credential by making a simple request
        
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
            # Get headers and base URL
            headers = self.get_headers()
            base_url = self.get_base_url()
            
            async with aiohttp.ClientSession() as session:
                # Test by listing models
                url = f"{base_url}/models"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        models = [model['id'] for model in data.get('data', [])]
                        return {
                            "success": True,
                            "message": f"Authentication successful. Available models: {', '.join(models)}"
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "message": f"API error {response.status}: {error_text}"
                        }
                        
        except aiohttp.ClientConnectorError:
            return {
                "success": False,
                "message": "Connection error: Could not reach DeepSeek API"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing credential: {str(e)}"
            }