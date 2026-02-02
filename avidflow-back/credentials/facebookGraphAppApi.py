"""
Facebook Graph App API credential for accessing Facebook's Graph API with App authentication.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class FacebookGraphAppApiCredential(BaseCredential):
    """Facebook Graph App API credential implementation - flattened structure"""
    
    name = "facebookGraphAppApi"
    display_name = "Facebook Graph API (App)"
    
    # Include all properties directly instead of inheriting
    properties = [
        # Properties from FacebookGraphApi
        {
            "name": "accessToken",
            "displayName": "کلید دسترسی",
            "type": "password",
            "required": True,
            "default": ""
        },
        # Additional properties for FacebookGraphAppApi
        {
            "name": "appSecret",
            "displayName": "کلید امنیتی اپلیکیشن",
            "type": "password",
            "default": "",
            "required": False,
            "description": "(اختیاری) وقتی کلید امنیتی تنظیم شده باشد، نود می‌تواند امضا را برای تأیید یکپارچگی و منبع داده‌ها بررسی کند"
        }
    ]
    
    icon = "fa:facebook-square"
    color = "#3b5998"
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Facebook Graph App API credential
        """
        try:
            # Validate required fields first
            validation = self.validate()
            if not validation["valid"]:
                return {
                    "success": False,
                    "message": validation["message"]
                }
            
            # Get access token from data
            access_token = self.data.get("accessToken")
            
            if not access_token:
                return {
                    "success": False,
                    "message": "توکن دسترسی موجود نیست"
                }
                
            # First test if the access token is valid
            async with aiohttp.ClientSession() as session:
                url = f"https://graph.facebook.com/v8.0/me?access_token={access_token}"
                
                async with session.get(url) as response:
                    if response.status != 200:
                        error_data = await response.json()
                        return {
                            "success": False,
                            "message": f"Authentication failed: {error_data.get('error', {}).get('message', 'Unknown error')}"
                        }
                    
                    data = await response.json()
                    base_result = {
                        "success": True,
                        "message": f"Successfully connected as {data.get('name', data.get('id', 'unknown'))}"
                    }
            
            # If we have an app secret, we need to verify we can generate an app token
            app_secret = self.data.get("appSecret")
            if not app_secret:
                # If no app secret, the base test is sufficient
                return base_result
                
            # Extract app ID from the access token or use it directly if provided
            app_id = None
            if access_token and '|' in access_token:
                app_id = access_token.split('|')[0]
                
            if app_id:
                return {
                    "success": True,
                    "message": f"اعتبارسنجی موفقیت‌آمیز. متصل به اپلیکیشن با شناسه {app_id}"
                }
            else:
                return {
                    "success": True,
                    "message": "اعتبارسنجی توکن موفقیت‌آمیز بود. کلید امنیتی اپلیکیشن در دسترس است."
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"خطا در بررسی کلید امنیتی اپلیکیشن: {str(e)}"
            }
