"""
Google Calendar API credential for accessing Google Calendar services.
"""
from typing import Dict, Any, List, ClassVar
from .googleOAuth2Api import GoogleOAuth2ApiCredential


class GoogleCalendarApiCredential(GoogleOAuth2ApiCredential):
    """Google Calendar API credential implementation"""
    
    name = "googleCalendarApi"
    display_name = "Google Calendar API"

    @staticmethod
    def _build_properties() -> List[Dict[str, Any]]:
        """Build Google-specific properties based on parent"""
        parent_props = GoogleOAuth2ApiCredential.properties
        modified_props = []

        calendar_scopes = [
            'https://www.googleapis.com/auth/calendar',
	        'https://www.googleapis.com/auth/calendar.events',
        ]

        for prop in parent_props:
            prop_copy = prop.copy()
            
            if prop_copy["name"] == "scope":
                prop_copy["type"] = "hidden"
                prop_copy.update({
                    "type": "hidden",
                    "default": " ".join(calendar_scopes)
                })
            
            modified_props.append(prop_copy)
        
        return modified_props
    
    icon = "fa:calendar"
    color = "#4285F4"

    properties: ClassVar[List[Dict[str, Any]]] = _build_properties()
