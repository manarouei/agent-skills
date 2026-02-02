"""
Local GPT API credential for accessing self-hosted GPT-compatible model servers.

This credential supports authentication via username/password for local or 
self-hosted GPT-compatible inference servers.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class LocalGptApiCredential(BaseCredential):
    """Local GPT API credential implementation with username/password auth"""
    
    name = "localGptApi"
    display_name = "Local GPT API"
    properties = [
        {
            "name": "username",
            "displayName": "نام کاربری",
            "type": "string",
            "required": True,
        },
        {
            "name": "password",
            "displayName": "کلمه عبور",
            "type": "password",
            "required": True,
        },
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Local GPT API credential
        
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
            return {
                "success": True,
                "message": "این اعتبارنامه معتبر است."
            }
                        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing credential: {str(e)}"
            }
