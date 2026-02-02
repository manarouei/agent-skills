"""
Wallex API credential for cryptocurrency exchange operations.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class WallexApiCredential(BaseCredential):
    """Wallex API credential implementation"""
    
    name = "wallexApi"
    display_name = "Wallex API"
    properties = [
        {
            "name": "apiKey",
            "displayName": "API Key",
            "type": "string",
            "required": True,
            "description": "The API key obtained from the API management section of the Wallex website"
        },
        {
            "name": "apiUrl",
            "displayName": "API URL",
            "type": "string",
            "default": "https://api.wallex.ir",
            "required": True,
            "description": "The Wallex API URL"
        },
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Wallex API credential by getting account profile
        
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
            # Get account profile to test credential
            api_url = self.data.get("apiUrl", "https://api.wallex.ir").rstrip('/')
            api_key = self.data["apiKey"]
            
            async with aiohttp.ClientSession() as session:
                headers = {
                    "X-API-Key": api_key,
                    "Content-Type": "application/json"
                }
                
                async with session.get(f"{api_url}/v1/account/profile", headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get("success"):
                            return {
                                "success": True,
                                "message": "احراز هویت موفق"
                            }
                        else:
                            return {
                                "success": False,
                                "message": f"خطا: {data.get('message', 'Unknown error')}"
                            }
                    elif response.status == 401:
                        return {
                            "success": False,
                            "message": "کلید API نامعتبر است"
                        }
                    elif response.status == 403:
                        return {
                            "success": False,
                            "message": "دسترسی غیر مجاز - لطفاً مجوزهای کلید API را بررسی کنید"
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"خطا با کد وضعیت: {response.status}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "message": f"خطا در تست اعتبارنامه: {str(e)}"
            }
