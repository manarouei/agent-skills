"""
GitHub API credential for accessing GitHub repositories and resources.
Supports personal access tokens for authentication.

Converted from TypeScript by agent-skills/credential-convert
Correlation ID: node-github-019
Generated: 2026-01-06

SYNC-CELERY SAFE: All methods are synchronous with timeouts.
"""
import requests
from typing import Dict, Any
from urllib.parse import urljoin

from .base import BaseCredential


class GithubApiCredential(BaseCredential):
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
            "default": "",
            "required": False,
            "description": "GitHub username (optional)"
        },
        {
            "name": "accessToken",
            "displayName": "Access Token",
            "type": "string",
            "required": True,
            "typeOptions": {"password": True},
            "description": "GitHub personal access token"
        }
    ]
    
    def test(self) -> Dict[str, Any]:
        """
        Test the GitHub credentials by fetching user information.
        
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
            server = self.data.get("server", "https://api.github.com").rstrip("/")
            access_token = self.data.get("accessToken")
            
            if not access_token:
                return {
                    "success": False,
                    "message": "Access token is required"
                }
            
            # Test the credentials by making a request to get user info
            headers = {
                "Authorization": f"token {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "n8n-python"
            }
            
            url = urljoin(server, "/user")
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get("login", "Unknown")
                return {
                    "success": True,
                    "message": f"Successfully connected to GitHub as {username}",
                    "data": {
                        "user_id": user_data.get("id"),
                        "username": username,
                        "name": user_data.get("name"),
                        "email": user_data.get("email"),
                        "server": server
                    }
                }
            elif response.status_code == 401:
                return {
                    "success": False,
                    "message": "Invalid access token. Please check your GitHub access token."
                }
            elif response.status_code == 403:
                return {
                    "success": False,
                    "message": "Access forbidden. Check token permissions or rate limits."
                }
            else:
                return {
                    "success": False,
                    "message": f"GitHub API error: {response.status_code} - {response.text}"
                }
                
        except requests.Timeout:
            return {
                "success": False,
                "message": "Connection timeout. Please check your network or server URL."
            }
        except requests.ConnectionError as e:
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
            
        return {
            "Authorization": f"token {access_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "n8n-python"
        }
    
    def get_server_url(self) -> str:
        """Get the GitHub server URL"""
        return self.data.get("server", "https://api.github.com").rstrip("/")
    
    def get_api_url(self, endpoint: str = "") -> str:
        """Get the full API URL for a given endpoint"""
        server = self.get_server_url()
        if endpoint:
            return urljoin(server, endpoint)
        return server
