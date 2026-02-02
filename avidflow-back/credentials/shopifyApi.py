import aiohttp
from typing import Dict, Any
from .base import BaseCredential
import base64

class ShopifyApiCredential(BaseCredential):
    name = "shopifyApi"
    display_name = "Shopify API"

    properties = [
        {
            "displayName": "API Key",
            "name": "apiKey",
            "type": "string",
            "required": True,
            "typeOptions": {"password": True},
            "default": ""
        },
        {
            "displayName": "Password",
            "name": "password",
            "type": "string",
            "required": True,
            "typeOptions": {"password": True},
            "default": ""
        },
        {
            "displayName": "Shop Subdomain",
            "name": "shopSubdomain",
            "type": "string",
            "required": True,
            "default": "",
            "description": "Only the subdomain without .myshopify.com"
        },
        {
            "displayName": "Shared Secret",
            "name": "sharedSecret",
            "type": "string",
            "typeOptions": {"password": True},
            "default": ""
        },
    ]

    def authenticate(self) -> Dict[str, Any]:
        """
        Build the Basic Auth headers dynamically
        """
        api_key = self.data.get("apiKey", "")
        password = self.data.get("password", "")
        credentials = f"{api_key}:{password}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        return {
            "type": "generic",
            "properties": {
                "headers": {
                    "Authorization": f"Basic {encoded_credentials}"
                }
            }
        }

    async def test(self) -> Dict[str, Any]:
        """
        Test Shopify API credential using Basic Auth
        """
        validation = self.validate()
        if not validation["valid"]:
            return {
                "success": False,
                "message": validation["message"]
            }

        try:
            shop_subdomain = self.data["shopSubdomain"]
            api_key = self.data["apiKey"]
            password = self.data["password"]

            base_url = f"https://{shop_subdomain}.myshopify.com/admin/api/2024-07"
            test_url = f"{base_url}/products.json"

            credentials = f"{api_key}:{password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()

            headers = {
                "Authorization": f"Basic {encoded_credentials}"
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url=test_url,
                    headers=headers
                ) as response:
                    if response.status == 200:
                        return {
                            "success": True,
                            "message": "Shopify API credentials are valid."
                        }
                    elif response.status == 401:
                        return {
                            "success": False,
                            "message": "Invalid API Key or Password."
                        }
                    else:
                        return {
                            "success": False,
                            "message": f"Shopify API returned status {response.status}."
                        }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing Shopify API credentials: {str(e)}"
            }
