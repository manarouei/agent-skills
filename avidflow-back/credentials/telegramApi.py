"""
Telegram API credential for bot interactions.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class TelegramApiCredential(BaseCredential):
    """Telegram API credential implementation"""
    
    name = "telegramApi"
    display_name = "Telegram API"
    properties = [
        {
            "name": "accessToken",
            "displayName": "توکن بات تلگرام",
            "type": "string",
            "required": True,
            "description": "توکن API که از BotFather دریافت کرده‌اید"
        },
        {
            "name": "apiUrl",
            "displayName": "آدرس API",
            "type": "string",
            "default": "https://api.telegram.org",
            "required": True,
            "description": "آدرس API تلگرام"
        },
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Telegram API credential by getting bot information
        
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
            api_url = self.data.get("apiUrl", "https://api.telegram.org").rstrip('/')
            bot_token = self.data["accessToken"]
            
            url = f"{api_url}/bot{bot_token}/getMe"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "message": f"Failed to connect to Telegram API. Status: {response.status}"
                        }
                    
                    data = await response.json()
                    if data.get("ok"):
                        bot_name = data.get("result", {}).get("username", "Unknown")
                        return {
                            "success": True,
                            "message": f"Successfully connected to Telegram API. Bot name: {bot_name}"
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"Telegram API error: {data.get('description', 'Unknown error')}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing Telegram API credential: {str(e)}"
            }
