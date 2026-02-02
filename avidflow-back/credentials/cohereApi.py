"""
Cohere API credential for accessing reranking and embedding services.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class CohereApiCredential(BaseCredential):
    """Cohere API credential implementation"""
    
    name = "cohereApi"
    display_name = "Cohere API"
    properties = [
        {
            "name": "apiKey",
            "displayName": "کلید API",
            "type": "string",
            "required": True,
            "description": "کلید API اختصاصی Cohere (از https://dashboard.cohere.com/api-keys)"
        },
        {
            "name": "baseUrl",
            "displayName": "آدرس پایه API",
            "type": "string",
            "default": "https://api.cohere.ai/v1",
            "required": False,
            "description": "آدرس پایه API در صورت استفاده از نسخه اختصاصی"
        },
        {
            "name": "timeout",
            "displayName": "زمان انتظار",
            "type": "number",
            "default": 30,
            "required": False,
            "description": "مدت زمان انتظار برای پاسخ (به ثانیه)"
        }
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Cohere API credential by checking models endpoint
        
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
            # Use Cohere Models API to test credential
            base_url = self.data.get("baseUrl", "https://api.cohere.ai/v1").rstrip('/')
            api_key = self.data["apiKey"]
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Set timeout
            timeout = aiohttp.ClientTimeout(total=float(self.data.get("timeout", 30)))
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                # Use check-api-key endpoint for validation
                url = f"{base_url}/check-api-key"
                async with session.post(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        is_valid = data.get("valid", False)
                        if is_valid:
                            return {
                                "success": True,
                                "message": "Successfully connected to Cohere API. API key is valid."
                            }
                        else:
                            return {
                                "success": False,
                                "message": "Cohere API key is invalid."
                            }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "message": f"Cohere API error (status {response.status}): {error_text}"
                        }
                        
        except aiohttp.ClientConnectorError as e:
            return {
                "success": False,
                "message": f"Cannot connect to Cohere API: {str(e)}"
            }
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "message": f"Network error while testing Cohere API: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing Cohere API credential: {str(e)}"
            }
