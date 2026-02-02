"""
Neshan API credential for accessing Neshan map services.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class NeshanApiCredential(BaseCredential):
    """Neshan API credential implementation"""
    
    name = "neshanApi"
    display_name = "Neshan API"
    properties = [
        {
            "name": "apiKey",
            "displayName": "API Key",
            "type": "string",
            "required": True,
            "description": "The API key you received from the Neshan developer panel"
        },
        {
            "name": "apiUrl",
            "displayName": "API URL",
            "type": "string",
            "default": "https://api.neshan.org",
            "required": True,
            "description": "The base URL for the Neshan API"
        },
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Neshan API credential by making a simple reverse geocoding request
        
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
            # Test with a simple reverse geocoding request (Tehran coordinates)
            api_url = self.data.get("apiUrl", "https://api.neshan.org").rstrip('/')
            api_key = self.data["apiKey"]
            
            # Using reverse geocoding to test the API key
            url = f"{api_url}/v5/reverse?lat=35.7&lng=51.4"
            headers = {
                "Api-Key": api_key
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "OK":
                            return {
                                "success": True,
                                "message": "Successfully connected to Neshan API"
                            }
                        else:
                            return {
                                "success": False,
                                "message": f"Neshan API returned non-OK status: {data.get('status', 'Unknown')}"
                            }
                    elif response.status == 480:
                        return {
                            "success": False,
                            "message": "Invalid API Key. Please check your credentials."
                        }
                    elif response.status == 481:
                        return {
                            "success": False,
                            "message": "API limit exceeded. Your quota has been exhausted."
                        }
                    elif response.status == 482:
                        return {
                            "success": False,
                            "message": "Rate limit exceeded. Too many requests per minute."
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"Failed to connect to Neshan API. Status: {response.status}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing Neshan API credential: {str(e)}"
            }
