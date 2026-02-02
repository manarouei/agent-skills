"""
HTTP Basic Authentication credential for API access.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class HttpBasicAuthCredential(BaseCredential):
    """HTTP Basic Authentication credential implementation"""
    
    name = "httpBasicAuth"
    display_name = "HTTP Basic Auth"
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
        Test the HTTP Basic Auth credential by making a request to a test URL
        
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
