"""
Hesabfa Token API credential for accounting system integration using login token.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class HesabfaTokenApiCredential(BaseCredential):
    """Hesabfa Token API credential implementation"""
    
    name = "hesabfaTokenApi"
    display_name = "Hesabfa - API Token"
    properties = [
        {
            "name": "apiKey",
            "displayName": "API Key",
            "type": "string",
            "required": True,
            "description": "API key received from Settings/Financial Settings/API in Hesabfa"
        },
        {
            "name": "loginToken",
            "displayName": "Login Token",
            "type": "string",
            "required": True,
            "description": "Login token for your business received from Settings/Financial Settings/API in Hesabfa"
        },
        {
            "name": "yearId",
            "displayName": "Fiscal Year ID",
            "type": "number",
            "default": None,
            "required": False,
            "description": "Fiscal year ID (if empty, the latest fiscal year will be used)"
        },
        {
            "name": "apiUrl",
            "displayName": "API URL",
            "type": "string",
            "default": "https://api.hesabfa.com/v1",
            "required": True,
            "description": "Base URL of Hesabfa API"
        },
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Hesabfa Token API credential by calling a simple endpoint
        
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
            # Test credential by getting fiscal years list
            api_url = self.data.get("apiUrl", "https://api.hesabfa.com/v1").rstrip('/')
            api_key = self.data["apiKey"]
            login_token = self.data["loginToken"]
            
            url = f"{api_url}/setting/getfiscalyears"
            
            # Build request body for token-based authentication
            request_data = {
                "apiKey": api_key,
                "loginToken": login_token
            }
            
            if self.data.get("yearId"):
                request_data["yearId"] = self.data.get("yearId")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=request_data) as response:
                    if response.status != 200:
                        return {
                            "success": False,
                            "message": f"Failed to connect to Hesabfa API. Status: {response.status}"
                        }
                    
                    data = await response.json()
                    if data.get("Success"):
                        years_count = len(data.get("Result", []))
                        return {
                            "success": True,
                            "message": f"Successfully connected to Hesabfa API. Found {years_count} fiscal years."
                        }
                    else:
                        error_message = data.get("ErrorMessage", "Unknown error")
                        error_code = data.get("ErrorCode", "N/A")
                        return {
                            "success": False,
                            "message": f"Hesabfa API error (Code: {error_code}): {error_message}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing Hesabfa Token API credential: {str(e)}"
            }