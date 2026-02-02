"""
Google Forms API credential implementation.
"""
from typing import Dict, Any, List, ClassVar
from .googleOAuth2Api import GoogleOAuth2ApiCredential

class GoogleFormApiCredential(GoogleOAuth2ApiCredential):
    """Google Forms API credential that extends Google OAuth2"""
    
    name = "googleFormApi"
    display_name = "Google Form API"
    documentationUrl = "googleForms"
    
    # Google Forms-specific scopes
    _scopes = [
        "https://www.googleapis.com/auth/forms.body",
        "https://www.googleapis.com/auth/forms.responses.readonly",
        "https://www.googleapis.com/auth/drive.file"
    ]
    
    @staticmethod
    def _build_properties() -> List[Dict[str, Any]]:
        """Build Google Forms-specific properties based on parent"""
        parent_props = GoogleOAuth2ApiCredential.properties
        modified_props = []
        
        # Set the default scopes for Google Forms API
        form_scopes = [
            "https://www.googleapis.com/auth/forms.body",
            "https://www.googleapis.com/auth/forms.responses.readonly",
            "https://www.googleapis.com/auth/drive.file"
        ]
        
        # Process each property from parent
        for prop in parent_props:
            prop_copy = prop.copy()
            
            # Override scope property with Forms-specific scopes
            if prop_copy["name"] == "scope":
                prop_copy.update({
                    "type": "hidden",
                    "default": " ".join(form_scopes)
                })
            
            modified_props.append(prop_copy)
        
        return modified_props
    
    properties: ClassVar[List[Dict[str, Any]]] = _build_properties()