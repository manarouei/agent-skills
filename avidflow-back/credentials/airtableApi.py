"""
Airtable API credential for database and table operations.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class AirtableApiCredential(BaseCredential):
    """Airtable API credential implementation"""
    
    name = "airtableApi"
    display_name = "Airtable API"
    properties = [
        {
            "name": "apiKey",
            "displayName": "API Key",
            "type": "password",
            "required": True,
            "description": "Your Airtable API key (pat_*****)"
        }
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Airtable API credential by checking API access
        
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
            # Test connection by making a simple request to get bases
            api_key = self.data["apiKey"]
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Use meta API to list bases (requires minimal permissions)
            url = "https://api.airtable.com/v0/meta/bases"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "Successfully connected to Airtable API"
                        }
                    elif response.status == 401:
                        return {
                            "success": False,
                            "message": "Invalid API key - authentication failed"
                        }
                    elif response.status == 403:
                        return {
                            "success": False,
                            "message": "API key lacks necessary permissions"
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "message": f"Airtable API error: {error_text}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing Airtable API credential: {str(e)}"
            }