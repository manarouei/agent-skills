"""
Grok API credential for accessing xAI's Grok services.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class GrokApiCredential(BaseCredential):
    """Grok API credential implementation"""
    
    name = "grokApi"
    display_name = "Grok API"
    properties = [
        {
            "name": "apiKey",
            "displayName": "API Key",
            "type": "string",
            "required": True,
            "description": "Your Grok API key"
        },
        {
            "name": "baseUrl",
            "displayName": "Base URL",
            "type": "string",
            "default": "https://api.grok.ai/v1",
            "required": False,
            "description": "The base URL for the Grok API"
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
            if "apiKey" in self.data:
                return self.data.get("apiKey", "")
            elif "data" in self.data and isinstance(self.data["data"], dict):
                return self.data["data"].get("apiKey", "")
        return ""
    
    def get_base_url(self) -> str:
        """
        Get the base URL for API requests
        
        Returns:
            Base URL string
        """
        # Handle both direct access and nested 'data' structure
        default_url = "https://api.grok.ai/v1"
        if isinstance(self.data, dict):
            if "baseUrl" in self.data:
                return self.data.get("baseUrl", default_url).rstrip('/')
            elif "data" in self.data and isinstance(self.data["data"], dict):
                return self.data["data"].get("baseUrl", default_url).rstrip('/')
        return default_url
    
    def get_headers(self) -> Dict[str, str]:
        """
        Get the headers for API requests
        
        Returns:
            Dictionary of headers
        """
        api_key = self.get_api_key()
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Grok API credential by making a simple request
        
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
                        model_count = len(data.get("data", []))
                        return {
                            "success": True,
                            "message": f"Successfully connected to Grok API. Found {model_count} available models."
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "message": f"Grok API error: {error_text}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing Grok API credential: {str(e)}"
            }