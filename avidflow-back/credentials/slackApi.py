"""
Slack API credential for Slack API operations.
Based on n8n's SlackApi.credentials.ts
"""
import aiohttp
from typing import Dict, Any
from .base import BaseCredential


class SlackApiCredential(BaseCredential):
    """
    Slack API credential implementation.
    
    This credential provides authentication for Slack API operations using
    a Bot User OAuth Access Token.
    
    Authentication flow:
    1. Create a Slack App at https://api.slack.com/apps
    2. Add required OAuth scopes (e.g., chat:write, channels:read, users:read)
    3. Install the app to your workspace
    4. Copy the Bot User OAuth Token (starts with xoxb-)
    
    Required scopes depend on operations:
    - chat:write - Send messages
    - channels:read - List channels
    - channels:write - Create/archive channels
    - users:read - List users
    - files:write - Upload files
    - reactions:read - Get reactions
    - reactions:write - Add/remove reactions
    - stars:read - List starred items
    - stars:write - Add/remove stars
    - usergroups:read - List user groups
    - usergroups:write - Create/update user groups
    """
    
    name = "slackApi"
    display_name = "Slack API"
    
    properties = [
        {
            "name": "accessToken",
            "displayName": "Access Token",
            "type": "string",
            "typeOptions": {"password": True},
            "required": True,
            "default": "",
            "description": "Bot User OAuth Access Token (starts with xoxb-). Get it from your Slack App's OAuth & Permissions page."
        },
        {
            "name": "signatureSecret",
            "displayName": "Signature Secret",
            "type": "string",
            "typeOptions": {"password": True},
            "required": False,
            "default": "",
            "description": "The signature secret is used to verify the authenticity of requests sent by Slack. Found in your Slack App's Basic Information page."
        },
    ]
    
    async def test(self) -> Dict[str, Any]:
        """
        Test the Slack API credential by getting the authenticated user's profile.
        
        Uses the users.profile.get endpoint which requires minimal permissions
        and verifies the token is valid.
        
        Returns:
            Dictionary with test results (success, message)
        """
        # Validate required fields first
        validation = self.validate()
        if not validation["valid"]:
            return {
                "success": False,
                "message": validation["message"]
            }
        
        try:
            access_token = self.data.get("accessToken", "")
            
            if not access_token:
                return {
                    "success": False,
                    "message": "Access token is required"
                }
            
            # Test the credential by getting the user profile
            url = "https://slack.com/api/users.profile.get"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    data = await response.json()
                    
                    # Check for invalid_auth error
                    if data.get("error") == "invalid_auth":
                        return {
                            "success": False,
                            "message": "Invalid access token"
                        }
                    
                    # Check if the request was successful
                    if data.get("ok"):
                        # Extract display name from profile if available
                        profile = data.get("profile", {})
                        display_name = profile.get("display_name") or profile.get("real_name") or "Unknown"
                        return {
                            "success": True,
                            "message": f"Successfully connected to Slack API. User: {display_name}"
                        }
                    else:
                        error_msg = data.get("error", "Unknown error")
                        return {
                            "success": False,
                            "message": f"Slack API error: {error_msg}"
                        }
                        
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "message": f"Network error testing Slack API credential: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Error testing Slack API credential: {str(e)}"
            }
    
    def get_auth_header(self) -> Dict[str, str]:
        """
        Get the authorization header for Slack API requests.
        
        Returns:
            Dictionary with Authorization header
        """
        access_token = self.data.get("accessToken", "")
        return {
            "Authorization": f"Bearer {access_token}"
        }
    
    def verify_signature(self, timestamp: str, body: str, signature: str) -> bool:
        """
        Verify a Slack request signature.
        
        Used to verify the authenticity of incoming webhook requests from Slack.
        
        Args:
            timestamp: The X-Slack-Request-Timestamp header value
            body: The raw request body
            signature: The X-Slack-Signature header value
            
        Returns:
            True if the signature is valid, False otherwise
        """
        import hmac
        import hashlib
        
        signing_secret = self.data.get("signatureSecret", "")
        
        if not signing_secret:
            # If no signing secret is configured, skip verification
            # This matches n8n's behavior where the secret is optional
            return True
        
        # Create the signature base string
        sig_basestring = f"v0:{timestamp}:{body}"
        
        # Calculate the expected signature
        expected_sig = "v0=" + hmac.new(
            signing_secret.encode("utf-8"),
            sig_basestring.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures in constant time to prevent timing attacks
        return hmac.compare_digest(expected_sig, signature)
