"""
Google Docs API credential for accessing Google Docs services.
"""
from typing import Dict, Any, Optional, List, ClassVar
from .googleOAuth2Api import GoogleOAuth2ApiCredential


class GoogleDocsApiCredential(GoogleOAuth2ApiCredential):
    """Google Docs API credential implementation"""
    
    name = "googleDocsApi"
    display_name = "Google Docs API"

    @staticmethod
    def _build_properties() -> List[Dict[str, Any]]:
        """Build Google-specific properties based on parent"""
        parent_props = GoogleOAuth2ApiCredential.properties
        modified_props = []

        docs_scopes = [
            'https://www.googleapis.com/auth/documents',
	        'https://www.googleapis.com/auth/drive',
	        'https://www.googleapis.com/auth/drive.file',
        ]

        for prop in parent_props:
            prop_copy = prop.copy()
            
            if prop_copy["name"] == "scope":
                prop_copy["type"] = "hidden"
                prop_copy.update({
                    "type": "hidden",
                    "default": " ".join(docs_scopes)
                })
            
            modified_props.append(prop_copy)
        
        return modified_props
    
    properties: ClassVar[List[Dict[str, Any]]] = _build_properties()
    
    icon = "fa:file-text"
    color = "#4285F4"
    