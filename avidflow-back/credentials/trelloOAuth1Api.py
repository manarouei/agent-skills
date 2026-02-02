"""
Trello API credential for Trello API authentication
Following n8n's simpler API Key + Token approach
"""
import aiohttp
from typing import Dict, Any, List, ClassVar
from .base import BaseCredential


class TrelloOAuth1ApiCredential(BaseCredential):
    """
    Trello API credential implementation
    Trello uses a simple API Key + Token authentication (not full OAuth1 flow)
    This matches n8n's TrelloApi credential approach
    """
    
    name = "trelloOAuth1Api"
    display_name = "Trello API"
    documentationUrl = "trello"
    
    properties = [
        {
            "name": "apiKey",
            "displayName": "API Key",
            "type": "password",
            "default": "",
            "required": True,
            "description": "Your Trello API key. Get it from https://trello.com/app-key"
        },
        {
            "name": "apiToken",
            "displayName": "API Token",
            "type": "password",
            "default": "",
            "required": True,
            "description": "Your Trello API token. Generate it at https://trello.com/app-key"
        },
        {
            "name": "oauthSecret",
            "displayName": "OAuth Secret",
            "type": "hidden",
            "default": "",
            "description": "OAuth secret for advanced authentication"
        },
    ]
    
    icon = "fa:trello"
    color = "#0079bf"
    
    def authenticate(self, request_options: Dict[str, Any]) -> Dict[str, Any]:
        """
        Authenticate request by adding API key and token to query parameters
        This matches n8n's authenticate method
        
        Args:
            request_options: Request options dictionary
            
        Returns:
            Modified request options with authentication
        """
        # Get existing query params or create new dict
        qs = request_options.get("qs", {})
        
        # Add API key and token
        qs["key"] = self.data.get("apiKey", "")
        qs["token"] = self.data.get("apiToken", "")
        
        request_options["qs"] = qs
        return request_options
    
    async def test(self) -> Dict[str, Any]:
        """
        Test Trello API credential by validating the token
        This matches n8n's test request
        
        Returns:
            Dictionary with test results
        """
        try:
            # Validate required fields
            api_key = self.data.get("apiKey", "")
            api_token = self.data.get("apiToken", "")
            
            if not api_key or not api_token:
                return {
                    "success": False,
                    "message": "API Key and API Token are required"
                }
            
            # Test by getting token member info (like n8n does)
            url = f"https://api.trello.com/1/tokens/{api_token}/member"
            params = {
                "key": api_key,
                "token": api_token
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params, timeout=10) as response:
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "Trello credentials validated successfully"
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "message": f"Invalid Trello credentials: {error_text}"
                        }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error validating Trello credential: {str(e)}"
            }
