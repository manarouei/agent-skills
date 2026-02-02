"""
Gmail OAuth2 API credential - following n8n pattern
"""
from typing import Dict, Any, List, ClassVar
from .googleOAuth2Api import GoogleOAuth2ApiCredential

class GmailOAuth2ApiCredential(GoogleOAuth2ApiCredential):
    """Gmail OAuth2 credential that extends Google OAuth2"""
    
    name = "gmailOAuth2"
    display_name = "Gmail OAuth2 API"
    
    # Gmail-specific scopes (matching n8n)
    GMAIL_SCOPES = [
        'https://www.googleapis.com/auth/gmail.labels',
        'https://www.googleapis.com/auth/gmail.addons.current.action.compose',
        'https://www.googleapis.com/auth/gmail.addons.current.message.action',
        'https://mail.google.com/',
        'https://www.googleapis.com/auth/gmail.modify',
        'https://www.googleapis.com/auth/gmail.compose',
    ]

    @staticmethod
    def _build_properties() -> List[Dict[str, Any]]:
        """Build Google-specific properties based on parent"""
        parent_props = GoogleOAuth2ApiCredential.properties
        modified_props = []

        gmail_scopes = [
            'https://www.googleapis.com/auth/gmail.labels',
            'https://www.googleapis.com/auth/gmail.addons.current.action.compose',
            'https://www.googleapis.com/auth/gmail.addons.current.message.action',
            'https://mail.google.com/',
            'https://www.googleapis.com/auth/gmail.modify',
            'https://www.googleapis.com/auth/gmail.compose',
        ]

        for prop in parent_props:
            prop_copy = prop.copy()
            
            if prop_copy["name"] == "scope":
                prop_copy["type"] = "hidden"
                prop_copy.update({
                    "type": "hidden",
                    "default": " ".join(gmail_scopes)
                })
            
            modified_props.append(prop_copy)
        
        return modified_props

    properties: ClassVar[List[Dict[str, Any]]] = _build_properties()
