"""
HTTP Header Authentication credential for API access.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class HttpHeaderAuthCredential(BaseCredential):
    """HTTP Header Authentication credential implementation"""
    
    name = "httpHeaderAuth"
    display_name = "HTTP Header Auth"
    properties = [
        {
            "name": "name",
            "displayName": "نام هدر",
            "type": "string",
            "default": "Authorization",
            "required": True,
        },
        {
            "name": "value",
            "displayName": "مقدار هدر",
            "type": "string",
            "required": True,
        },
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the HTTP Header Auth credential by making a request to a test URL
        
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
            # Default test URL - could be configurable in the future
            test_url = self.data.get("testUrl", "https://httpbin.org/headers")
            
            async with aiohttp.ClientSession() as session:
                headers = {self.data["name"]: self.data["value"]}
                
                async with session.get(test_url, headers=headers) as response:
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "Authentication successful"
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"Authentication failed with status code: {response.status}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing credential: {str(e)}"
            }
