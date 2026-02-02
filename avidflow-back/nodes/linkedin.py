import requests
import logging
import base64
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
from urllib.parse import urlencode
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)

class LinkedInNode(BaseNode):
    """
    LinkedIn node for interacting with LinkedIn API.
    """

    type = "linkedin"
    version = 1.0

    description = {
        "displayName": "LinkedIn",
        "name": "linkedin",
        "icon": "file:linkedin.svg",
        "group": ["output"],
        "description": "Post updates, get profile information, and interact with LinkedIn",
        "inputs": [
            {"name": "main", "type": "main", "required": True}
        ],
        "outputs": [
            {"name": "main", "type": "main", "required": True}
        ],
        "usableAsTool": True,
        "credentials": [
            {
                "name": "linkedinApi",
                "required": True
            }
        ]
    }

    properties = {
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "required": True,
                "options": [
                    {"name": "Post", "value": "post"},
                    {"name": "Profile", "value": "profile"},
                    {"name": "Company", "value": "company"}
                ],
                "default": "post",
                "description": "The LinkedIn resource to operate on"
            },
            {
                "name": "operation",
                    "type": NodeParameterType.OPTIONS,
                    "display_name": "Operation",
                    "required": True,
                    "options": [
                        {"name": "Get Profile", "value": "getProfile"},
                        {"name": "Create Post", "value": "createPost"},
                        {"name": "Get Company", "value": "getCompany"}
                    ],
                    "default": "getProfile",
                    "description": "The operation to perform (legacy format)",
                    "displayOptions": {
                        "hide": {
                            "resource": ["post", "profile", "company"]
                        }
                    }
            },
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "options": [
                    {"name": "Get", "value": "get"}
                ],
                "default": "get",
                "description": "The operation to perform",
                "displayOptions": {
                    "show": {
                        "resource": ["profile", "company"]
                    }
                }
            },
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "options": [
                    {"name": "Create", "value": "create"}
                ],
                "default": "create",
                "description": "The operation to perform",
                "displayOptions": {
                    "show": {
                        "resource": ["post"]
                    }
                }
            },
            {
                "name": "text",
                "type": NodeParameterType.STRING,
                "display_name": "Text",
                "description": "The text content of the post",
                "required": True,
                "typeOptions": {
                    "rows": 4
                },
                "displayOptions": {
                    "show": {
                        "resource": ["post"],
                        "operation": ["create"]
                    }
                }
            },
            {
                "name": "visibility",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Visibility",
                "options": [
                    {"name": "Public", "value": "PUBLIC"},
                    {"name": "Connections", "value": "CONNECTIONS"}
                ],
                "default": "PUBLIC",
                "description": "Who can see this post",
                "displayOptions": {
                    "show": {
                        "resource": ["post"],
                        "operation": ["create"]
                    }
                }
            },
            {
                "name": "additionalFields",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Additional Fields",
                "placeholder": "Add Field",
                "default": {},
                "displayOptions": {
                    "show": {
                        "resource": ["post"],
                        "operation": ["create"]
                    }
                },
                "options": [
                    {
                        "name": "mediaUrl",
                        "type": NodeParameterType.STRING,
                        "display_name": "Media URL",
                        "description": "URL of media to attach to the post"
                    },
                    {
                        "name": "mediaTitle",
                        "type": NodeParameterType.STRING,
                        "display_name": "Media Title",
                        "description": "Title for the attached media"
                    },
                    {
                        "name": "mediaDescription",
                        "type": NodeParameterType.STRING,
                        "display_name": "Media Description",
                        "description": "Description for the attached media"
                    }
                ]
            },
            {
                "name": "companyId",
                "type": NodeParameterType.STRING,
                "display_name": "Company ID",
                "description": "The LinkedIn company ID to get information for",
                "required": True,
                "displayOptions": {
                    "show": {
                        "resource": ["company"],
                        "operation": ["get"]
                    }
                }
            }
        ],
        "credentials": [
            {
                "name": "linkedinApi",
                "required": True
            }
        ]
    }

    icon = "linkedin.svg"
    color = "#0077B5"

    @staticmethod
    def has_access_token(credentials_data: Dict[str, Any]) -> bool:
        """Check if credentials have access token (n8n's approach)"""
        oauth_token_data = credentials_data.get('oauthTokenData')
        if not isinstance(oauth_token_data, dict):
            return False
        return 'access_token' in oauth_token_data

    def get_credential_type(self):
        return self.properties["credentials"][0]['name']

    def _is_token_expired(self, oauth_data: Dict[str, Any]) -> bool:
        """Check if the current token is expired"""
        if "expires_at" not in oauth_data:
            return False

        # Add 30 second buffer
        return time.time() > (oauth_data["expires_at"] - 30)
    
    def refresh_token(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Refresh OAuth2 access token (exact n8n implementation)"""
        if not data.get("oauthTokenData") or not data["oauthTokenData"].get("refresh_token"):
            raise ValueError("No refresh token available")

        oauth_data = data["oauthTokenData"]

        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": oauth_data["refresh_token"],
        }
        
        headers = {}
        
        # Add client credentials based on authentication method
        if data.get("authentication", "header") == "header":
            auth_header = base64.b64encode(
                f"{data['clientId']}:{data['clientSecret']}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {auth_header}"
        else:
            token_data.update({
                "client_id": data["clientId"],
                "client_secret": data["clientSecret"]
            })
        
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        
        try:
            response = requests.post(
                data["accessTokenUrl"],
                data=urlencode(token_data),
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                new_token_data = response.json()
                
                # Update token data (preserve existing data)
                updated_oauth_data = oauth_data.copy()
                updated_oauth_data["access_token"] = new_token_data["access_token"]
                
                if "expires_in" in new_token_data:
                    updated_oauth_data["expires_at"] = time.time() + new_token_data["expires_in"]
                
                # Only update refresh token if a new one is provided
                if "refresh_token" in new_token_data:
                    updated_oauth_data["refresh_token"] = new_token_data["refresh_token"]
                
                # Preserve any additional token data
                for key, value in new_token_data.items():
                    if key not in ["access_token", "expires_in", "refresh_token"]:
                        updated_oauth_data[key] = value
                
                # Save updated token data
                data["oauthTokenData"] = updated_oauth_data
                self.update_credentials(self.get_credential_type(), data)

                return data
            else:
                error_data = {}
                try:
                    error_data = response.json()
                except:
                    error_data = {"error": response.text}
                
                raise Exception(f"Token refresh failed with status {response.status_code}: {error_data.get('error', 'Unknown error')}")
                
        except requests.RequestException as e:
            raise Exception(f"Token refresh request failed: {str(e)}")
        except Exception as e:
             raise Exception(f"Token refresh failed: {str(e)}")
    
    def _get_access_token(self) -> str:
        """
        Get a valid access token for LinkedIn API from the credentials
        """
        try:
            # Get credentials
            credentials = self.get_credentials("linkedinApi")
            if not credentials:
                raise ValueError("LinkedIn OAuth2 credentials not found")

            if not self.has_access_token(credentials):
                raise ValueError("LinkedIn OAuth2 access token not found")

            if self._is_token_expired(credentials['oauthTokenData']):
                credentials = self.refresh_token(credentials)

            return credentials['oauthTokenData']['access_token']
            
        except Exception as e:
            logger.error(f"Error getting LinkedIn access token: {str(e)}")
            raise ValueError(f"Failed to get LinkedIn access token: {str(e)}")
    
    def linkedin_api_request(self, method: str, endpoint: str, body: Dict[str, Any] = None, query: Dict[str, Any] = None, api_version: str = "v2") -> Dict[str, Any]:
        """
        Make a request to the LinkedIn API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path (without base URL)
            body: Request body for POST/PUT requests
            query: Query parameters
            api_version: API version (v2 by default)
            
        Returns:
            API response as dictionary
        """
        # Get access token (will automatically handle token acquisition/refresh)
        access_token = self._get_access_token()
        
        # Set up request
        base_url = f"https://api.linkedin.com/{api_version}"
        url = f"{base_url}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0"
        }
        
        try:
            # Make the request
            if method.upper() == 'GET':
                response = requests.get(url, params=query, headers=headers, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, params=query, json=body, headers=headers, timeout=30)
            elif method.upper() == 'PUT':
                response = requests.put(url, params=query, json=body, headers=headers, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, params=query, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle errors
            response.raise_for_status()
            
            # Return the response data
            if response.content:
                return response.json()
            else:
                return {"success": True}
                
        except requests.RequestException as e:
            error_msg = str(e)
            try:
                if hasattr(e, 'response') and e.response:
                    error_data = e.response.json()
                    error_msg = f"LinkedIn API Error: {error_data.get('message', 'Unknown error')}"
                    
                    # Handle auth errors specifically
                    if e.response.status_code == 401:
                        # Token might be expired, invalidate it
                        credentials = self.get_credentials("linkedinApi")
                        if credentials:
                            credentials["accessToken"] = None
                            credentials["accessTokenExpiry"] = 0
                        error_msg += " - Will retry with new token on next request."
            except:
                pass
            logger.error(f"LinkedIn API request failed: {error_msg}")
            raise ValueError(error_msg)

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute LinkedIn node operations"""
        result_items: List[NodeExecutionData] = []
        
        try:
            # Get input items
            items = self.get_input_data()
            
            # Process each input item
            for i, item in enumerate(items):
                try:
                    # Check for direct operation format (backward compatibility)
                    direct_operation = self.get_node_parameter('operation', i, None)
                    
                    # Map old direct operations to resource-operation pairs
                    if direct_operation in ["getProfile", "createPost", "getCompany"]:
                        if direct_operation == "getProfile":
                            resource = "profile"
                            operation = "get"
                        elif direct_operation == "createPost":
                            resource = "post"
                            operation = "create"
                        elif direct_operation == "getCompany":
                            resource = "company"
                            operation = "get"
                    else:
                        # Get resource and operation for each item using new format
                        resource = self.get_node_parameter('resource', i, "profile")  # Default to profile
                        operation = self.get_node_parameter('operation', i, "get")    # Default to get
                    
                    if not resource:
                        raise ValueError(f"Resource parameter is required (received: {resource})")
                    
                    if not operation:
                        raise ValueError(f"Operation parameter is required (received: {operation})")
                    
                    if resource == 'profile':
                        if operation == 'get':
                            response_data = self._get_profile(i)
                        else:
                            raise ValueError(f"Unsupported profile operation: {operation}")
                    
                    elif resource == 'post':
                        if operation == 'create':
                            response_data = self._create_post(i)
                        else:
                            raise ValueError(f"Unsupported post operation: {operation}")
                    
                    elif resource == 'company':
                        if operation == 'get':
                            response_data = self._get_company(i)
                        else:
                            raise ValueError(f"Unsupported company operation: {operation}")
                    
                    else:
                        raise ValueError(f"Unsupported resource: {resource}")
                    
                    result_items.append(NodeExecutionData(
                        json_data=response_data,
                        item_index=i,
                        binary_data=None
                    ))
                    
                except Exception as e:
                    logger.error(f"LinkedIn Node - Error processing item {i}: {str(e)}")
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": self.get_node_parameter("resource", i, "profile"),
                            "operation": self.get_node_parameter("operation", i, "get"),
                            "item_index": i
                        },
                        binary_data=None
                    )
                    result_items.append(error_item)
        
            return [result_items]
            
        except Exception as e:
            logger.error(f"LinkedIn Node - Execute error: {str(e)}")
            error_data = [NodeExecutionData(
                json_data={"error": f"Error in LinkedIn node: {str(e)}"},
                binary_data=None
            )]
            return [error_data]

    def _get_profile(self, item_index: int) -> Dict[str, Any]:
        """Get the LinkedIn profile of the authenticated user"""
        try:
            # Try the userinfo endpoint first (OpenID Connect standard, more reliable)
            try:
                response_data = self.linkedin_api_request('GET', '/userinfo')
                return response_data
            except Exception as userinfo_error:
                logger.warning(f"userinfo endpoint failed: {str(userinfo_error)}, trying basic me endpoint")
            
            # Fallback to basic me endpoint without projection (safest approach)
            try:
                response_data = self.linkedin_api_request('GET', '/me')
                return response_data
            except Exception as me_error:
                logger.warning(f"Basic me endpoint failed: {str(me_error)}, trying with minimal projection")
            
            # Last resort: try with minimal safe projection
            response_data = self.linkedin_api_request(
                'GET', 
                '/me',
                query={
                    'projection': '(id,firstName,lastName)'
                }
            )
            
            return response_data
            
        except Exception as e:
            logger.error(f"Error getting LinkedIn profile: {str(e)}")
            raise

    def _create_post(self, item_index: int) -> Dict[str, Any]:
        """Create a post on LinkedIn"""
        try:
            text = self.get_node_parameter("text", item_index, "")
            visibility = self.get_node_parameter("visibility", item_index, "PUBLIC")
            additional_fields = self.get_node_parameter("additionalFields", item_index, {})
            
            if not text:
                raise ValueError("Text is required for creating a post")
            
            # Get the authenticated user's ID
            profile = self.linkedin_api_request('GET', '/me')
            author_urn = f"urn:li:person:{profile.get('id')}"
            
            # Build the post payload
            post_data = {
                "author": author_urn,
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {
                            "text": text
                        },
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {
                    "com.linkedin.ugc.MemberNetworkVisibility": visibility
                }
            }
            
            # Add media if provided
            if additional_fields.get("mediaUrl"):
                media_url = additional_fields["mediaUrl"]
                media_title = additional_fields.get("mediaTitle", "")
                media_description = additional_fields.get("mediaDescription", "")
                
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["shareMediaCategory"] = "ARTICLE"
                post_data["specificContent"]["com.linkedin.ugc.ShareContent"]["media"] = [{
                    "status": "READY",
                    "description": {
                        "text": media_description
                    },
                    "originalUrl": media_url,
                    "title": {
                        "text": media_title
                    }
                }]
            
            # Create the post
            response_data = self.linkedin_api_request('POST', '/ugcPosts', body=post_data)
            
            return {
                "success": True,
                "postId": response_data.get("id"),
                "author": author_urn,
                "text": text,
                "visibility": visibility,
                "response": response_data
            }
            
        except Exception as e:
            logger.error(f"Error creating LinkedIn post: {str(e)}")
            raise

    def _get_company(self, item_index: int) -> Dict[str, Any]:
        """Get company information"""
        try:
            company_id = self.get_node_parameter("companyId", item_index, "")
            
            if not company_id:
                raise ValueError("Company ID is required")
            
            # Get company information with basic fields first
            try:
                response_data = self.linkedin_api_request(
                    'GET',
                    f'/companies/{company_id}'
                )
                return response_data
            except Exception as e:
                # If basic request fails, try with minimal projection
                response_data = self.linkedin_api_request(
                    'GET',
                    f'/companies/{company_id}',
                    query={
                        'projection': '(id,name)'
                    }
                )
                return response_data
            
        except Exception as e:
            logger.error(f"Error getting LinkedIn company: {str(e)}")
            raise