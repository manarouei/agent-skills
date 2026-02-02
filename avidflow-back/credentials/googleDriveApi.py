"""
Google Drive API credential for accessing Google Drive services.
"""
from typing import Dict, Any, List, Optional, ClassVar
from .googleOAuth2Api import GoogleOAuth2ApiCredential


class GoogleDriveApiCredential(GoogleOAuth2ApiCredential):
    """Google Drive API credential implementation"""
    
    name = "googleDriveApi"
    display_name = "Google Drive API"
    
    @staticmethod
    def _build_properties() -> List[Dict[str, Any]]:
        """Build Google-specific properties based on parent"""
        parent_props = GoogleOAuth2ApiCredential.properties
        modified_props = []

        drive_scopes = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive.metadata',
            'https://www.googleapis.com/auth/drive.readonly',
        ]

        for prop in parent_props:
            prop_copy = prop.copy()
            
            if prop_copy["name"] == "scope":
                prop_copy["type"] = "hidden"
                prop_copy.update({
                    "type": "hidden",
                    "default": " ".join(drive_scopes)
                })
            
            modified_props.append(prop_copy)
        
        return modified_props
    
    icon = "fa:hdd"
    color = "#0F9D58"
    
    properties: ClassVar[List[Dict[str, Any]]] = _build_properties()

