"""
OAuth1 API credential for generic OAuth 1.0a authentication.
"""
import hmac
import hashlib
import base64
import urllib.parse
import time
import random
import string
import aiohttp
from typing import Dict, Any, Optional
from .base import BaseCredential


class OAuth1ApiCredential(BaseCredential):
    """OAuth1 API credential implementation for OAuth 1.0a authentication"""
    
    name = "oAuth1Api"
    display_name = "OAuth1 API"
    documentationUrl = "httpRequest"
    
    # Generic auth flag indicates this credential can be used by multiple nodes
    generic_auth = True
    
    properties = [
        {
            "name": "authUrl",
            "displayName": "Authorization URL",
            "type": "string",
            "default": "",
            "required": True
        },
        {
            "name": "accessTokenUrl",
            "displayName": "Access Token URL",
            "type": "string",
            "default": "",
            "required": True
        },
        {
            "name": "consumerKey",
            "displayName": "Consumer Key",
            "type": "password",
            "default": "",
            "required": True
        },
        {
            "name": "consumerSecret",
            "displayName": "Consumer Secret",
            "type": "password",
            "default": "",
            "required": True
        },
        {
            "name": "requestTokenUrl",
            "displayName": "Request Token URL",
            "type": "string",
            "default": "",
            "required": True
        },
        {
            "name": "signatureMethod",
            "displayName": "Signature Method",
            "type": "options",
            "default": "HMAC-SHA1",
            "required": True,
            "options": [
                {"name": "HMAC-SHA1", "value": "HMAC-SHA1"},
                {"name": "HMAC-SHA256", "value": "HMAC-SHA256"},
                {"name": "HMAC-SHA512", "value": "HMAC-SHA512"}
            ]
        },
    ]
    
    icon = "fa:key"
    color = "#666666"
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the OAuth1 API credential by validating required fields
        
        Since OAuth1 endpoints vary widely, we just validate the required fields exist.
        A real test would require setting up the entire OAuth flow.
        """
        try:
            # Validate required fields first
            validation = self.validate()
            if not validation["valid"]:
                return {
                    "success": False,
                    "message": validation["message"]
                }
            
            # Make sure we have essential OAuth1 fields
            required_fields = ["consumerKey", "consumerSecret", "requestTokenUrl", "accessTokenUrl", "authUrl"]
            missing_fields = [field for field in required_fields if not self.data.get(field)]
            
            if missing_fields:
                return {
                    "success": False,
                    "message": f"Missing required OAuth1 fields: {', '.join(missing_fields)}"
                }
            
            return {
                "success": True,
                "message": "OAuth1 credential validated successfully"
            }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error validating OAuth1 credential: {str(e)}"
            }
    
    def generate_oauth_signature(self, method: str, url: str, params: Dict[str, str]) -> str:
        """
        Generate OAuth 1.0a signature
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            params: Request parameters including OAuth params
            
        Returns:
            Generated signature
        """
        # Create signature base string
        # 1. Convert parameters to query string format and encode
        sorted_params = sorted(params.items())
        param_string = '&'.join([f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(str(v), safe='')}" for k, v in sorted_params])
        
        # 2. Create signature base string
        base_string = f"{method}&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(param_string, safe='')}"
        
        # 3. Create signing key
        consumer_secret = self.data.get("consumerSecret", "")
        token_secret = self.data.get("accessTokenSecret", "")
        signing_key = f"{urllib.parse.quote(consumer_secret, safe='')}&{urllib.parse.quote(token_secret, safe='')}"
        
        # 4. Generate signature based on selected method
        signature_method = self.data.get("signatureMethod", "HMAC-SHA1")
        
        if signature_method == "HMAC-SHA1":
            hash_func = hashlib.sha1
        elif signature_method == "HMAC-SHA256":
            hash_func = hashlib.sha256
        elif signature_method == "HMAC-SHA512":
            hash_func = hashlib.sha512
        else:
            hash_func = hashlib.sha1  # Default to SHA1
        
        signature = base64.b64encode(
            hmac.new(
                signing_key.encode(),
                base_string.encode(), 
                hash_func
            ).digest()
        ).decode()
        
        return signature
    
    def get_oauth_parameters(self) -> Dict[str, str]:
        """
        Get basic OAuth 1.0a parameters
        
        Returns:
            Dictionary of OAuth parameters
        """
        # Generate nonce - random string
        nonce = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(32))
        
        oauth_params = {
            'oauth_consumer_key': self.data.get("consumerKey", ""),
            'oauth_nonce': nonce,
            'oauth_signature_method': f"HMAC-{self.data.get('signatureMethod', 'SHA1')}",
            'oauth_timestamp': str(int(time.time())),
            'oauth_version': '1.0'
        }
        
        # Add access token if available
        if self.data.get("accessToken"):
            oauth_params['oauth_token'] = self.data.get("accessToken")
            
        return oauth_params
    
    def get_authorization_header(self, method: str, url: str, params: Dict[str, str] = None) -> Dict[str, str]:
        """
        Create Authorization header for OAuth 1.0a request
        
        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            params: Additional request parameters
            
        Returns:
            Dictionary containing Authorization header
        """
        if params is None:
            params = {}
            
        # Get OAuth parameters
        oauth_params = self.get_oauth_parameters()
        
        # Combine with other parameters
        all_params = {**params, **oauth_params}
        
        # Generate signature
        signature = self.generate_oauth_signature(method, url, all_params)
        
        # Add signature to params
        oauth_params['oauth_signature'] = signature
        
        # Create Authorization header
        auth_header = 'OAuth ' + ', '.join([
            f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(str(v), safe="")}"'
            for k, v in sorted(oauth_params.items())
        ])
        
        return {'Authorization': auth_header}
