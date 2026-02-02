"""
Facebook Lead Ads OAuth2 API credential for accessing Facebook Lead Ads data.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class FacebookLeadAdsOAuth2ApiCredential(BaseCredential):
    """Facebook Lead Ads OAuth2 API credential implementation - flattened structure"""
    
    name = "facebookLeadAdsOAuth2Api"
    display_name = "Facebook Lead Ads OAuth2 API"
    
    # Include all properties directly without inheritance
    properties = [
        # Hidden OAuth2 configuration properties
        {
            "name": "grantType",
            "displayName": "Grant Type",
            "type": "hidden",
            "default": "authorizationCode",
        },
        {
            "name": "authUrl",
            "displayName": "Authorization URL",
            "type": "hidden",
            "default": "https://www.facebook.com/v17.0/dialog/oauth",
            "required": True,
        },
        {
            "name": "accessTokenUrl",
            "displayName": "Access Token URL",
            "type": "hidden",
            "default": "https://graph.facebook.com/v17.0/oauth/access_token",
            "required": True,
        },
        {
            "name": "scope",
            "displayName": "Scope",
            "type": "hidden",
            "default": "leads_retrieval pages_show_list pages_manage_metadata pages_manage_ads business_management",
        },
        {
            "name": "authQueryParameters",
            "displayName": "Auth URI Query Parameters",
            "type": "hidden",
            "default": "",
        },
        {
            "name": "authentication",
            "displayName": "Authentication",
            "type": "hidden",
            "default": "header",
        },
        # Standard OAuth2 properties 
        {
            "name": "clientId",
            "displayName": "Client ID",
            "type": "string",
            "required": True,
        },
        {
            "name": "clientSecret",
            "displayName": "Client Secret",
            "type": "password",
            "required": True,
        },
    ]
    
    icon = "fa:facebook"
    color = "#3b5998"
    documentationUrl = 'facebookleadads'
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Facebook Lead Ads OAuth2 API credential by making a test request
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
            
            # Test with Facebook Graph API to get Pages
            async with aiohttp.ClientSession() as session:
                # First check if token is valid
                url = f"https://graph.facebook.com/v17.0/me?access_token={access_token}"
                
                async with session.get(url) as response:
                    if response.status != 200:
                        error_data = await response.json()
                        return {
                            "success": False,
                            "message": f"خطا در اعتبارسنجی توکن: {error_data.get('error', {}).get('message', 'خطای نامشخص')}"
                        }
                    
                    user_data = await response.json()
                    
                    # Now test if we can access lead ads-related features
                    pages_url = f"https://graph.facebook.com/v17.0/me/accounts?fields=name,access_token&access_token={access_token}"
                    
                    async with session.get(pages_url) as pages_response:
                        if pages_response.status == 200:
                            pages_data = await pages_response.json()
                            pages_count = len(pages_data.get("data", []))
                            return {
                                "success": True,
                                "message": f"اعتبارسنجی موفق. متصل به حساب {user_data.get('name', '')} با دسترسی به {pages_count} صفحه"
                            }
                        else:
                            error_data = await pages_response.json()
                            return {
                                "success": False,
                                "message": f"توکن معتبر است اما دسترسی به صفحات ممکن نیست: {error_data.get('error', {}).get('message', 'خطای نامشخص')}"
                            }
        
        except Exception as e:
            return {
                "success": False,
                "message": f"خطا در اتصال به Facebook Lead Ads API: {str(e)}"
            }
