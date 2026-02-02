"""
Google Sheets API credential for accessing Google Sheets services.
"""
from typing import Dict, Any, List, ClassVar
from .googleOAuth2Api import GoogleOAuth2ApiCredential


class GoogleSheetsApiCredential(GoogleOAuth2ApiCredential):
    """Google Sheets API credential implementation"""
    
    name = "googleSheetsApi"
    display_name = "Google Sheets API"
    
    @staticmethod
    def _build_properties() -> List[Dict[str, Any]]:
        """Build Google-specific properties based on parent"""
        parent_props = GoogleOAuth2ApiCredential.properties
        modified_props = []

        sheets_scopes = [
            'https://www.googleapis.com/auth/drive.file',
	        'https://www.googleapis.com/auth/spreadsheets',
	        'https://www.googleapis.com/auth/drive.metadata',
        ]

        for prop in parent_props:
            prop_copy = prop.copy()
            
            if prop_copy["name"] == "scope":
                prop_copy["type"] = "hidden"
                prop_copy.update({
                    "type": "hidden",
                    "default": " ".join(sheets_scopes)
                })
            
            modified_props.append(prop_copy)
        
        return modified_props
    
    properties: ClassVar[List[Dict[str, Any]]] = _build_properties()
    
    icon = "fa:table"
    color = "#0F9D58"
