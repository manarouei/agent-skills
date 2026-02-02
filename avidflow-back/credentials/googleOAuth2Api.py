from typing import Dict, Any, List, ClassVar
from .oAuth2Api import OAuth2ApiCredential

class GoogleOAuth2ApiCredential(OAuth2ApiCredential):
    name = "googleOAuth2Api"
    display_name = "Google OAuth2 API"

    @staticmethod
    def _build_properties() -> List[Dict[str, Any]]:
        """Build Google-specific properties based on parent"""
        parent_props = OAuth2ApiCredential.properties
        hidden_fields = ["authUrl", "accessTokenUrl", "authQueryParameters", "authentication", "grantType"]
        modified_props: List[Dict[str, Any]] = []
        base_data = [{"authUrl": "https://accounts.google.com/o/oauth2/v2/auth"},
                     {"accessTokenUrl": "https://oauth2.googleapis.com/token"},
                     {"authQueryParameters": "access_type=offline&prompt=consent"},
                     {"authentication": "body"},
                     {"grantType": "authorizationCode"}
                     ]

        for prop in parent_props:
            prop_copy = prop.copy()
            
            if prop_copy["name"] in hidden_fields:
                prop_copy["type"] = "hidden"
            
            modified_props.append(prop_copy)

        [current.update({"default": value}) for current in modified_props for d in base_data for key, value in d.items() if current["name"] == key]

        return modified_props

    properties: ClassVar[List[Dict[str, Any]]] = _build_properties()
    # Override default properties with Google-specific values
