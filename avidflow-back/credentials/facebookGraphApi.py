"""
Facebook Graph API credential for accessing Facebook's Graph API.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class FacebookGraphApiCredential(BaseCredential):
    """Facebook Graph API credential implementation that matches n8n's original implementation"""
    
    name = "facebookGraphApi"
    display_name = "Facebook Graph API"
    properties = [
        {
            "name": "accessToken",
            "displayName": "کلید دسترسی",
            "type": "password",
            "required": True,
            "default": ""
        }
    ]
    
    icon = "fa:facebook"
    color = "#3b5998"
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Facebook Graph API credential by making a test request
        """
        # Validate required fields first
        validation = self.validate()
        if not validation["valid"]:
            return {
                "success": False,
                "message": validation["message"]
            }
        
        try:
            # Get access token from data
            access_token = self.data.get("accessToken")
            
            # Make API request to test the access token using v8.0 as per n8n's implementation
            async with aiohttp.ClientSession() as session:
                url = f"https://graph.facebook.com/v8.0/me?access_token={access_token}"
                
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            "success": True,
                            "message": f"Successfully connected as {data.get('name', data.get('id', 'unknown'))}"
                        }
                    else:
                        error_data = await response.json()
                        return {
                            "success": False,
                            "message": f"Authentication failed: {error_data.get('error', {}).get('message', 'Unknown error')}"
                        }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error connecting to Facebook Graph API: {str(e)}"
            }
