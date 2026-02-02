"""
OpenAI API credential for accessing AI services.
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class OpenAiApiCredential(BaseCredential):
    """OpenAI API credential implementation"""
    
    name = "openAiApi"
    display_name = "OpenAI API"
    properties = [
        {
            "name": "apiKey",
            "displayName": "کلید API",
            "type": "string",
            "required": True,
            "description": "کلید API اختصاصی OpenAI"
        },
        {
            "name": "organizationId",
            "displayName": "شناسه سازمانی",
            "type": "string",
            "required": False,
            "description": "شناسه سازمانی برای حساب‌های سازمانی (اختیاری)"
        },
        {
            "name": "baseUrl",
            "displayName": "آدرس پایه API",
            "type": "string",
            "default": "https://api.openai.com/v1",
            "required": False,
            "description": "آدرس پایه API در صورت استفاده از نسخه اختصاصی"
        },
        {
            "name": "timeout",
            "displayName": "زمان انتظار",
            "type": "number",
            "default": 60,
            "required": False,
            "description": "مدت زمان انتظار برای پاسخ (به ثانیه)"
        }
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the OpenAI API credential by listing models
        
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
            # Use OpenAI Models API to test credential
            base_url = self.data.get("baseUrl", "https://api.openai.com/v1").rstrip('/')
            api_key = self.data["apiKey"]
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # Add organization header if provided
            if self.data.get("organizationId"):
                headers["OpenAI-Organization"] = self.data["organizationId"]
            
            # Set timeout
            timeout = aiohttp.ClientTimeout(total=float(self.data.get("timeout", 60)))
            
            async with aiohttp.ClientSession(timeout=timeout) as session:
                url = f"{base_url}/models"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        model_count = len(data.get("data", []))
                        return {
                            "success": True,
                            "message": f"Successfully connected to OpenAI API. Found {model_count} available models."
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "message": f"OpenAI API error: {error_text}"
                        }
                        
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing OpenAI API credential: {str(e)}"
            }
