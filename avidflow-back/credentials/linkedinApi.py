"""
LinkedIn API credential for accessing LinkedIn services.
"""

from typing import Dict, Any, List, ClassVar
from .oAuth2Api import OAuth2ApiCredential


class LinkedInApiCredential(OAuth2ApiCredential):
    """LinkedIn API credential implementation using standard OAuth2 flow"""

    name = "linkedinApi"
    display_name = "LinkedIn API"

    # LinkedIn scopes that are actually authorized for your application
    _scopes = ["openid", "profile", "email", "w_member_social"]

    @staticmethod
    def _build_properties() -> List[Dict[str, Any]]:
        """Build LinkedIn-specific properties based on parent"""
        parent_props = OAuth2ApiCredential.properties
        hidden_fields = [
            "authUrl",
            "accessTokenUrl",
            "authQueryParameters",
            "authentication",
            "grantType",
        ]
        base_data = [
            {"authUrl": "https://www.linkedin.com/oauth/v2/authorization"},
            {"accessTokenUrl": "https://www.linkedin.com/oauth/v2/accessToken"},
            {"authQueryParameters": ""},
            {"authentication": "body"},
            {"grantType": "authorizationCode"},
        ]

        _scopes = ["w_member_social", "openid", "profile", "email"]

        modified_props: List[Dict[str, Any]] = []
        for prop in parent_props:
            prop_copy = prop.copy()

            if prop_copy["name"] in hidden_fields:
                prop_copy["type"] = "hidden"

            if prop_copy["name"] == "scope":
                prop_copy["type"] = "hidden"
                prop_copy.update({"type": "hidden", "default": " ".join(_scopes)})

            modified_props.append(prop_copy)

        [current.update({"default": value}) for current in modified_props for d in base_data for key, value in d.items() if current["name"] == key]
        
        return modified_props

    properties: ClassVar[List[Dict[str, Any]]] = _build_properties()
