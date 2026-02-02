"""
Slack OAuth2 API credential for Slack API operations.
Based on n8n's SlackOAuth2Api.credentials.ts

This credential uses OAuth2 to authenticate with Slack, which is the recommended
method for most Slack integrations as it provides:
- User-level permissions (not just bot permissions)
- Automatic token refresh
- Better security than static tokens
"""
import aiohttp
import time
from typing import Dict, Any, List, ClassVar, Optional
from urllib.parse import urlencode
from .oAuth2Api import OAuth2ApiCredential


# User scopes matching n8n's SlackOAuth2Api.credentials.ts
# https://api.slack.com/scopes
# IMPORTANT: These must be configured in your Slack App's OAuth & Permissions
# Only request scopes that are added to your Slack App
USER_SCOPES = [
    'channels:read',
    'chat:write',
]

# Bot scopes for bot token operations
# IMPORTANT: These must be configured in your Slack App's OAuth & Permissions
# Only request scopes that are added to your Slack App
BOT_SCOPES = [
    'chat:write',           # Send messages
    'channels:read',        # View channel info
    'channels:history',     # View messages in channels
    'channels:join',        # Join public channels
]


class SlackOAuth2ApiCredential(OAuth2ApiCredential):
    """
    Slack OAuth2 credential implementation.
    
    This credential provides OAuth2 authentication for Slack API operations.
    It supports both user tokens and bot tokens through the OAuth2 flow.
    
    Authentication flow:
    1. Create a Slack App at https://api.slack.com/apps
    2. Configure OAuth & Permissions with required scopes
    3. Add redirect URL: {your_backend_url}/api/oauth2/callback
    4. Use this credential to initiate OAuth2 flow
    
    The credential will store:
    - access_token: User or bot access token
    - refresh_token: For token refresh (if available)
    - authed_user: Information about the authenticated user
    - team: Information about the Slack workspace
    """
    
    name = "slackOAuth2Api"
    display_name = "Slack OAuth2 API"
    
    @staticmethod
    def _build_properties() -> List[Dict[str, Any]]:
        """Build Slack-specific OAuth2 properties based on parent"""
        parent_props = OAuth2ApiCredential.properties
        hidden_fields = ["authUrl", "accessTokenUrl", "authQueryParameters", "authentication", "grantType"]
        modified_props: List[Dict[str, Any]] = []
        
        # Slack OAuth2 configuration
        # https://api.slack.com/authentication/oauth-v2
        # Bot scopes are passed via 'scope' parameter
        # User scopes are passed via 'user_scope' in authQueryParameters
        bot_scopes = ' '.join(BOT_SCOPES)
        user_scopes = ' '.join(USER_SCOPES)
        
        base_data = [
            {"authUrl": "https://slack.com/oauth/v2/authorize"},
            {"accessTokenUrl": "https://slack.com/api/oauth.v2.access"},
            {"authQueryParameters": f"user_scope={user_scopes}"},
            {"authentication": "body"},  # Slack uses body authentication
            {"grantType": "authorizationCode"},
            {"scope": bot_scopes},  # Bot scopes - all required scopes
        ]
        
        for prop in parent_props:
            prop_copy = prop.copy()
            
            if prop_copy["name"] in hidden_fields:
                prop_copy["type"] = "hidden"
            
            # Update scope field description for Slack
            if prop_copy["name"] == "scope":
                prop_copy.update({
                    "description": "Bot scopes (space-separated). Required scopes are pre-filled.",
                    "default": bot_scopes,
                })
            
            modified_props.append(prop_copy)
        
        # Apply defaults
        for current in modified_props:
            for d in base_data:
                for key, value in d.items():
                    if current["name"] == key:
                        current["default"] = value
        
        # Add Slack-specific notice
        modified_props.append({
            "name": "notice",
            "displayName": "Notice",
            "type": "notice",
            "default": "If you get an Invalid Scopes error, make sure you add the required scopes to your Slack App at https://api.slack.com/apps",
        })
        
        return modified_props
    
    properties: ClassVar[List[Dict[str, Any]]] = _build_properties()
    
    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access token (Slack-specific).
        
        Slack's OAuth2 response is different from standard OAuth2:
        - Returns 'authed_user' with user token
        - Returns 'access_token' for bot token
        - Returns 'team' information
        
        Args:
            code: Authorization code from Slack
            redirect_uri: Redirect URI used in authorization
            
        Returns:
            Token data dictionary
        """
        access_token_url = "https://slack.com/api/oauth.v2.access"
        
        token_data = {
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.data["clientId"],
            "client_secret": self.data["clientSecret"],
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                access_token_url,
                data=urlencode(token_data),
                headers=headers
            ) as response:
                response_data = await response.json()
                
                if not response_data.get("ok"):
                    error_msg = response_data.get("error", "Unknown error")
                    raise Exception(f"Slack OAuth error: {error_msg}")
                
                # Build OAuth token data from Slack's response
                oauth_data = {
                    "token_type": response_data.get("token_type", "bearer"),
                }
                
                # Bot token (access_token)
                if response_data.get("access_token"):
                    oauth_data["access_token"] = response_data["access_token"]
                    oauth_data["bot_token"] = response_data["access_token"]
                
                # User token (from authed_user)
                authed_user = response_data.get("authed_user", {})
                if authed_user.get("access_token"):
                    oauth_data["user_access_token"] = authed_user["access_token"]
                    # If no bot token, use user token as primary
                    if not oauth_data.get("access_token"):
                        oauth_data["access_token"] = authed_user["access_token"]
                
                # Refresh token (if available - Slack doesn't always provide this)
                if response_data.get("refresh_token"):
                    oauth_data["refresh_token"] = response_data["refresh_token"]
                
                # Expiration (if available)
                if response_data.get("expires_in"):
                    oauth_data["expires_in"] = response_data["expires_in"]
                    oauth_data["expires_at"] = time.time() + response_data["expires_in"]
                
                # Store additional Slack-specific data
                if response_data.get("team"):
                    oauth_data["team"] = response_data["team"]
                    oauth_data["team_id"] = response_data["team"].get("id")
                    oauth_data["team_name"] = response_data["team"].get("name")
                
                if authed_user:
                    oauth_data["authed_user"] = authed_user
                    oauth_data["user_id"] = authed_user.get("id")
                
                if response_data.get("bot_user_id"):
                    oauth_data["bot_user_id"] = response_data["bot_user_id"]
                
                if response_data.get("scope"):
                    oauth_data["scope"] = response_data["scope"]
                
                if response_data.get("app_id"):
                    oauth_data["app_id"] = response_data["app_id"]
                
                return oauth_data
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Slack OAuth2 credential.
        
        Tests the credential by calling the auth.test endpoint,
        which verifies the token and returns user/team information.
        
        Returns:
            Dictionary with test results
        """
        # Check if we have OAuth token data
        if not self.has_access_token(self.data):
            return {
                "success": False,
                "message": "OAuth credentials not connected. Please connect your Slack account first.",
                "needsOAuth": True
            }
        
        oauth_data = self.data.get("oauthTokenData", {})
        access_token = oauth_data.get("access_token")
        
        if not access_token:
            return {
                "success": False,
                "message": "No access token found. Please reconnect your Slack account.",
                "needsOAuth": True
            }
        
        try:
            # Test using auth.test endpoint
            url = "https://slack.com/api/auth.test"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers) as response:
                    data = await response.json()
                    
                    if data.get("ok"):
                        user = data.get("user", "Unknown")
                        team = data.get("team", "Unknown")
                        return {
                            "success": True,
                            "message": f"Successfully connected to Slack. User: {user}, Team: {team}"
                        }
                    else:
                        error = data.get("error", "Unknown error")
                        
                        # Handle specific errors
                        if error in ["token_expired", "token_revoked", "invalid_auth"]:
                            return {
                                "success": False,
                                "message": f"Slack token is invalid or expired: {error}. Please reconnect.",
                                "needsOAuth": True
                            }
                        
                        return {
                            "success": False,
                            "message": f"Slack API error: {error}"
                        }
                        
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "message": f"Network error testing Slack credential: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing Slack credential: {str(e)}"
            }
    
    async def refresh_token(self) -> Optional[Dict[str, Any]]:
        """
        Refresh Slack OAuth2 token.
        
        Note: Slack's standard OAuth2 flow doesn't support refresh tokens
        for user tokens. This method is provided for compatibility but
        may not work with all Slack token types.
        
        For token rotation (Enterprise Grid), Slack uses a different mechanism.
        
        Returns:
            Updated token data or None
        """
        oauth_data = self.data.get("oauthTokenData", {})
        refresh_token = oauth_data.get("refresh_token")
        
        if not refresh_token:
            # Slack doesn't always provide refresh tokens
            raise ValueError("No refresh token available. Slack user tokens typically don't expire.")
        
        # Use parent's refresh implementation
        return await super().refresh_token()
    
    def get_access_token_sync(self) -> str:
        """
        Get the current access token synchronously.
        
        Useful for node execution where async may not be available.
        Prefers bot token over user token.
        
        Returns:
            Access token string
        """
        oauth_data = self.data.get("oauthTokenData", {})
        
        # Prefer bot token, fall back to user token
        return (
            oauth_data.get("access_token") or 
            oauth_data.get("bot_token") or 
            oauth_data.get("user_access_token") or
            ""
        )
    
    def get_user_token(self) -> Optional[str]:
        """
        Get the user access token specifically.
        
        Returns:
            User access token or None
        """
        oauth_data = self.data.get("oauthTokenData", {})
        return oauth_data.get("user_access_token")
    
    def get_bot_token(self) -> Optional[str]:
        """
        Get the bot access token specifically.
        
        Returns:
            Bot access token or None
        """
        oauth_data = self.data.get("oauthTokenData", {})
        return oauth_data.get("bot_token") or oauth_data.get("access_token")
    
    def get_team_info(self) -> Dict[str, Any]:
        """
        Get Slack team information from OAuth data.
        
        Returns:
            Dictionary with team_id, team_name, etc.
        """
        oauth_data = self.data.get("oauthTokenData", {})
        return {
            "team_id": oauth_data.get("team_id"),
            "team_name": oauth_data.get("team_name"),
            "team": oauth_data.get("team", {}),
        }
    
    def get_auth_header(self) -> Dict[str, str]:
        """
        Get the authorization header for Slack API requests.
        
        Returns:
            Dictionary with Authorization header
        """
        access_token = self.get_access_token_sync()
        return {
            "Authorization": f"Bearer {access_token}"
        }
