"""
GitHub API credential for accessing GitHub repositories and resources.
Supports both personal access tokens and OAuth2.
"""
import aiohttp
from typing import Dict, Any, Optional
from urllib.parse import urljoin

from .base import BaseCredential


class GitHubApiCredential(BaseCredential):
    """GitHub API credential implementation"""
    
    name = "githubApi"
    display_name = "GitHub API"
    properties = [
        {
            "name": "server",
            "displayName": "Github Server",
            "type": "string",
            "default": "https://api.github.com",
            "required": True,
            "description": "The server to connect to. Only has to be set if Github Enterprise is used."
        },
        {
            "name": "user",
            "displayName": "User",
            "type": "string",
            "required": False,
            "description": "GitHub username (optional)"
        },
        {
            "name": "accessToken",
            "displayName": "Access Token",
            "type": "password",
            "required": True,
            "description": "GitHub personal access token"
        }
    ]
    
    async def validate(self) -> bool:
        """Validate the GitHub credentials"""
        try:
            server = self.data.get("server", "https://api.github.com").rstrip("/")
            access_token = self.data.get("accessToken")
            
            if not access_token:
                return False
                
            # Test the credentials by making a request to get user info
            headers = {
                "Authorization": f"token {access_token}",
                "User-Agent": "n8n",
                "Accept": "application/vnd.github.v3+json"
            }
            
            async with aiohttp.ClientSession() as session:
                url = f"{server}/user"
                async with session.get(url, headers=headers) as response:
                    return response.status == 200
                    
        except Exception:
            return False
    
    async def test(self) -> Dict[str, Any]:
        """Test the GitHub credentials and return user information"""
        try:
            server = self.data.get("server", "https://api.github.com").rstrip("/")
            access_token = self.data.get("accessToken")
            
            if not access_token:
                return {
                    "success": False,
                    "message": "Access token is required"
                }
            
            # GitHub uses "token" prefix instead of "Bearer"
            headers = {
                "Authorization": f"token {access_token}",
                "User-Agent": "n8n",
                "Accept": "application/vnd.github.v3+json"
            }
            
            async with aiohttp.ClientSession() as session:
                # Get user information
                url = f"{server}/user"
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        user_data = await response.json()
                        return {
                            "success": True,
                            "message": f"Successfully connected to GitHub as {user_data.get('name', user_data.get('login', 'Unknown'))}",
                            "data": {
                                "user_id": user_data.get("id"),
                                "username": user_data.get("login"),
                                "name": user_data.get("name"),
                                "email": user_data.get("email"),
                                "server": server
                            }
                        }
                    elif response.status == 401:
                        return {
                            "success": False,
                            "message": "Invalid access token. Please check your GitHub personal access token."
                        }
                    else:
                        error_text = await response.text()
                        return {
                            "success": False,
                            "message": f"GitHub API error: {response.status} - {error_text}"
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
        """Get authentication headers for GitHub API requests"""
        access_token = self.data.get("accessToken")
        if not access_token:
            raise ValueError("Access token not found in credentials")
            
        # GitHub uses "token" prefix in Authorization header
        return {
            "Authorization": f"token {access_token}",
            "User-Agent": "n8n",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def get_server_url(self) -> str:
        """Get the GitHub server URL"""
        return self.data.get("server", "https://api.github.com").rstrip("/")
    
    def get_api_url(self, endpoint: str = "") -> str:
        """Get the full API URL for a given endpoint"""
        server = self.get_server_url()
        if endpoint:
            # GitHub API URLs don't have /api/v4 like GitLab
            # Endpoints already include full path from root
            if endpoint.startswith('/'):
                return f"{server}{endpoint}"
            else:
                return f"{server}/{endpoint}"
        return server
