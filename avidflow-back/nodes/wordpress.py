from typing import Dict, Any, List
from nodes.base import BaseNode, NodeExecutionData, GetNodeParameterOptions, NodeParameterType
import requests
import base64
import time
from datetime import datetime
from typing import Optional
from urllib.parse import urlencode
import logging
from credentials.wordpressApi import WordpressApiCredential
import json
from utils.serialization import deep_serialize
from utils.expression_evaluator import ExpressionEngine

logger = logging.getLogger(__name__)


class WordPressNode(BaseNode):
    """Node to interact with WordPress API (both self-hosted and WordPress.com)"""
    
    type = "wordpress"
    version = 1
    icon = "file:wordpress.svg"
    
    description = {
        "displayName": "WordPress",
        "name": "wordpress",
        "icon": "file:wordpress.svg",
        "group": ["output"],
        "version": 1,
        "description": "Consume WordPress API",
        "defaults": {
            "name": "WordPress",
        },
        "inputs": [{"type": "main"}],
        "outputs": [{"type": "main"}]
    }
    
    properties = {
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "required": True,
                "display_name": "Resource",
                "description": "The resource to operate on",
                "default": "post",
                "options": [
                    {"name": "Post", "value": "post"},
                    {"name": "Page", "value": "page"},
                    {"name": "User", "value": "user"}
                ]
            },
            # POST OPERATIONS
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "required": True,
                "display_name": "Operation",
                "description": "The operation to perform",
                "default": "getAll",
                "display_options": {
                    "show": {
                        "resource": ["post"]
                    }
                },
                "options": [
                    {"name": "Create", "value": "create", "description": "Create a post"},
                    {"name": "Update", "value": "update", "description": "Update a post"},
                    {"name": "Get", "value": "get", "description": "Get a post"},
                    {"name": "Get All", "value": "getAll", "description": "Get all posts"},
                    {"name": "Delete", "value": "delete", "description": "Delete a post"}
                ]
            },
            # PAGE OPERATIONS
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "required": True,
                "display_name": "Operation",
                "description": "The operation to perform",
                "default": "getAll",
                "display_options": {
                    "show": {
                        "resource": ["page"]
                    }
                },
                "options": [
                    {"name": "Create", "value": "create", "description": "Create a page"},
                    {"name": "Update", "value": "update", "description": "Update a page"},
                    {"name": "Get", "value": "get", "description": "Get a page"},
                    {"name": "Get All", "value": "getAll", "description": "Get all pages"},
                    {"name": "Delete", "value": "delete", "description": "Delete a page"}
                ]
            },
            # USER OPERATIONS
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "required": True,
                "display_name": "Operation",
                "description": "The operation to perform",
                "default": "getAll",
                "display_options": {
                    "show": {
                        "resource": ["user"]
                    }
                },
                "options": [
                    {"name": "Create", "value": "create", "description": "Create a user"},
                    {"name": "Update", "value": "update", "description": "Update a user"},
                    {"name": "Get", "value": "get", "description": "Get a user"},
                    {"name": "Get All", "value": "getAll", "description": "Get all users"},
                    {"name": "Delete", "value": "delete", "description": "Delete a user"}
                ]
            },
            # COMMON PARAMETERS FOR GET ALL OPERATIONS
            {
                "name": "returnAll",
                "type": NodeParameterType.BOOLEAN,
                "required": False,
                "display_name": "Return All",
                "description": "Whether to return all results or only up to a given limit",
                "default": False,
                "display_options": {
                    "show": {
                        "operation": ["getAll"]
                    }
                }
            },
            {
                "name": "limit",
                "type": NodeParameterType.NUMBER,
                "required": False,
                "display_name": "Limit",
                "description": "Max number of results to return",
                "default": 50,
                "display_options": {
                    "show": {
                        "operation": ["getAll"],
                        "returnAll": [False]
                    }
                },
                "type_options": {
                    "minValue": 1,
                    "maxValue": 100
                }
            },
            # ID PARAMETERS FOR SINGLE ITEM OPERATIONS
            {
                "name": "postId",
                "type": NodeParameterType.STRING,
                "required": True,
                "display_name": "Post ID",
                "description": "The ID of the post",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["post"],
                        "operation": ["get", "update", "delete"]
                    }
                }
            },
            {
                "name": "pageId",
                "type": NodeParameterType.STRING,
                "required": True,
                "display_name": "Page ID",
                "description": "The ID of the page",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["page"],
                        "operation": ["get", "update", "delete"]
                    }
                }
            },
            {
                "name": "userId",
                "type": NodeParameterType.STRING,
                "required": True,
                "display_name": "User ID",
                "description": "The ID of the user",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["user"],
                        "operation": ["get", "update", "delete"]
                    }
                }
            },
            # CREATE/UPDATE POST PARAMETERS
            {
                "name": "title",
                "type": NodeParameterType.STRING,
                "required": True,
                "display_name": "Title",
                "description": "The title of the post/page",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["post", "page"],
                        "operation": ["create"]
                    }
                }
            },
            {
                "name": "additionalFields",
                "type": NodeParameterType.COLLECTION,
                "required": False,
                "display_name": "Additional Fields",
                "description": "Additional fields to include in the request",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["post", "page"],
                        "operation": ["create"]
                    }
                },
                "options": [
                    {
                        "name": "authorId",
                        "type": NodeParameterType.STRING,
                        "display_name": "Author ID",
                        "description": "The ID of the author",
                        "default": ""
                    },
                    {
                        "name": "content",
                        "type": NodeParameterType.STRING,
                        "display_name": "Content",
                        "description": "The content of the post/page",
                        "default": ""
                    },
                    {
                        "name": "slug",
                        "type": NodeParameterType.STRING,
                        "display_name": "Slug",
                        "description": "The slug of the post/page",
                        "default": ""
                    },
                    {
                        "name": "status",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Status",
                        "description": "The status of the post/page",
                        "default": "draft",
                        "options": [
                            {"name": "Draft", "value": "draft"},
                            {"name": "Pending", "value": "pending"},
                            {"name": "Private", "value": "private"},
                            {"name": "Publish", "value": "publish"}
                        ]
                    }
                ]
            },
            # UPDATE FIELDS
            {
                "name": "updateFields",
                "type": NodeParameterType.COLLECTION,
                "required": False,
                "display_name": "Update Fields",
                "description": "Fields to update in the request",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["post", "page"],
                        "operation": ["update"]
                    }
                },
                "options": [
                    {
                        "name": "title",
                        "type": NodeParameterType.STRING,
                        "display_name": "Title",
                        "description": "The title of the post/page",
                        "default": ""
                    },
                    {
                        "name": "authorId",
                        "type": NodeParameterType.STRING,
                        "display_name": "Author ID",
                        "description": "The ID of the author",
                        "default": ""
                    },
                    {
                        "name": "content",
                        "type": NodeParameterType.STRING,
                        "display_name": "Content",
                        "description": "The content of the post/page",
                        "default": ""
                    },
                    {
                        "name": "slug",
                        "type": NodeParameterType.STRING,
                        "display_name": "Slug",
                        "description": "The slug of the post/page",
                        "default": ""
                    },
                    {
                        "name": "status",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Status",
                        "description": "The status of the post/page",
                        "default": "draft",
                        "options": [
                            {"name": "Draft", "value": "draft"},
                            {"name": "Pending", "value": "pending"},
                            {"name": "Private", "value": "private"},
                            {"name": "Publish", "value": "publish"}
                        ]
                    }
                ]
            },
            # USER CREATE/UPDATE PARAMETERS
            {
                "name": "username",
                "type": NodeParameterType.STRING,
                "required": True,
                "display_name": "Username",
                "description": "The username of the user",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["user"],
                        "operation": ["create"]
                    }
                }
            },
            {
                "name": "email",
                "type": NodeParameterType.STRING,
                "required": True,
                "display_name": "Email",
                "description": "The email of the user",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["user"],
                        "operation": ["create"]
                    }
                }
            },
            {
                "name": "password",
                "type": NodeParameterType.STRING,
                "required": True,
                "display_name": "Password",
                "description": "The password of the user",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["user"],
                        "operation": ["create"]
                    }
                },
                "type_options": {
                    "password": True
                }
            },
            {
                "name": "userAdditionalFields",
                "type": NodeParameterType.COLLECTION,
                "required": False,
                "display_name": "User Additional Fields",
                "description": "Additional fields for user creation",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["user"],
                        "operation": ["create"]
                    }
                },
                "options": [
                    {
                        "name": "firstName",
                        "type": NodeParameterType.STRING,
                        "display_name": "First Name",
                        "description": "The first name of the user",
                        "default": ""
                    },
                    {
                        "name": "lastName",
                        "type": NodeParameterType.STRING,
                        "display_name": "Last Name",
                        "description": "The last name of the user",
                        "default": ""
                    },
                    {
                        "name": "nickname",
                        "type": NodeParameterType.STRING,
                        "display_name": "Nickname",
                        "description": "The nickname of the user",
                        "default": ""
                    },
                    {
                        "name": "description",
                        "type": NodeParameterType.STRING,
                        "display_name": "Description",
                        "description": "The description of the user",
                        "default": ""
                    },
                    {
                        "name": "roles",
                        "type": NodeParameterType.STRING,
                        "display_name": "Roles",
                        "description": "The roles of the user (comma-separated)",
                        "default": ""
                    }
                ]
            },
            {
                "name": "userUpdateFields",
                "type": NodeParameterType.COLLECTION,
                "required": False,
                "display_name": "User Update Fields",
                "description": "Fields to update for the user",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["user"],
                        "operation": ["update"]
                    }
                },
                "options": [
                    {
                        "name": "username",
                        "type": NodeParameterType.STRING,
                        "display_name": "Username",
                        "description": "The username of the user",
                        "default": ""
                    },
                    {
                        "name": "email",
                        "type": NodeParameterType.STRING,
                        "display_name": "Email",
                        "description": "The email of the user",
                        "default": ""
                    },
                    {
                        "name": "password",
                        "type": NodeParameterType.STRING,
                        "display_name": "Password",
                        "description": "The password of the user",
                        "default": "",
                        "type_options": {
                            "password": True
                        }
                    },
                    {
                        "name": "firstName",
                        "type": NodeParameterType.STRING,
                        "display_name": "First Name",
                        "description": "The first name of the user",
                        "default": ""
                    },
                    {
                        "name": "lastName",
                        "type": NodeParameterType.STRING,
                        "display_name": "Last Name",
                        "description": "The last name of the user",
                        "default": ""
                    },
                    {
                        "name": "nickname",
                        "type": NodeParameterType.STRING,
                        "display_name": "Nickname",
                        "description": "The nickname of the user",
                        "default": ""
                    },
                    {
                        "name": "description",
                        "type": NodeParameterType.STRING,
                        "display_name": "Description",
                        "description": "The description of the user",
                        "default": ""
                    },
                    {
                        "name": "roles",
                        "type": NodeParameterType.STRING,
                        "display_name": "Roles",
                        "description": "The roles of the user (comma-separated)",
                        "default": ""
                    }
                ]
            }
        ],
        "credentials": [
            {
                "name": "wordpressApi",
                "required": True
            }
        ]
    }

    # Authentication helper methods
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
        """Refresh OAuth2 access token with improved credential handling"""
        if not data.get("oauthTokenData") or not data["oauthTokenData"].get("refresh_token"):
            raise ValueError("No refresh token available")

        oauth_data = data["oauthTokenData"]
        refresh_token = oauth_data["refresh_token"]
        client_id = data["clientId"]
        client_secret = data["clientSecret"]

        # Create base token request data
        token_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        
        # First try the body authentication method with proper URL encoding
        body_auth_data = token_data.copy()
        body_auth_data.update({
            "client_id": client_id,
            "client_secret": client_secret
        })
        
        # Prepare headers - application/x-www-form-urlencoded is REQUIRED
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json"
        }
        
        try:
            # Make the request with client credentials in body
            response = requests.post(
                data["accessTokenUrl"],
                data=urlencode(body_auth_data),
                headers=headers,
                timeout=30
            )
            
            # If body auth failed, try header auth
            if response.status_code == 400 and "invalid_client" in response.text:

                auth_str = f"{client_id}:{client_secret}"
                auth_header = base64.b64encode(auth_str.encode()).decode()
                headers["Authorization"] = f"Basic {auth_header}"
                
                # Make the request with client credentials in header
                response = requests.post(
                    data["accessTokenUrl"],
                    data=urlencode(token_data),  # only include grant_type and refresh_token
                    headers=headers,
                    timeout=30
                )
            
            if response.status_code == 200:
                # Successfully refreshed token
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
                logger.error(f"Response body: {response.text}")
                
                try:
                    error_data = response.json()
                    error_message = f"Token refresh failed with status {response.status_code}: {error_data.get('error', '')}"
                    if 'error_description' in error_data:
                        error_message += f" - {error_data['error_description']}"
                except:
                    error_message = f"Token refresh failed with status {response.status_code}: {response.text}"
            
                raise Exception(error_message)
                
        except requests.RequestException as e:
            logger.error(f"Token refresh request failed: {str(e)}")
            raise Exception(f"Token refresh request failed: {str(e)}")
        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            raise Exception(f"Token refresh failed: {str(e)}")
    
    def reauthorize_instead_of_refresh(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """Instead of refreshing, provide instructions to reauthorize"""
        msg = (
            "This WordPress site doesn't support token refresh. "
            "Please reauthorize this credential through the OAuth2 flow."
        )
        logger.error(msg)
        raise ValueError(msg)

    def _get_access_token(self) -> str:
        """
        Get a valid access token for WordPress API from the credentials
        """
        try:
            # Get credentials
            credentials = self.get_credentials("wordpressApi")
            if not credentials:
                raise ValueError("WordPress OAuth2 credentials not found")

            if not self.has_access_token(credentials):
                raise ValueError("WordPress OAuth2 access token not found")
            
            oauth_data = credentials.get('oauthTokenData', {})
            
            # Check if token is expired
            if 'access_token' in oauth_data:
                # If token is expired, don't try to refresh, just notify to reauthorize
                if self._is_token_expired(oauth_data):
                    self.reauthorize_instead_of_refresh(credentials)
                else:
                    logger.info("Using existing valid access token")
                    
                return oauth_data['access_token']
                
            # If we get here, we don't have a valid token
            raise ValueError("No valid access token available")
            
        except Exception as e:
            logger.error(f"Error getting WordPress access token: {str(e)}")
            raise ValueError(f"Failed to get WordPress access token: {str(e)}")

    
    # API URL helpers
    def get_api_url(self, resource: str) -> str:
        """Return the API URL for the resource (WordPress API)"""
        credentials = self.get_credentials("wordpressApi")
        base_url = credentials.get("url", "").strip().rstrip("/")
        
        # Remove protocol if present
        if base_url.startswith(("http://", "https://")):
            if "://" in base_url:
                base_url = base_url.split("://")[1]
        
        # Determine if it's WordPress.com or self-hosted
        if "wordpress.com" in base_url:
            # WordPress.com API
            api_url = f"https://public-api.wordpress.com/rest/v1.1/sites/{base_url}/{resource}"
        else:
            # Check if base_url already has protocol
            if not base_url.startswith(("http://", "https://")):
                base_url = f"https://{base_url}"
            # Self-hosted WordPress with WP REST API
            api_url = f"{base_url}/wp-json/wp/v2/{resource}"

        return api_url
    
    # Authentication helpers
    def get_auth_headers(self) -> dict:
        """Return headers for OAuth2 requests"""
        try:
            access_token = self._get_access_token()
            
            # Check if the site is WordPress.com or self-hosted
            credentials = self.get_credentials("wordpressApi")
            base_url = credentials.get("url", "").strip().rstrip("/")
            
            # WordPress.com uses Bearer token
            if "wordpress.com" in base_url:
                return {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            # WordPress with JWT authentication plugin might use different header
            elif base_url and "/wp-json/" in self.get_api_url("posts"):
                return {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            # Default OAuth2 headers
            else:
                return {
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
        except Exception as e:
            logger.error(f"Error creating auth headers: {str(e)}")
            # Return basic headers without auth as fallback
            return {
                "Accept": "application/json",
                "Content-Type": "application/json"
            }

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute the WordPress node operations"""

        result_items: List[NodeExecutionData] = []
        
        try:
            # Get input items
            items = self.get_input_data()
            
            # Process each input item
            for i, item in enumerate(items):
                try:
                    # Get parameters for this item
                    resource = self.get_node_parameter("resource", i, "post")
                    operation = self.get_node_parameter("operation", i, "getAll")
                  
                    # Execute the appropriate operation based on resource and operation
                    if resource == "post":
                        if operation == "getAll":
                            result = self._get_all_posts(i)
                        elif operation == "get":
                            result = self._get_post(i)
                        elif operation == "create":
                            result = self._create_post(i)
                        elif operation == "update":
                            result = self._update_post(i)
                        elif operation == "delete":
                            result = self._delete_post(i)
                        else:
                            raise ValueError(f"Unsupported operation '{operation}' for resource '{resource}'")
                    
                    elif resource == "page":
                        if operation == "getAll":
                            result = self._get_all_pages(i)
                        elif operation == "get":
                            result = self._get_page(i)
                        elif operation == "create":
                            result = self._create_page(i)
                        elif operation == "update":
                            result = self._update_page(i)
                        elif operation == "delete":
                            result = self._delete_page(i)
                        else:
                            raise ValueError(f"Unsupported operation '{operation}' for resource '{resource}'")
                            
                    elif resource == "user":
                        if operation == "getAll":
                            result = self._get_all_users(i)
                        elif operation == "get":
                            result = self._get_user(i)
                        elif operation == "create":
                            result = self._create_user(i)
                        elif operation == "update":
                            result = self._update_user(i)
                        elif operation == "delete":
                            result = self._delete_user(i)
                        else:
                            raise ValueError(f"Unsupported operation '{operation}' for resource '{resource}'")
                    else:
                        raise ValueError(f"Unsupported resource '{resource}'")
                
                    # Add result to output
                    result_items.append(NodeExecutionData(
                        json_data=result,
                        binary_data=None,
                        pairedItem={"item": i}
                    ))
                    
                except Exception as e:
                    logger.error(f"WordPress Node - Error processing item {i}: {str(e)}", exc_info=True)
                    if hasattr(self.node_data, 'continueOnFail') and self.node_data.continueOnFail:
                        result_items.append(NodeExecutionData(
                            json_data={"error": str(e)},
                            binary_data=None,
                            pairedItem={"item": i}
                        ))
                    else:
                        raise
            
            return [result_items]
        
        except Exception as e:
            logger.error(f"WordPress Node - Execute error: {str(e)}", exc_info=True)
            error_data = [NodeExecutionData(
                json_data={"error": f"Error in WordPress node: {str(e)}"},
                binary_data=None
            )]
            return [error_data]

    def _get_all_posts(self, item_index: int) -> Dict[str, Any]:
        """Get all posts from WordPress API (WordPress.com)"""
        try:
            # Get parameters
            return_all = self.get_node_parameter("returnAll", item_index, False)
            limit = self.get_node_parameter("limit", item_index, 50) if not return_all else 100
            
            # Build the API URL
            api_url = self.get_api_url("posts")
            
            # Get posts from WordPress.com API
            return self._get_wordpress_com_posts(api_url, limit)
        
        except Exception as e:
            logger.error(f"Error in _get_all_posts: {str(e)}", exc_info=True)
            raise
    
    def _get_wordpress_com_posts(self, api_url: str, limit: int) -> Dict[str, Any]:
        """Get posts from WordPress API using OAuth2"""
        try:
            # Set up headers with OAuth2 token
            headers = self.get_auth_headers()
            
            # WordPress.com uses "number" parameter, WP REST API uses "per_page"
            # Determine which parameter to use based on the URL
            if "public-api.wordpress.com" in api_url:
                params = {"number": limit}
            else:
                params = {"per_page": limit}
        
            # Make the request
            response = requests.get(
                api_url,
                params=params,
                headers=headers,
                timeout=30
            )

            response.raise_for_status()
            
            response_data = response.json()
            
            # Handle different response formats between WordPress.com and standard WordPress REST API
            if isinstance(response_data, list):
                # Standard WordPress REST API returns a list of posts directly
                posts_data = response_data
                total_found = int(response.headers.get('X-WP-Total', len(posts_data)))
            else:
                # WordPress.com API returns an object with a "posts" property
                posts_data = response_data.get("posts", [])
                total_found = response_data.get("found", 0)
            
            return {
                "posts": posts_data,
                "count": len(posts_data),
                "total_found": total_found,
                "url": api_url
            }
        
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise Exception("WordPress OAuth2 authentication failed - token may be expired")
            else:
                raise Exception(f"WordPress API HTTP Error {e.response.status_code}: {str(e)}")
        except Exception as e:
            logger.error(f"WordPress API request failed: {str(e)}")
            raise

    def wordpress_api_request(self, method: str, endpoint: str, body: Dict[str, Any] = None, query: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a request to the WordPress API using OAuth2"""
        try:
            # Get OAuth2 access token and create headers
            headers = self.get_auth_headers()
            
            # Make the request
            if method.upper() == 'GET':
                response = requests.get(endpoint, params=query, headers=headers, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(endpoint, params=query, json=body, headers=headers, timeout=30)
            elif method.upper() == 'PUT':
                response = requests.put(endpoint, params=query, json=body, headers=headers, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(endpoint, params=query, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle errors
            response.raise_for_status()
            
            # Return the response data
            if response.content:
                return response.json()
            else:
                return {"success": True}
                
        except requests.exceptions.HTTPError as e:
            error_msg = str(e)
            try:
                if hasattr(e, 'response') and e.response:
                    try:
                        error_data = e.response.json()
                        error_msg = f"WordPress API Error: {error_data.get('message', error_data.get('error', 'Unknown error'))}"
                    except:
                        error_msg = f"WordPress API Error: {e.response.text}"
                
                # Handle auth errors specifically
                if e.response.status_code == 401:
                    error_msg = "WordPress API authentication failed. Your token may be expired - please reauthorize this credential."
            except:
                pass
            logger.error(f"WordPress API request failed: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"WordPress API request error: {str(e)}")
            raise ValueError(f"WordPress API request failed: {str(e)}")

    def _get_post(self, item_index: int) -> Dict[str, Any]:
        """Get a single post by ID"""
        try:
            # Get the post ID and strip any leading = character
            post_id = self.get_node_parameter("postId", item_index)
            if post_id and isinstance(post_id, str):
                # Clean up the post ID
                if post_id.startswith('='):
                    post_id = post_id[1:]
                # Remove any whitespace
                post_id = post_id.strip()
    
            if not post_id:
                raise ValueError("Post ID is required for get operation. Please provide a valid post ID.")
            
            # Check if post_id is numeric
            try:
                int(post_id)
            except ValueError:
                raise ValueError(f"Invalid Post ID: '{post_id}'. Post ID must be a number.")
        
            # Build the API URL
            api_url = f"{self.get_api_url('posts')}/{post_id}"
            
            # Make the request
            return self.wordpress_api_request("GET", api_url)
        
        except Exception as e:
            logger.error(f"Error in _get_post: {str(e)}", exc_info=True)
            raise

    def _create_post(self, item_index: int) -> Dict[str, Any]:
        """Create a new post with proper expression evaluation"""
        try:
            # Get required parameters
            title = self._process_value_recursively(
                self.get_node_parameter("title", item_index),
                item_index
            )
            
            # Build post body
            body = {
                "title": title,  # WordPress expects a string, not an object
                "status": "draft"  # Default status
            }
            
            # Get optional parameters
            additional_fields = self.get_node_parameter("additionalFields", item_index, {})
            
            # Add additional fields to body with expression evaluation
            if additional_fields:
                if "authorId" in additional_fields:
                    body["author"] = self._process_value_recursively(additional_fields["authorId"], item_index)
                if "content" in additional_fields:
                    content = self._process_value_recursively(additional_fields["content"], item_index)
                    body["content"] = content  # WordPress expects a string
                if "slug" in additional_fields:
                    body["slug"] = self._process_value_recursively(additional_fields["slug"], item_index)
                if "status" in additional_fields:
                    body["status"] = self._process_value_recursively(additional_fields["status"], item_index)

            # Build the API URL
            api_url = self.get_api_url("posts")
            
            # Make the request
            result = self.wordpress_api_request("POST", api_url, body=body)
            
            # Return serialized result
            return deep_serialize(result)
    
        except Exception as e:
            logger.error(f"Error in _create_post: {str(e)}", exc_info=True)
            raise

    def _process_value_recursively(self, value, item_index):
        """Process a value recursively, evaluating expressions at any level"""
        # Handle strings with expressions
        if isinstance(value, str) and "{{" in value:
            processed = self._process_custom_expression(value, item_index)
            return processed
    
        # Handle lists - process each item recursively
        elif isinstance(value, list):
            return [self._process_value_recursively(item, item_index) for item in value]
    
        # Handle dictionaries - process each value recursively
        elif isinstance(value, dict):
            result = {}
            for k, v in value.items():
                result[k] = self._process_value_recursively(v, item_index)
            return result
    
        # Return other types unchanged
        else:
            return value
    
    def _process_custom_expression(self, expression_value, item_index):
        """Process expression in a custom string value not directly from parameters"""
        if not isinstance(expression_value, str) or "{{" not in expression_value:
            return expression_value
            
        # Use the base node's evaluation method
        options = GetNodeParameterOptions()
        return self._evaluate_expressions(
            expression_value,
            item_index,
            "custom_expression",  # Parameter name (for error context)
            options
        )

    # POST METHODS (add these methods)
    def _update_post(self, item_index: int) -> Dict[str, Any]:
        """Update an existing post"""
        try:
            # Get the post ID
            post_id = self._process_value_recursively(
                self.get_node_parameter("postId", item_index),
                item_index
            )
            
            if not post_id:
                raise ValueError("Post ID is required for update operation")
            
            # Get update fields
            update_fields = self.get_node_parameter("updateFields", item_index, {})
            
            # Build request body
            body = {}
            
            # Process update fields with expression evaluation
            if "title" in update_fields:
                body["title"] = self._process_value_recursively(update_fields["title"], item_index)
            if "authorId" in update_fields:
                body["author"] = self._process_value_recursively(update_fields["authorId"], item_index)
            if "content" in update_fields:
                body["content"] = self._process_value_recursively(update_fields["content"], item_index)
            if "slug" in update_fields:
                body["slug"] = self._process_value_recursively(update_fields["slug"], item_index)
            if "status" in update_fields:
                body["status"] = self._process_value_recursively(update_fields["status"], item_index)
            
            # Build API URL
            api_url = f"{self.get_api_url('posts')}/{post_id}"
            
            # Make request
            result = self.wordpress_api_request("POST", api_url, body=body)
            
            # Return serialized result
            return deep_serialize(result)
    
        except Exception as e:
            logger.error(f"Error in _update_post: {str(e)}", exc_info=True)
            raise

    def _delete_post(self, item_index: int) -> Dict[str, Any]:
        """Delete a post"""
        try:
            # Get the post ID with detailed debugging
            raw_post_id = self.get_node_parameter("postId", item_index)
            logger.info(f"DELETE POST DEBUG - Raw postId parameter: {raw_post_id}, type: {type(raw_post_id)}")
            
            # Debug current input data
            input_data = self.get_input_data()
            if input_data and item_index < len(input_data):
                current_item = input_data[item_index].json_data
            
            # Process the value
            post_id = self._process_value_recursively(raw_post_id, item_index)

            if not post_id:
                raise ValueError("Post ID is required for delete operation")
            
            # Build API URL
            api_url = f"{self.get_api_url('posts')}/{post_id}"
            
            # Query parameters
            query = {}
            
            # Check for force delete option
            options = self.get_node_parameter("options", item_index, {})
            if options.get("force", False):
                query["force"] = True
            
            # Make request
            result = self.wordpress_api_request("DELETE", api_url, query=query)
            
            # Return result
            return deep_serialize(result)
    
        except Exception as e:
            logger.error(f"Error in _delete_post: {str(e)}", exc_info=True)
            raise

    # PAGE METHODS
    def _get_all_pages(self, item_index: int) -> Dict[str, Any]:
        """Get all pages"""
        try:
            # Get parameters
            return_all = self.get_node_parameter("returnAll", item_index, False)
            limit = self.get_node_parameter("limit", item_index, 50) if not return_all else 100
            
            # Build query parameters
            query = {}
            options = self.get_node_parameter("options", item_index, {})
            
            # Process options
            if "context" in options:
                query["context"] = self._process_value_recursively(options["context"], item_index)
            if "orderBy" in options:
                query["orderby"] = self._process_value_recursively(options["orderBy"], item_index)
            if "order" in options:
                query["order"] = self._process_value_recursively(options["order"], item_index)
            if "search" in options:
                query["search"] = self._process_value_recursively(options["search"], item_index)
            if "after" in options:
                query["after"] = self._process_value_recursively(options["after"], item_index)
            if "author" in options:
                query["author"] = self._process_value_recursively(options["author"], item_index)
            if "parent" in options:
                query["parent"] = self._process_value_recursively(options["parent"], item_index)
            if "status" in options:
                query["status"] = self._process_value_recursively(options["status"], item_index)
            
            # Add pagination parameters
            if not return_all:
                query["per_page"] = limit
                
            # Build API URL
            api_url = self.get_api_url("pages")
            
            # Make request
            if return_all:
                # TODO: Implement pagination for all results
                result = self._get_all_items_with_pagination(api_url, query)
            else:
                result = self.wordpress_api_request("GET", api_url, query=query)
                
            # Return result as collection
            return {
                "pages": result if isinstance(result, list) else [],
                "count": len(result) if isinstance(result, list) else 0
            }
    
        except Exception as e:
            logger.error(f"Error in _get_all_pages: {str(e)}", exc_info=True)
            raise

    def _get_page(self, item_index: int) -> Dict[str, Any]:
        """Get a single page by ID"""
        try:
            # Get the page ID
            page_id = self._process_value_recursively(
                self.get_node_parameter("pageId", item_index),
                item_index
            )
            
            if not page_id:
                raise ValueError("Page ID is required for get operation")
            
            # Build query parameters
            query = {}
            options = self.get_node_parameter("options", item_index, {})
            
            # Process options
            if "context" in options:
                query["context"] = self._process_value_recursively(options["context"], item_index)
            if "password" in options:
                query["password"] = self._process_value_recursively(options["password"], item_index)
                
            # Build API URL
            api_url = f"{self.get_api_url('pages')}/{page_id}"
            
            # Make request
            result = self.wordpress_api_request("GET", api_url, query=query)
            
            # Return result
            return deep_serialize(result)
    
        except Exception as e:
            logger.error(f"Error in _get_page: {str(e)}", exc_info=True)
            raise

    def _create_page(self, item_index: int) -> Dict[str, Any]:
        """Create a new page"""
        try:
            # Get required parameters
            title = self._process_value_recursively(
                self.get_node_parameter("title", item_index),
                item_index
            )
            
            # Build page body
            body = {
                "title": title
            }
            
            # Get optional parameters
            additional_fields = self.get_node_parameter("additionalFields", item_index, {})
            
            # Add additional fields with expression evaluation
            if additional_fields:
                if "authorId" in additional_fields:
                    body["author"] = self._process_value_recursively(additional_fields["authorId"], item_index)
                if "content" in additional_fields:
                    body["content"] = self._process_value_recursively(additional_fields["content"], item_index)
                if "slug" in additional_fields:
                    body["slug"] = self._process_value_recursively(additional_fields["slug"], item_index)
                if "status" in additional_fields:
                    body["status"] = self._process_value_recursively(additional_fields["status"], item_index)
                
                # Page-specific fields
                if "parent" in additional_fields:
                    body["parent"] = self._process_value_recursively(additional_fields["parent"], item_index)
                if "menuOrder" in additional_fields:
                    body["menu_order"] = self._process_value_recursively(additional_fields["menuOrder"], item_index)
            
            # Build API URL
            api_url = self.get_api_url("pages")
            
            # Make request
            result = self.wordpress_api_request("POST", api_url, body=body)
            
            # Return serialized result
            return deep_serialize(result)
    
        except Exception as e:
            logger.error(f"Error in _create_page: {str(e)}", exc_info=True)
            raise

    def _update_page(self, item_index: int) -> Dict[str, Any]:
        """Update an existing page"""
        try:
            # Get the page ID
            page_id = self._process_value_recursively(
                self.get_node_parameter("pageId", item_index),
                item_index
            )
            
            if not page_id:
                raise ValueError("Page ID is required for update operation")
            
            # Get update fields
            update_fields = self.get_node_parameter("updateFields", item_index, {})
            
            # Build request body
            body = {}
            
            # Process update fields with expression evaluation
            if "title" in update_fields:
                body["title"] = self._process_value_recursively(update_fields["title"], item_index)
            if "authorId" in update_fields:
                body["author"] = self._process_value_recursively(update_fields["authorId"], item_index)
            if "content" in update_fields:
                body["content"] = self._process_value_recursively(update_fields["content"], item_index)
            if "slug" in update_fields:
                body["slug"] = self._process_value_recursively(update_fields["slug"], item_index)
            if "status" in update_fields:
                body["status"] = self._process_value_recursively(update_fields["status"], item_index)
                
            # Page-specific fields
            if "parent" in update_fields:
                body["parent"] = self._process_value_recursively(update_fields["parent"], item_index)
            if "menuOrder" in update_fields:
                body["menu_order"] = self._process_value_recursively(update_fields["menuOrder"], item_index)
            
            # Build API URL
            api_url = f"{self.get_api_url('pages')}/{page_id}"
            logger.info(f"Updating page with ID {page_id} at {api_url}")
            
            # Make request
            result = self.wordpress_api_request("POST", api_url, body=body)
            
            # Return serialized result
            return deep_serialize(result)
    
        except Exception as e:
            logger.error(f"Error in _update_page: {str(e)}", exc_info=True)
            raise

    def _delete_page(self, item_index: int) -> Dict[str, Any]:
        """Delete a page"""
        try:
            # Get the page ID
            page_id = self._process_value_recursively(
                self.get_node_parameter("pageId", item_index),
                item_index
            )
            
            if not page_id:
                raise ValueError("Page ID is required for delete operation")
            
            # Build API URL
            api_url = f"{self.get_api_url('pages')}/{page_id}"
            
            # Query parameters
            query = {}
            
            # Check for force delete option
            options = self.get_node_parameter("options", item_index, {})
            if options.get("force", False):
                query["force"] = True
            
            # Make request
            result = self.wordpress_api_request("DELETE", api_url, query=query)
            
            # Return result
            return deep_serialize(result)
    
        except Exception as e:
            logger.error(f"Error in _delete_page: {str(e)}", exc_info=True)
            raise

    # USER METHODS
    def _get_all_users(self, item_index: int) -> Dict[str, Any]:
        """Get all users"""
        try:
            # Get parameters
            return_all = self.get_node_parameter("returnAll", item_index, False)
            limit = self.get_node_parameter("limit", item_index, 50) if not return_all else 100
            
            # Build query parameters
            query = {}
            options = self.get_node_parameter("options", item_index, {})
            
            # Process options
            if "context" in options:
                query["context"] = self._process_value_recursively(options["context"], item_index)
            if "orderBy" in options:
                query["orderby"] = self._process_value_recursively(options["orderBy"], item_index)
            if "order" in options:
                query["order"] = self._process_value_recursively(options["order"], item_index)
            if "search" in options:
                query["search"] = self._process_value_recursively(options["search"], item_index)
            if "who" in options:
                query["who"] = self._process_value_recursively(options["who"], item_index)
        
            # Add pagination parameters
            if not return_all:
                query["per_page"] = limit
                
            # Build API URL
            api_url = self.get_api_url("users")
            
            # Make request
            if return_all:
                # TODO: Implement pagination for all results
                result = self._get_all_items_with_pagination(api_url, query)
            else:
                result = self.wordpress_api_request("GET", api_url, query=query)
                
            # Return result as collection
            return {
                "users": result if isinstance(result, list) else [],
                "count": len(result) if isinstance(result, list) else 0
            }
    
        except Exception as e:
            logger.error(f"Error in _get_all_users: {str(e)}", exc_info=True)
            raise

    def _get_user(self, item_index: int) -> Dict[str, Any]:
        """Get a single user by ID"""
        try:
            # Get the user ID
            user_id = self._process_value_recursively(
                self.get_node_parameter("userId", item_index),
                item_index
            )
            
            if not user_id:
                raise ValueError("User ID is required for get operation")
            
            # Build query parameters
            query = {}
            options = self.get_node_parameter("options", item_index, {})
            
            # Process options
            if "context" in options:
                query["context"] = self._process_value_recursively(options["context"], item_index)
            
            # Build API URL
            api_url = f"{self.get_api_url('users')}/{user_id}"

            # Make request
            result = self.wordpress_api_request("GET", api_url, query=query)
            
            # Return result
            return deep_serialize(result)
    
        except Exception as e:
            logger.error(f"Error in _get_user: {str(e)}", exc_info=True)
            raise

    def _create_user(self, item_index: int) -> Dict[str, Any]:
        """Create a new user"""
        try:
            # Get required parameters
            username = self._process_value_recursively(
                self.get_node_parameter("username", item_index),
                item_index
            )
            email = self._process_value_recursively(
                self.get_node_parameter("email", item_index),
                item_index
            )
            password = self._process_value_recursively(
                self.get_node_parameter("password", item_index),
                item_index
            )
            
            # Build user body
            body = {
                "username": username,
                "email": email,
                "password": password
            }
            
            # Get optional parameters
            additional_fields = self.get_node_parameter("userAdditionalFields", item_index, {})
            
            # Add additional fields with expression evaluation
            if additional_fields:
                if "firstName" in additional_fields:
                    body["first_name"] = self._process_value_recursively(additional_fields["firstName"], item_index)
                if "lastName" in additional_fields:
                    body["last_name"] = self._process_value_recursively(additional_fields["lastName"], item_index)
                if "nickname" in additional_fields:
                    body["nickname"] = self._process_value_recursively(additional_fields["nickname"], item_index)
                if "description" in additional_fields:
                    body["description"] = self._process_value_recursively(additional_fields["description"], item_index)
                if "roles" in additional_fields:
                    roles = self._process_value_recursively(additional_fields["roles"], item_index)
                    # Convert comma-separated roles to list if needed
                    if isinstance(roles, str):
                        body["roles"] = [role.strip() for role in roles.split(",")]
                    else:
                        body["roles"] = roles
        
            # Build API URL
            api_url = self.get_api_url("users")
            # Make request
            result = self.wordpress_api_request("POST", api_url, body=body)
            
            # Return serialized result
            return deep_serialize(result)
    
        except Exception as e:
            logger.error(f"Error in _create_user: {str(e)}", exc_info=True)
            raise

    def _update_user(self, item_index: int) -> Dict[str, Any]:
        """Update an existing user"""
        try:
            # Get the user ID
            user_id = self._process_value_recursively(
                self.get_node_parameter("userId", item_index),
                item_index
            )
            
            if not user_id:
                raise ValueError("User ID is required for update operation")
            
            # Get update fields
            update_fields = self.get_node_parameter("userUpdateFields", item_index, {})
            
            # Build request body
            body = {}
            
            # Process update fields with expression evaluation
            if "username" in update_fields:
                body["username"] = self._process_value_recursively(update_fields["username"], item_index)
            if "email" in update_fields:
                body["email"] = self._process_value_recursively(update_fields["email"], item_index)
            if "password" in update_fields:
                body["password"] = self._process_value_recursively(update_fields["password"], item_index)
            if "firstName" in update_fields:
                body["first_name"] = self._process_value_recursively(update_fields["firstName"], item_index)
            if "lastName" in update_fields:
                body["last_name"] = self._process_value_recursively(update_fields["lastName"], item_index)
            if "nickname" in update_fields:
                body["nickname"] = self._process_value_recursively(update_fields["nickname"], item_index)
            if "description" in update_fields:
                body["description"] = self._process_value_recursively(update_fields["description"], item_index)
            if "roles" in update_fields:
                roles = self._process_value_recursively(update_fields["roles"], item_index)
                # Convert comma-separated roles to list if needed
                if isinstance(roles, str):
                    body["roles"] = [role.strip() for role in roles.split(",")]
                else:
                    body["roles"] = roles
        
            # Build API URL
            api_url = f"{self.get_api_url('users')}/{user_id}"
            # Make request
            result = self.wordpress_api_request("POST", api_url, body=body)
            
            # Return serialized result
            return deep_serialize(result)
    
        except Exception as e:
            logger.error(f"Error in _update_user: {str(e)}", exc_info=True)
            raise

    def _delete_user(self, item_index: int) -> Dict[str, Any]:
        """Delete a user"""
        try:
            # Get the user ID
            user_id = self._process_value_recursively(
                self.get_node_parameter("userId", item_index),
                item_index
            )
            
            if not user_id:
                raise ValueError("User ID is required for delete operation")
            
            # Get the reassign parameter (required for deleting users)
            reassign = self.get_node_parameter("reassign", item_index)
            
            # Build API URL
            api_url = f"{self.get_api_url('users')}/{user_id}"

            # Query parameters
            query = {
                "force": True,
                "reassign": reassign
            }
            
            # Make request
            result = self.wordpress_api_request("DELETE", api_url, query=query)
            
            # Return result
            return deep_serialize(result)
    
        except Exception as e:
            logger.error(f"Error in _delete_user: {str(e)}", exc_info=True)
            raise

    def _get_all_items_with_pagination(self, endpoint: str, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get all items from WordPress API with pagination support"""
        all_items = []
        page = 1
        max_pages = 100  # Safety limit
        
        # Make a copy of the query parameters to avoid modifying the original
        paginated_query = query.copy()
        
        while page <= max_pages:
            # Update pagination parameters
            paginated_query["page"] = page
            paginated_query["per_page"] = 100  # Maximum allowed by WordPress API
            
            response = self.wordpress_api_request("GET", endpoint, query=paginated_query)
            
            # Check if we got any items
            if not response or not isinstance(response, list) or len(response) == 0:
                break
                
            # Add items to our collection
            all_items.extend(response)
            
            # Check if we've reached the last page
            if len(response) < 100:
                break
            
            # Move to next page
            page += 1
        
        return all_items

    def get_categories(self) -> List[Dict[str, Any]]:
        """Get all available categories from WordPress"""
        try:
            # Build API URL for categories
            api_url = self.get_api_url("categories")
            
            # Make request
            categories = self._get_all_items_with_pagination(api_url, {})
            
            # Format as options
            return [
                {"name": category.get("name", ""), "value": category.get("id", "")}
                for category in categories
            ]
        except Exception as e:
            logger.error(f"Error getting categories: {str(e)}", exc_info=True)
            return []
        
    def get_tags(self) -> List[Dict[str, Any]]:
        """Get all available tags from WordPress"""
        try:
            # Build API URL for tags
            api_url = self.get_api_url("tags")
            # Make request
            tags = self._get_all_items_with_pagination(api_url, {})
            
            # Format as options
            return [
                {"name": tag.get("name", ""), "value": tag.get("id", "")}
                for tag in tags
            ]
        except Exception as e:
            logger.error(f"Error getting tags: {str(e)}", exc_info=True)
            return []
        
    def get_authors(self) -> List[Dict[str, Any]]:
        """Get all available authors from WordPress"""
        try:
            # Build API URL for users with author role
            api_url = self.get_api_url("users")
            
            # Make request with 'who=authors' parameter
            authors = self._get_all_items_with_pagination(api_url, {"who": "authors"})
            
            # Format as options
            return [
                {"name": author.get("name", ""), "value": author.get("id", "")}
                for author in authors
            ]
        except Exception as e:
            logger.error(f"Error getting authors: {str(e)}", exc_info=True)
            return []

    # Method to get options
    def get_load_options(self, option_type: str) -> List[Dict[str, Any]]:
        """Get options for dynamic fields"""
        if option_type == "categories":
            return self.get_categories()
        elif option_type == "tags":
            return self.get_tags()
        elif option_type == "authors":
            return self.get_authors()
        else:
            return []
    
    def _prepare_for_json(self, value):
        """Prepare values for JSON serialization, especially datetime objects"""
        from datetime import datetime
        
        if isinstance(value, datetime):
            return value.isoformat()
        return value