"""
Twitter OAuth2 API credential for accessing Twitter/X API with OAuth2 authentication.
"""
from typing import Dict, Any, List, ClassVar
import aiohttp
import base64
import time
from urllib.parse import urlencode
from .oAuth2Api import OAuth2ApiCredential


class TwitterOAuth2ApiCredential(OAuth2ApiCredential):
    """Twitter OAuth2 API credential implementation"""
    
    name = "twitterOAuth2Api"
    display_name = "X OAuth2 API"
    
    _scopes = [
        'tweet.read',
        'users.read',
        'tweet.write',
        'tweet.moderate.write',
        'users.read',
        'follows.read',
        'follows.write',
        'offline.access',
        'like.read',
        'like.write',
        'dm.write',
        'dm.read',
        'list.read',
        'list.write',
    ]
    
    @staticmethod
    def _build_properties() -> List[Dict[str, Any]]:
        """Build Google-specific properties based on parent"""
        parent_props = OAuth2ApiCredential.properties
        hidden_fields = ["authUrl", "accessTokenUrl", "authQueryParameters", "authentication", "grantType"]
        base_data = [{"authUrl": "https://twitter.com/i/oauth2/authorize"},
                     {"accessTokenUrl": "https://api.twitter.com/2/oauth2/token"},
                     {"authQueryParameters": ""},
                     {"authentication": "header"},
                     {"grantType": "pkce"}
                     ]
    
        _scopes = [
            'tweet.read',
            'users.read',
            'tweet.write',
            'tweet.moderate.write',
            'users.read',
            'follows.read',
            'follows.write',
            'offline.access',
            'like.read',
            'like.write',
            'dm.write',
            'dm.read',
            'list.read',
            'list.write',
        ]

        modified_props: List[Dict[str, Any]] = []
        for prop in parent_props:
            prop_copy = prop.copy()
            
            if prop_copy["name"] in hidden_fields:
                prop_copy["type"] = "hidden"

            if prop_copy["name"] == "scope":
                prop_copy["type"] = "hidden"
                prop_copy.update({
                    "type": "hidden",
                    "default": " ".join(_scopes)
                })
            
            modified_props.append(prop_copy)
        
        [current.update({"default": value}) for current in modified_props for d in base_data for key, value in d.items() if current["name"] == key]
        
        return modified_props
    
    icon = "fa:twitter"
    color = "#1DA1F2"
    
    properties: ClassVar[List[Dict[str, Any]]] = _build_properties()
