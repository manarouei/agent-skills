"""
Supabase API credential for database and backend services.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class SupabaseApiCredential(BaseCredential):
    """Supabase API credential implementation"""
    
    name = "supabaseApi"
    display_name = "Supabase API"
    properties = [
        {
            "name": "host",
            "displayName": "Host",
            "type": "string",
            "required": True,
            "description": "The host URL of your Supabase project (e.g., https://your-project.supabase.co)"
        },
        {
            "name": "serviceKey",
            "displayName": "Service Key",
            "type": "password",
            "required": True,
            "description": "The service key for your Supabase project"
        }
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Supabase API credential by checking API access
        
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
            # Get connection info to test credential
            host = self.data.get("host", "").rstrip("/")
            service_key = self.data["serviceKey"]
            
            # Test connection by checking if we can access the API
            headers = {
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
                "Content-Type": "application/json"
            }
            
            url = f"{host}/rest/v1/"
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "Successfully connected to Supabase API"
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "message": f"Supabase API error: {error_text}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing Supabase API credential: {str(e)}"
            }