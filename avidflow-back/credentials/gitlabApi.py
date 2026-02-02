"""
GitLab API credential for accessing GitLab repositories and resources.
Supports both access token authentication and OAuth2.
"""
import aiohttp
from typing import Dict, Any, Optional
from urllib.parse import urljoin

from .base import BaseCredential


class GitLabApiCredential(BaseCredential):
    """GitLab API credential implementation"""
    
    name = "gitlabApi"
    display_name = "GitLab API"
    properties = [
        {
            "name": "server",
            "displayName": "GitLab Server",
            "type": "string",
            "default": "https://gitlab.com",
            "required": True,
            "description": "The GitLab server URL (e.g., https://gitlab.com or your self-hosted instance)"
        },
        {
            "name": "accessToken",
            "displayName": "Access Token",
            "type": "password",
            "required": True,
            "description": "GitLab personal access token or OAuth2 access token"
        }
    ]
    
    async def validate(self) -> bool:
        """Validate the GitLab credentials"""
        try:
            server = self.data.get("server", "https://gitlab.com").rstrip("/")
            access_token = self.data.get("accessToken")
            
            if not access_token:
                return False
                
            # Test the credentials by making a request to get user info
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                url = urljoin(server, "/api/v4/user")
                async with session.get(url, headers=headers) as response:
                    return response.status == 200
                    
        except Exception:
            return False
    
    async def test(self) -> Dict[str, Any]:
        """Test the GitLab credentials and return user information"""
        try:
            server = self.data.get("server", "https://gitlab.com").rstrip("/")
            access_token = self.data.get("accessToken")
            
            if not access_token:
                return {
                    "success": False,
                    "message": "Access token is required"
                }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                # Get user information
                url = urljoin(server, "/api/v4/user")
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        return {
                            "success": True,
                            "message": f"Successfully connected to GitLab as {user_data.get('name', user_data.get('username', 'Unknown'))}",
                            "data": {
                                "user_id": user_data.get("id"),
                                "username": user_data.get("username"),
                                "name": user_data.get("name"),
                                "email": user_data.get("email"),
                                "server": server
                            }
                        }
                    elif response.status == 401:
                        return {
                            "success": False,
                            "message": "Invalid access token. Please check your GitLab access token."
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "message": f"GitLab API error: {response.status} - {error_text}"
                        }
                        
        except aiohttp.ClientError as e:
            return {
                "success": False,
                "message": f"Connection error: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Unexpected error: {str(e)}"
            }
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for GitLab API requests"""
        access_token = self.data.get("accessToken")
        if not access_token:
            raise ValueError("Access token not found in credentials")
            
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    def get_server_url(self) -> str:
        """Get the GitLab server URL"""
        return self.data.get("server", "https://gitlab.com").rstrip("/")
    
    def get_api_url(self, endpoint: str = "") -> str:
        """Get the full API URL for a given endpoint"""
        server = self.get_server_url()
        base_api_url = urljoin(server, "/api/v4/")
        if endpoint:
            return urljoin(base_api_url, endpoint)
        return base_api_url
