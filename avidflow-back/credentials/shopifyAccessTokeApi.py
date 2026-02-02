import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class ShopifyAccessTokenApiCredential(BaseCredential):
    name = "shopifyAccessTokenApi"
    display_name = "Shopify Access Token API"

    properties = [
        {
            "displayName": "Shop Subdomain",
            "name": "shopSubdomain",
            "type": "string",
            "required": True,
            "default": "",
            "description": "Only the subdomain without .myshopify.com",
        },
        {
            "displayName": "Access Token",
            "name": "accessToken",
            "type": "string",
            "required": True,
            "typeOptions": {"password": True},
            "default": "",
        },
        {
            "displayName": "APP Secret Key",
            "name": "appSecretKey",
            "type": "string",
            "required": True,
            "typeOptions": {"password": True},
            "default": "",
            "description": (
                "Secret key needed to verify Shopify webhooks when using trigger nodes"
            ),
        },
    ]

    def authenticate(self) -> Dict[str, Any]:
        """
        Generate authenticate headers dynamically based on credential data.
        Equivalent to n8n's `authenticate` object.
        """
        return {
            "type": "generic",
            "properties": {
                "headers": {
                    "X-Shopify-Access-Token": self.data.get("accessToken", "")
                }
            }
        }

    async def test(self) -> Dict[str, Any]:
        validation = self.validate()
        if not validation["valid"]:
            return {"success": False, "message": validation["message"]}

        try:
            shop_subdomain = self.data["shopSubdomain"]
            access_token = self.data["accessToken"]

            base_url = f"https://{shop_subdomain}.myshopify.com/admin/api/2024-07"
            test_url = f"{base_url}/products.json"

            headers = {"X-Shopify-Access-Token": access_token}

            async with aiohttp.ClientSession() as session:
                async with session.get(test_url, headers=headers) as response:
                    if response.status == 200:
                        return {"success": True, "message": "Shopify Access Token is valid."}
                    elif response.status == 401:
                        return {"success": False, "message": "Invalid Access Token."}
                    else:
                        return {"success": False, "message": f"Shopify API returned {response.status}."}

        except Exception as e:
            return {"success": False, "message": f"Error testing Shopify Access Token: {str(e)}"}