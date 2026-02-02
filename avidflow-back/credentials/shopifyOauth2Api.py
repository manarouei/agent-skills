"""
Shopify OAuth2 API credential for accessing Shopify API with OAuth2 authentication.
"""
from typing import Dict, Any, List, ClassVar
from .oAuth2Api import OAuth2ApiCredential


class ShopifyOAuth2ApiCredential(OAuth2ApiCredential):
    """Shopify OAuth2 API credential implementation"""
    
    name = "shopifyOAuth2Api"
    display_name = "Shopify OAuth2 API"
    
    @staticmethod
    def _build_properties() -> List[Dict[str, Any]]:
        """Build Shopify-specific properties based on parent"""
        parent_props = OAuth2ApiCredential.properties
        hidden_fields = ["grantType", "authUrl", "accessTokenUrl", "scope", "authQueryParameters", "authentication"]
        
        # Extra fields that should appear at the top
        extra_fields = [
            {
                "displayName": "Shop Subdomain",
                "name": "shopSubdomain",
                "type": "string",
                "required": True,
                "default": "",
                "description": "Only the subdomain without .myshopify.com",
            },
        ]
        
        base_data = [{"grantType": "authorizationCode"},
                     {"authUrl": 'https://{{$self["shopSubdomain"]}}.myshopify.com/admin/oauth/authorize'},
                     {"accessTokenUrl": 'https://{{$self["shopSubdomain"]}}.myshopify.com/admin/oauth/access_token'},
                     {"scope": 'write_orders,read_orders,write_products,read_products'},
                     {"authQueryParameters": ""},
                     {"authentication": "body"}
                     ]
        
        # Start with extra fields so they appear first in the UI
        modified_props: List[Dict[str, Any]] = extra_fields.copy()

        # Then add parent props
        for prop in parent_props:
            prop_copy = prop.copy()
            
            if prop_copy["name"] in hidden_fields:
                prop_copy["type"] = "hidden"
            
            modified_props.append(prop_copy)

        # Update with base data defaults
        [current.update({"default": value}) for current in modified_props for d in base_data for key, value in d.items() if current["name"] == key]

        return modified_props
    
    icon = "shopify.svg"
    color = "#95bf47"
    
    properties: ClassVar[List[Dict[str, Any]]] = _build_properties()
