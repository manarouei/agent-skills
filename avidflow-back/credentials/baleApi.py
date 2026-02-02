"""
Bale API credential for bot interactions.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class BaleApiCredential(BaseCredential):
    """Bale API credential implementation"""
    
    name = "baleApi"
    display_name = "Bale API"
    properties = [
        {
            "name": "accessToken",
            "displayName": "توکن بات بله",
            "type": "string",
            "required": True,
            "description": "توکن API که از BotFather بله دریافت کرده‌اید"
        },
        {
            "name": "apiUrl",
            "displayName": "آدرس API",
            "type": "string",
            "default": "https://tapi.bale.ai",
            "required": True,
            "description": "آدرس API بله"
        },
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Bale API credential by getting bot information
        
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
            # Get bot info to test credential
            api_url = self.data.get("apiUrl", "https://tapi.bale.ai").rstrip('/')
            bot_token = self.data["accessToken"]
            
            url = f"{api_url}/bot{bot_token}/getMe"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "message": f"Failed to connect to Bale API. Status: {response.status}"
                        }
                    
                    data = await response.json()
                    if data.get("ok"):
                        bot_name = data.get("result", {}).get("username", "Unknown")
                        return {
                            "success": True,
                            "message": f"Successfully connected to Bale API. Bot name: {bot_name}"
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"Bale API error: {data.get('description', 'Unknown error')}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing Bale API credential: {str(e)}"
            }