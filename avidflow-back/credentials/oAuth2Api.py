"""
OAuth2 API credential for service authentication.
Stateless design - returns refreshed tokens without automatic persistence.
"""
import aiohttp
import asyncio
import time
import logging
import json
from typing import Dict, Any, Optional, Tuple
from urllib.parse import urlencode, parse_qs
import base64
import hashlib
from config import settings

from .base import BaseCredential
import re

logger = logging.getLogger(__name__)

# Lightweight constants
TOKEN_EXPIRY_BUFFER = 60  # seconds before expiry to trigger refresh


class TokenRefreshError(Exception):
    """Lightweight exception for token refresh failures"""
    
    def __init__(self, message: str, needs_reauth: bool = False, error_code: str = None):
        super().__init__(message)
        self.needs_reauth = needs_reauth
        self.error_code = error_code  # e.g., "invalid_grant", "network_error"


class OAuth2ApiCredential(BaseCredential):
    """OAuth2 API credential implementation"""
    
    name = "oAuth2Api"
    display_name = "OAuth2 API"
    
    @staticmethod
    def resolve_credential_expression(expression: str, credential_data: Dict[str, Any]) -> str:
        """
        Resolve expressions like {{$self["shopSubdomain"]}} to actual values from credential_data
        """
        if not expression or not isinstance(expression, str):
            return expression
        
        # Check if expression starts with = (n8n convention)
        if expression.startswith('='):
            expression = expression[1:]  # Remove the = prefix
        
        # Find all {{$self["fieldName"]}} patterns
        pattern = r'\{\{\$self\["([^"]+)"\]\}\}'
        
        def replacer(match):
            field_name = match.group(1)
            value = credential_data.get(field_name, '')
            return str(value) if value else ''
        
        resolved = re.sub(pattern, replacer, expression)
        return resolved
    
    properties = [
        {
            "name": "clientId",
            "displayName": "Client ID",
            "type": "string",
            "required": True,
        },
        {
            "name": "clientSecret",
            "displayName": "Client Secret",
            "type": "password",
            "required": True,
        },
        {
            "name": "authUrl",
            "displayName": "Authorization URL",
            "type": "string",
            "required": True,
        },
        {
            "name": "accessTokenUrl",
            "displayName": "Access Token URL",
            "type": "string",
            "required": True,
        },
        {
            "name": "scope",
            "displayName": "Scope",
            "type": "string",
            "required": False,
        },
        {
            "name": "grantType",
            "displayName": "Grant Type",
            "type": "options",
            "options": [
                {"name": "Authorization Code", "value": "authorizationCode"},
                {"name": "Client Credentials", "value": "clientCredentials"},
                {"name": "PKCE", "value": "pkce"}
            ],
            "default": "authorizationCode",
            "required": True,
        },
        {
            "name": "authentication",
            "displayName": "Authentication",
            "type": "options",
            "options": [
                {"name": "Header", "value": "header"},
                {"name": "Body", "value": "body"}
            ],
            "default": "header",
            "required": True,
        },
        {
            "name": "authQueryParameters",
            "displayName": "Auth Query Parameters",
            "type": "string",
            "required": False,
            "placeholder": "access_type=offline&prompt=consent"
        },
        {
            "name": "redirectUrl",
            "displayName": "Redirect URL",
            "type": "string",
            "required": False,
            "default": settings.OAUTH2_CALLBACK_URL
        },
        # OAuth token data (stored after successful auth)
        {
            "name": "oauthTokenData",
            "displayName": "OAuth Token Data",
            "type": "json",
            "required": False,
        },
    ]
    
    
    @staticmethod
    def has_access_token(credentials_data: Dict[str, Any]) -> bool:
        """Check if credentials have access token (n8n's approach)"""
        oauth_token_data = credentials_data.get('oauthTokenData')
        if not isinstance(oauth_token_data, dict):
            return False
        return 'access_token' in oauth_token_data
    
    async def test(self) -> Dict[str, Any]:
        """Test OAuth2 credential following n8n's exact approach"""
        # First check: Do we have OAuth token data?
        if not self.has_access_token(self.data):
            return {
                "success": False,
                "message": "OAuth credentials not connected. Please connect your account first.",
                "needsOAuth": True
            }
        
        # We have token data, now test it
        oauth_data = self.data["oauthTokenData"]
        
        # Check if token is expired and try to refresh
        if await self._is_token_expired(oauth_data):
            refresh_result = await self._try_refresh_token()
            if not refresh_result["success"]:
                return refresh_result
            # Update oauth_data with refreshed tokens
            oauth_data = self.data["oauthTokenData"]
        
        # Test the token by making a request
        return await self._test_token_request(oauth_data)
        
    async def _is_token_expired(self, oauth_data: Dict[str, Any]) -> bool:
        """Check if the current token is expired with clock skew tolerance"""
        if "expires_at" not in oauth_data:
            if "access_token" not in oauth_data:
                return True
            # No expiry info but has token - assume valid
            return False
        
        return time.time() > (oauth_data["expires_at"] - TOKEN_EXPIRY_BUFFER)
    
    @staticmethod
    def _parse_oauth_error(error_data: Dict[str, Any], status_code: int) -> TokenRefreshError:
        """Parse OAuth error response into typed exception (stateless, no side effects)"""
        error = error_data.get("error", "")
        desc = error_data.get("error_description", "")
        
        # Errors requiring re-authentication
        if error in ("invalid_grant", "unauthorized_client", "access_denied", "invalid_client"):
            return TokenRefreshError(
                desc or f"OAuth error: {error}",
                needs_reauth=True,
                error_code=error
            )
        
        # Transient/server errors
        return TokenRefreshError(
            desc or f"OAuth error ({status_code}): {error}",
            needs_reauth=False,
            error_code=error
        )
    
    async def _test_token_request(self, oauth_data: Dict[str, Any]) -> Dict[str, Any]:
        """Test the OAuth token by making a real request"""
        test_urls = [
            f"{self.data.get('authUrl', '').rstrip('/')}/userinfo",
            f"{self.data.get('authUrl', '').replace('/authorize', '/userinfo')}",
            f"{self.data.get('authUrl', '').replace('/oauth/authorize', '/api/user')}",
        ]
        
        headers = {
            "Authorization": f"Bearer {oauth_data['access_token']}",
            "Accept": "application/json"
        }
        
        async with aiohttp.ClientSession() as session:
            for test_url in test_urls:
                if not test_url or not test_url.startswith('http'):
                    continue
                    
                try:
                    async with session.get(test_url, headers=headers) as response:
                        if response.status == 200:
                            return {
                                "success": True,
                                "message": "OAuth2 credentials are connected and valid"
                            }
                        elif response.status == 401:
                            return {
                                "success": False,
                                "message": "OAuth2 token is invalid or expired. Please reconnect."
                            }
                except Exception:
                    continue
        
        return {
            "success": True,
            "message": "OAuth2 credentials appear to be connected (test endpoint not available)"
        }
    
    async def refresh_token(self) -> Dict[str, Any]:
        """
        Refresh OAuth2 access token - STATELESS version.
        
        Returns new token data WITHOUT modifying self.data.
        Caller is responsible for persisting if needed.
        
        Returns:
            Dict with new token data (access_token, refresh_token, expires_at, etc.)
            
        Raises:
            TokenRefreshError: On failure with needs_reauth flag
        """
        oauth_data = self.data.get("oauthTokenData", {})
        refresh_token = oauth_data.get("refresh_token")
        
        if not refresh_token:
            raise TokenRefreshError("No refresh token available", needs_reauth=True, error_code="no_refresh_token")
        
        access_token_url = self.resolve_credential_expression(
            self.data.get("accessTokenUrl", ""),
            self.data
        )
        
        # Build request
        body = {"grant_type": "refresh_token", "refresh_token": refresh_token}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        if self.data.get("authentication", "header") == "header":
            auth = base64.b64encode(f"{self.data['clientId']}:{self.data['clientSecret']}".encode()).decode()
            headers["Authorization"] = f"Basic {auth}"
        else:
            body["client_id"] = self.data["clientId"]
            body["client_secret"] = self.data["clientSecret"]
        
        timeout = aiohttp.ClientTimeout(total=15)
        
        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(access_token_url, data=urlencode(body), headers=headers) as resp:
                    text = await resp.text()
                    
                    if resp.status == 200:
                        data = json.loads(text)
                        
                        # Build updated token data (merge with existing)
                        result = oauth_data.copy()
                        result["access_token"] = data["access_token"]
                        result["expires_at"] = time.time() + data.get("expires_in", 3600)
                        
                        # Handle refresh token rotation
                        if "refresh_token" in data:
                            result["refresh_token"] = data["refresh_token"]
                        
                        # Copy other fields (scope, token_type, etc.)
                        for k, v in data.items():
                            if k not in ("access_token", "expires_in", "refresh_token"):
                                result[k] = v
                        
                        return result
                    else:
                        try:
                            err = json.loads(text)
                        except:
                            err = {"error": text[:200]}
                        
                        raise self._parse_oauth_error(err, resp.status)
                        
        except aiohttp.ClientError as e:
            raise TokenRefreshError(f"Network error: {e}", needs_reauth=False, error_code="network_error")
        except asyncio.TimeoutError:
            raise TokenRefreshError("Request timed out", needs_reauth=False, error_code="timeout")
    
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token (n8n compatible)"""
        access_token_url = self.resolve_credential_expression(
            self.data.get("accessTokenUrl", ""),
            self.data
        )
        
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        }
        
        if self.data.get("grantType") == "pkce" and self.data.get("codeVerifier"):
            token_data["code_verifier"] = self.data["codeVerifier"]
        
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        if self.data.get("authentication", "header") == "header":
            auth = base64.b64encode(f"{self.data['clientId']}:{self.data['clientSecret']}".encode()).decode()
            headers["Authorization"] = f"Basic {auth}"
        else:
            token_data["client_id"] = self.data["clientId"]
            token_data["client_secret"] = self.data["clientSecret"]
        
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        async with aiohttp.ClientSession() as session:
            async with session.post(
                access_token_url,
                data=urlencode(token_data),
                headers=headers
            ) as response:
                if response.status == 200:
                    oauth_data = await response.json()
                    
                    # Calculate expiration time
                    if "expires_in" in oauth_data:
                        oauth_data["expires_at"] = time.time() + oauth_data["expires_in"]
                    
                    # Don't store in self.data here - let the caller handle merging
                    return oauth_data
                else:
                    error_data = {}
                    try:
                        error_data = await response.json()
                    except:
                        error_data = {"error": await response.text()}
                    
                    error_msg = error_data.get('error_description', error_data.get('error', 'Unknown error'))
                    raise Exception(f"Token exchange failed: {error_msg}")

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate OAuth2 authorization URL (n8n compatible)"""
        # Resolve authUrl expression (e.g., {{$self["shopSubdomain"]}})
        auth_url = self.resolve_credential_expression(
            self.data.get("authUrl", ""),
            self.data
        )
        
        params = {
            "response_type": "code",
            "client_id": self.data["clientId"],
            "redirect_uri": redirect_uri,
            "state": state,
        }
        
        if self.data.get("scope"):
            # Handle both comma and space separated scopes like n8n
            scope = self.data["scope"]
            if "," in scope:
                params["scope"] = scope  # Keep comma-separated
            else:
                params["scope"] = scope  # Keep space-separated
        
        # Add custom auth query parameters (like n8n does)
        if self.data.get("authQueryParameters"):
            try:
                auth_params = parse_qs(self.data["authQueryParameters"])
                for key, values in auth_params.items():
                    if values:
                        params[key] = values[0]
            except Exception:
                pass
        
        # Handle PKCE (like n8n does)
        if self.data.get("grantType") == "pkce" and self.data.get("codeVerifier"):
            code_challenge = base64.urlsafe_b64encode(
                hashlib.sha256(self.data["codeVerifier"].encode()).digest()
            ).decode().rstrip('=')
            
            params.update({
                "code_challenge": code_challenge,
                "code_challenge_method": "S256"
            })
        
        return f"{auth_url}?{urlencode(params)}"
    
    async def get_access_token(self) -> str:
        """Get current access token, refreshing if necessary"""
        if not self.has_access_token(self.data):
            raise ValueError("No OAuth token data available")
        
        oauth_data = self.data["oauthTokenData"]
        
        if not oauth_data.get("access_token"):
            raise TokenRefreshError("No access token available", needs_reauth=True)
        
        # Token still valid
        if not await self._is_token_expired(oauth_data):
            return oauth_data["access_token"], None
        
        # Need refresh - returns new data without modifying self
        new_oauth_data = await self.refresh_token()
        return new_oauth_data["access_token"], new_oauth_data

