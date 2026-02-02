"""
Kavenegar API credential for SMS services.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class KavenegarApiCredential(BaseCredential):
    """Kavenegar API credential implementation"""
    
    name = "kavenegarApi"
    display_name = "Kavenegar API"
    properties = [
        {
            "name": "apiKey",
            "displayName": "API Key",
            "type": "string",
            "required": True,
            "description": "The API key you received from your Kavenegar user panel"
        },
        {
            "name": "apiUrl",
            "displayName": "API URL",
            "type": "string",
            "default": "https://api.kavenegar.com",
            "required": True,
            "description": "Kavenegar API address"
        },
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Kavenegar API credential by getting account info
        
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
            # Get account info to test credential
            api_url = self.data.get("apiUrl", "https://api.kavenegar.com").rstrip('/')
            api_key = self.data["apiKey"]
            
            url = f"{api_url}/v1/{api_key}/account/info.json"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "message": f"Failed to connect to Kavenegar API. Status: {response.status}"
                        }
                    
                    data = await response.json()
                    if data.get("return", {}).get("status") == 200:
                        account_type = data.get("entries", {}).get("type", "Unknown")
                        remain_credit = data.get("entries", {}).get("remaincredit", 0)
                        return {
                            "success": True,
                            "message": f"Successfully connected to Kavenegar API. Account type: {account_type}, Remaining credit: {remain_credit} Rials"
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"Kavenegar API error: {data.get('return', {}).get('message', 'Unknown error')}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing Kavenegar API credential: {str(e)}"
            }
