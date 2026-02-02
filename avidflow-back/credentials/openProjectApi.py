"""
OpenProject API credential for accessing OpenProject REST API with API Key through Basic Auth.
"""

import aiohttp
import base64
from typing import Dict, Any
from .base import BaseCredential


class OpenProjectApiCredential(BaseCredential):
    """OpenProject API credential implementation using API Key through Basic Auth"""
    
    name = "openProjectApi"
    display_name = "OpenProject API"
    properties = [
        {
            "name": "apiKey",
            "displayName": "API Key",
            "type": "password",
            "required": True,
            "description": "Your OpenProject API token (found in My Account > Access tokens)"
        },
        {
            "name": "baseUrl",
            "displayName": "Base URL",
            "type": "string",
            "required": True,
            "default": "https://community.openproject.org",
            "placeholder": "https://your-instance.openproject.com",
            "description": "The base URL of your OpenProject instance"
        },
    ]
    
    def get_auth_header(self) -> Dict[str, str]:
        """
        Correct Basic Auth:
        username = 'apikey'
        password = <apiKey>
        base64("apikey:API_KEY")
        """
        api_key = self.data.get("apiKey", "")
        
        auth_string = f"apikey:{api_key}"
        encoded = base64.b64encode(auth_string.encode()).decode()
        
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json"
        }
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the OpenProject API credential by fetching the /api/v3 endpoint
        """
        validation = self.validate()
        if not validation["valid"]:
            return {
                "success": False,
                "message": validation["message"]
            }
        
        try:
            base_url = self.data.get("baseUrl", "").rstrip('/')
            url = f"{base_url}/api/v3"
            headers = self.get_auth_header()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    
                    if response.status == 401:
                        return {
                            "success": False,
                            "message": "Authentication failed. Check your API key."
                        }
                    if response.status == 403:
                        return {
                            "success": False,
                            "message": "Forbidden. Your API key does not have permission."
                        }
                    if response.status != 200:
                        return {
                            "success": False,
                            "message": f"Connection failed. Status: {response.status}"
                        }
                    
                    data = await response.json()
                    instance_name = data.get("instanceName", "OpenProject")
                    
                    return {
                        "success": True,
                        "message": f"Successfully connected to {instance_name}"
                    }

        except aiohttp.ClientError as e:
            return {
                "success": False,
                "message": f"Connection error: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Unexpected error: {str(e)}"
            }
