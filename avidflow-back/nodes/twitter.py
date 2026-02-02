import logging
import re
import base64
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests
from urllib.parse import urlencode, urlparse, parse_qs

from models import NodeExecutionData
from .base import BaseNode

logger = logging.getLogger(__name__)

class TwitterNode(BaseNode):
    """Twitter/X Node for interacting with Twitter/X API v2"""
    
    type = "twitter"
    version = 2
    
    description = {
        "displayName": "X (Formerly Twitter)",
        "name": "twitter",
        "icon": "file:x.svg",
        "group": ["output"],
        "version": 2,
        "description": "Post, like, and search tweets, send messages, search users, and add users to lists",
        "defaults": {
            "name": "X (Formerly Twitter)"
        },
        "inputs": [
            {
                "name": "main",
                "type": "main",
                "required": True
            }
        ],
        "outputs": [
            {
                "name": "main",
                "type": "main",
                "required": True
            }
        ]
    }
    
    properties = {
        "parameters": [
            {
                "name": "resource",
                "type": "options",
                "required": True,
                "displayName": "Resource",
                "description": "The Twitter/X resource to operate on",
                "default": "tweet",
                "options": [
                    {
                        "name": "Direct Message",
                        "value": "directMessage",
                        "description": "Send a direct message to a user"
                    },
                    {
                        "name": "List",
                        "value": "list",
                        "description": "Add a user to a list"
                    },
                    {
                        "name": "Tweet",
                        "value": "tweet",
                        "description": "Create, like, search, or delete a tweet"
                    },
                    {
                        "name": "User",
                        "value": "user",
                        "description": "Search users by username"
                    }
                ]
            },
            # TWEET OPERATIONS
            {
                "name": "operation",
                "type": "options",
                "displayName": "Operation",
                "description": "The operation to perform",
                "default": "create",
                "options": [
                    {
                        "name": "Create",
                        "value": "create",
                        "description": "Create a tweet"
                    },
                    {
                        "name": "Delete",
                        "value": "delete",
                        "description": "Delete a tweet"
                    },
                    {
                        "name": "Like",
                        "value": "like",
                        "description": "Like a tweet"
                    },
                    {
                        "name": "Retweet",
                        "value": "retweet",
                        "description": "Retweet a tweet"
                    },
                    {
                        "name": "Search",
                        "value": "search",
                        "description": "Search for tweets"
                    },
                ],
                "display_options": {
                    "show": {
                        "resource": ["tweet"]
                    }
                }
            },
            # Tweet text for creating tweets
            {
                "name": "text",
                "type": "string",
                "displayName": "Text",
                "description": "The text of the tweet",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["tweet"],
                        "operation": ["create"]
                    }
                }
            },
            # Tweet delete parameter
            {
                "name": "tweetDeleteId",
                "type": "resourceLocator",
                "displayName": "Tweet ID",
                "description": "ID of the tweet to delete",
                "default": { "mode": "id", "value": "" },
                "required": True,
                "modes": [
                    {
                        "displayName": "By ID",
                        "name": "id",
                        "type": "string"
                    },
                    {
                        "displayName": "By URL",
                        "name": "url",
                        "type": "string"
                    }
                ],
                "display_options": {
                    "show": {
                        "resource": ["tweet"],
                        "operation": ["delete"]
                    }
                }
            },
            # Tweet ID for like, retweet, get
            {
                "name": "tweetId",
                "type": "resourceLocator",
                "displayName": "Tweet ID",
                "description": "ID of the tweet",
                "default": { "mode": "id", "value": "" },
                "required": True,
                "modes": [
                    {
                        "displayName": "By ID",
                        "name": "id",
                        "type": "string"
                    },
                    {
                        "displayName": "By URL",
                        "name": "url",
                        "type": "string"
                    }
                ],
                "display_options": {
                    "show": {
                        "resource": ["tweet"],
                        "operation": ["like", "retweet"]
                    }
                }
            },
            # Tweet search parameters
            {
                "name": "searchText",
                "type": "string",
                "displayName": "Search Text",
                "description": "The text to search for",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["tweet"],
                        "operation": ["search"]
                    }
                }
            },
            {
                "name": "returnAll",
                "type": "boolean",
                "displayName": "Return All Results",
                "description": "Whether to return all results or just the first page",
                "default": False,
                "display_options": {
                    "show": {
                        "resource": ["tweet"],
                        "operation": ["search"]
                    }
                }
            },
            {
                "name": "limit",
                "type": "number",
                "displayName": "Limit",
                "description": "Max number of results to return",
                "default": 50,
                "typeOptions": {
                    "minValue": 1,
                    "maxValue": 100
                },
                "display_options": {
                    "show": {
                        "resource": ["tweet"],
                        "operation": ["search"],
                        "returnAll": [False]
                    }
                }
            },
            {
                "name": "additionalFields",
                "type": "collection",
                "displayName": "Additional Fields",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["tweet"],
                        "operation": ["create"]
                    }
                },
                "options": [
                    {
                        "name": "location",
                        "type": "string",
                        "displayName": "Location",
                        "description": "Place ID for location tagging"
                    },
                    {
                        "name": "attachments",
                        "type": "string",
                        "displayName": "Media IDs",
                        "description": "Media ID to attach to the tweet"
                    },
                    {
                        "name": "inQuoteToStatusId",
                        "type": "resourceLocator",
                        "displayName": "In Quote To Tweet",
                        "description": "The tweet being quoted",
                        "default": { "mode": "id", "value": "" },
                        "modes": [
                            {
                                "displayName": "By ID",
                                "name": "id",
                                "type": "string"
                            },
                            {
                                "displayName": "By URL",
                                "name": "url",
                                "type": "string"
                            }
                        ]
                    },
                    {
                        "name": "inReplyToStatusId",
                        "type": "resourceLocator",
                        "displayName": "In Reply To Tweet",
                        "description": "The tweet being replied to",
                        "default": { "mode": "id", "value": "" },
                        "modes": [
                            {
                                "displayName": "By ID",
                                "name": "id",
                                "type": "string"
                            },
                            {
                                "displayName": "By URL",
                                "name": "url",
                                "type": "string"
                            }
                        ]
                    }
                ]
            },
            {
                "name": "additionalFields",
                "type": "collection",
                "displayName": "Additional Fields",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["tweet"],
                        "operation": ["search"]
                    }
                },
                "options": [
                    {
                        "name": "sortOrder",
                        "type": "options",
                        "displayName": "Sort Order",
                        "options": [
                            {
                                "name": "Recency",
                                "value": "recency"
                            },
                            {
                                "name": "Relevancy",
                                "value": "relevancy"
                            }
                        ],
                        "default": "recency"
                    },
                    {
                        "name": "startTime",
                        "type": "dateTime",
                        "displayName": "Start Time"
                    },
                    {
                        "name": "endTime",
                        "type": "dateTime",
                        "displayName": "End Time"
                    },
                    {
                        "name": "tweetFieldsObject",
                        "type": "multiOptions",
                        "displayName": "Tweet Fields",
                        "options": [
                            {"name": "Attachments", "value": "attachments"},
                            {"name": "Author ID", "value": "author_id"},
                            {"name": "Created At", "value": "created_at"},
                            {"name": "Entities", "value": "entities"},
                            {"name": "Geo", "value": "geo"},
                            {"name": "ID", "value": "id"},
                            {"name": "In Reply To User ID", "value": "in_reply_to_user_id"},
                            {"name": "Language", "value": "lang"},
                            {"name": "Referenced Tweets", "value": "referenced_tweets"},
                            {"name": "Text", "value": "text"}
                        ]
                    }
                ]
            },
            
            # USER OPERATIONS
            {
                "name": "operation",
                "type": "options",
                "displayName": "Operation",
                "description": "The operation to perform",
                "default": "searchUser",
                "options": [
                    {
                        "name": "Search User",
                        "value": "searchUser",
                        "description": "Search for a user"
                    }
                ],
                "display_options": {
                    "show": {
                        "resource": ["user"]
                    }
                }
            },
            {
                "name": "me",
                "type": "boolean",
                "displayName": "Me",
                "description": "Return the authenticated user",
                "default": True,
                "display_options": {
                    "show": {
                        "resource": ["user"],
                        "operation": ["searchUser"]
                    }
                }
            },
            {
                "name": "user",
                "type": "resourceLocator",
                "displayName": "User",
                "description": "Username or ID of the user",
                "default": { "mode": "username", "value": "" },
                "modes": [
                    {
                        "displayName": "By Username",
                        "name": "username",
                        "type": "string"
                    },
                    {
                        "displayName": "By ID",
                        "name": "id",
                        "type": "string"
                    }
                ],
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["user"],
                        "operation": ["searchUser"],
                        "me": [False]
                    }
                }
            },
            
            # LIST OPERATIONS
            {
                "name": "operation",
                "type": "options",
                "displayName": "Operation",
                "description": "The operation to perform",
                "default": "add",
                "options": [
                    {
                        "name": "Add",
                        "value": "add",
                        "description": "Add a user to a list"
                    }
                ],
                "display_options": {
                    "show": {
                        "resource": ["list"]
                    }
                }
            },
            {
                "name": "user",
                "type": "resourceLocator",
                "displayName": "User",
                "description": "Username or ID of the user to add",
                "default": { "mode": "username", "value": "" },
                "modes": [
                    {
                        "displayName": "By Username",
                        "name": "username",
                        "type": "string"
                    },
                    {
                        "displayName": "By ID",
                        "name": "id",
                        "type": "string"
                    }
                ],
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["list"],
                        "operation": ["add"]
                    }
                }
            },
            {
                "name": "list",
                "type": "resourceLocator",
                "displayName": "List",
                "description": "ID or URL of the list",
                "default": { "mode": "id", "value": "" },
                "modes": [
                    {
                        "displayName": "By ID",
                        "name": "id",
                        "type": "string"
                    },
                    {
                        "displayName": "By URL",
                        "name": "url",
                        "type": "string"
                    }
                ],
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["list"],
                        "operation": ["add"]
                    }
                }
            },
            
            # DIRECT MESSAGE OPERATIONS
            {
                "name": "operation",
                "type": "options",
                "displayName": "Operation",
                "description": "The operation to perform",
                "default": "create",
                "options": [
                    {
                        "name": "Create",
                        "value": "create",
                        "description": "Send a direct message"
                    }
                ],
                "display_options": {
                    "show": {
                        "resource": ["directMessage"]
                    }
                }
            },
            {
                "name": "user",
                "type": "resourceLocator",
                "displayName": "User",
                "description": "Username or ID of the recipient",
                "default": { "mode": "username", "value": "" },
                "modes": [
                    {
                        "displayName": "By Username",
                        "name": "username",
                        "type": "string"
                    },
                    {
                        "displayName": "By ID",
                        "name": "id",
                        "type": "string"
                    }
                ],
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["directMessage"],
                        "operation": ["create"]
                    }
                }
            },
            {
                "name": "text",
                "type": "string",
                "displayName": "Text",
                "description": "Content of the direct message",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["directMessage"],
                        "operation": ["create"]
                    }
                }
            },
            {
                "name": "additionalFields",
                "type": "collection",
                "displayName": "Additional Fields",
                "placeholder": "Add Field",
                "default": {},
                "display_options": {
                    "show": {
                        "resource": ["directMessage"],
                        "operation": ["create"]
                    }
                },
                "options": [
                    {
                        "name": "attachments",
                        "type": "string",
                        "displayName": "Media ID",
                        "description": "Media ID to attach to the message"
                    }
                ]
            }
        ],
        "credentials": [
            {
                "name": "twitterOAuth2Api",
                "required": True
            }
        ]
    }
    
    icon = "fa:twitter"
    color = "#1DA1F2"
    
    def _extract_id_from_url(self, url: str) -> str:
        """Extract tweet ID from a Twitter URL"""
        try:
            # Extract the last path component which should be the ID
            match = re.search(r'/status/(\d+)', url)
            if match:
                return match.group(1)
            
            # Try direct URL parsing
            parsed = urlparse(url)
            path_parts = parsed.path.split('/')
            if 'status' in path_parts:
                idx = path_parts.index('status')
                if idx + 1 < len(path_parts):
                    return path_parts[idx + 1]
                    
            # If we can't find the ID, raise an error
            raise ValueError(f"Could not extract ID from URL: {url}")
        except Exception as e:
            logger.error(f"Error extracting ID from URL: {str(e)}")
            raise ValueError(f"Invalid Twitter URL: {url}")
    
    def _extract_list_id_from_url(self, url: str) -> str:
        """Extract list ID from a Twitter URL"""
        try:
            match = re.search(r'/lists/(\d+)', url)
            if match:
                return match.group(1)
                
            # Parse URL
            parsed = urlparse(url)
            path_parts = parsed.path.split('/')
            
            # Try to find the ID in path or query string
            if 'lists' in path_parts:
                idx = path_parts.index('lists')
                if idx + 1 < len(path_parts):
                    return path_parts[idx + 1]
                    
            # Look for ID in query params
            query_params = parse_qs(parsed.query)
            if 'list_id' in query_params:
                return query_params['list_id'][0]
                
            raise ValueError(f"Could not extract list ID from URL: {url}")
        except Exception as e:
            logger.error(f"Error extracting list ID from URL: {str(e)}")
            raise ValueError(f"Invalid Twitter list URL: {url}")
    
    def return_id(self, resource_locator: Dict[str, Any]) -> str:
        """
        Extract ID from a resource locator
        
        Args:
            resource_locator: Object with 'mode' and 'value' properties
            
        Returns:
            The ID extracted from the resource locator
        """
        mode = resource_locator.get('mode')
        value = resource_locator.get('value')
        
        if mode == 'id':
            return str(value)
        elif mode == 'url':
            return self._extract_id_from_url(value)
        else:
            raise ValueError(f"Invalid resource locator mode: {mode}")
    
    def return_id_from_username(self, username_locator: Dict[str, Any]) -> str:
        """
        Get user ID from username
        
        Args:
            username_locator: Object with username details
            
        Returns:
            The user ID
        """
        mode = username_locator.get('mode')
        value = username_locator.get('value')
        
        if mode == 'id':
            return str(value)
        elif mode == 'username':
            # Strip @ if present
            username = value.replace('@', '') if value.startswith('@') else value
            # Look up the ID from the username
            response = self.twitter_api_request('GET', f'/users/by/username/{username}')
            return response.get('data', {}).get('id')
        else:
            raise ValueError(f"Invalid username locator mode: {mode}")
        
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
            # Use requests instead of aiohttp for synchronous operation
            
            response = requests.post(
                data["accessTokenUrl"],
                data=urlencode(token_data),
                headers=headers,
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
        Get a valid access token for Twitter API from the credentials
        """
        try:
            # Get credentials
            credentials = self.get_credentials("twitterOAuth2Api")
            if not credentials:
                raise ValueError("Twitter OAuth2 credentials not found")

            if not self.has_access_token(credentials):
                raise ValueError("Twitter OAuth2 access token not found")

            if self._is_token_expired(credentials['oauthTokenData']):
                credentials = self.refresh_token(credentials)

            return credentials['oauthTokenData']['access_token']
            
        except Exception as e:
            logger.error(f"Error getting Twitter access token: {str(e)}")
            raise ValueError(f"Failed to get Twitter access token: {str(e)}")
    
    def twitter_api_request(self, method: str, endpoint: str, body: Dict[str, Any] = None, query: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Make a request to the Twitter API v2
        
        Args:
            method: HTTP method (GET, POST, DELETE)
            endpoint: API endpoint path (without base URL)
            body: Request body for POST requests
            query: Query parameters
            
        Returns:
            API response as dictionary
        """
        # Get access token (will automatically handle token acquisition/refresh)
        access_token = self._get_access_token()
        
        # Set up request
        base_url = "https://api.twitter.com/2"
        url = f"{base_url}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            # Make the request
            if method == 'GET':
                response = requests.get(url, params=query, headers=headers)
            elif method == 'POST':
                response = requests.post(url, params=query, json=body, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, params=query, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, params=query, json=body, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            # Handle errors
            response.raise_for_status()
            
            # Return the response data
            return response.json()
            
        except requests.RequestException as e:
            error_msg = str(e)
            try:
                if hasattr(e, 'response') and e.response:
                    error_data = e.response.json()
                    error_msg = f"Twitter API Error: {error_data.get('errors', [{'message': 'Unknown error'}])[0].get('message')}"
                    
                    # Handle auth errors specifically
                    if e.response.status_code == 401:
                        # Token might be expired, invalidate it
                        credentials = self.get_credentials("twitterOAuth2Api")
                        if credentials:
                            credentials["accessToken"] = None
                            credentials["accessTokenExpiry"] = 0
                        error_msg += " - Will retry with new token on next request."
            except:
                pass
            logger.error(f"Twitter API request failed: {error_msg}")
            raise ValueError(error_msg)
    
    def twitter_api_request_all_items(self, property_name: str, method: str, endpoint: str, body: Dict[str, Any] = None, query: Dict[str, Any] = None) -> List[Any]:
        """
        Make paginated requests to the Twitter API v2
        
        Args:
            property_name: The name of the property containing the items
            method: HTTP method
            endpoint: API endpoint
            body: Request body
            query: Query parameters
            
        Returns:
            All items from all pages
        """
        query = query or {}
        body = body or {}
        
        all_items = []
        next_token = None
        
        while True:
            # Add pagination token if we have one
            if next_token:
                query['pagination_token'] = next_token
            
            # Make the request
            response_data = self.twitter_api_request(method, endpoint, body, query)
            
            # Add items to our result
            if property_name in response_data:
                all_items.extend(response_data[property_name])
            
            # Check if we have a next page
            meta = response_data.get('meta', {})
            next_token = meta.get('next_token')
            
            # If no next token or we've reached the desired count, break
            if not next_token:
                break
        
        return all_items
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Twitter node operations"""
        result_items: List[NodeExecutionData] = []
        
        try:
            # Get input items
            items = self.get_input_data()
            
            # Process each input item
            for i, item in enumerate(items):
                try:
                    # Get resource and operation for each item
                    resource = self.get_node_parameter('resource', i)
                    operation = self.get_node_parameter('operation', i)
                    
                    if resource == 'user':
                        if operation == 'searchUser':
                            me = self.get_node_parameter('me', i, False)
                            
                            if me:
                                response_data = self.twitter_api_request('GET', '/users/me', {})
                            else:
                                user_rlc = self.get_node_parameter('user', i)
                                
                                if user_rlc.get('mode') == 'username':
                                    username = user_rlc.get('value')
                                    username = username.replace('@', '') if '@' in username else username
                                    response_data = self.twitter_api_request('GET', f'/users/by/username/{username}')
                                else:  # id mode
                                    user_id = user_rlc.get('value')
                                    response_data = self.twitter_api_request('GET', f'/users/{user_id}')
                        
                        result_items.append(NodeExecutionData(json_data=response_data, binary_data=None))
                        
                    elif resource == 'tweet':
                        if operation == 'search':
                            search_text = self.get_node_parameter('searchText', i, '')
                            return_all = self.get_node_parameter('returnAll', i, False)
                            additional_fields = self.get_node_parameter('additionalFields', i, {})
                            
                            # Setup query params
                            query = {
                                'query': search_text,
                            }
                            
                            # Add additional parameters
                            if 'endTime' in additional_fields:
                                query['end_time'] = datetime.fromisoformat(additional_fields['endTime']).isoformat()
                            
                            if 'startTime' in additional_fields:
                                query['start_time'] = datetime.fromisoformat(additional_fields['startTime']).isoformat()
                            
                            if 'sortOrder' in additional_fields:
                                query['sort_order'] = additional_fields['sortOrder']
                            
                            if 'tweetFieldsObject' in additional_fields and additional_fields['tweetFieldsObject']:
                                query['tweet.fields'] = ','.join(additional_fields['tweetFieldsObject'])
                            
                            if return_all:
                                response_data = self.twitter_api_request_all_items(
                                    'data',
                                    'GET',
                                    '/tweets/search/recent',
                                    query=query
                                )
                            else:
                                limit = self.get_node_parameter('limit', i, 50)
                                query['max_results'] = limit
                                response = self.twitter_api_request('GET', '/tweets/search/recent', query=query)
                                response_data = response.get('data', [])
                            
                            for tweet in response_data:
                                result_items.append(NodeExecutionData(json_data=tweet, binary_data=None))
                        
                        elif operation == 'create':
                            text = self.get_node_parameter('text', i, '')
                            additional_fields = self.get_node_parameter('additionalFields', i, {})
                            
                            body = {
                                'text': text,
                            }
                            
                            # Add optional parameters
                            if 'location' in additional_fields:
                                body['geo'] = {'place_id': additional_fields['location']}
                            
                            if 'attachments' in additional_fields:
                                body['media'] = {'media_ids': [additional_fields['attachments']]}
                            
                            if 'inQuoteToStatusId' in additional_fields:
                                quote_id = self.return_id(additional_fields['inQuoteToStatusId'])
                                body['quote_tweet_id'] = quote_id
                            
                            if 'inReplyToStatusId' in additional_fields:
                                reply_id = self.return_id(additional_fields['inReplyToStatusId'])
                                body['reply'] = {'in_reply_to_tweet_id': reply_id}
                            
                            response_data = self.twitter_api_request('POST', '/tweets', body)
                            result_items.append(NodeExecutionData(json_data=response_data, binary_data=None))
                            
                        elif operation == 'delete':
                            tweet_rlc = self.get_node_parameter('tweetDeleteId', i)
                            tweet_id = self.return_id(tweet_rlc)
                            
                            response_data = self.twitter_api_request('DELETE', f'/tweets/{tweet_id}')
                            result_items.append(NodeExecutionData(json_data=response_data, binary_data=None))
                            
                        elif operation == 'like':
                            tweet_rlc = self.get_node_parameter('tweetId', i)
                            tweet_id = self.return_id(tweet_rlc)
                            
                            # Get current user
                            user = self.twitter_api_request('GET', '/users/me')
                            user_id = user.get('data', {}).get('id')
                            
                            body = {
                                'tweet_id': tweet_id
                            }
                            
                            response_data = self.twitter_api_request('POST', f'/users/{user_id}/likes', body)
                            result_items.append(NodeExecutionData(json_data=response_data, binary_data=None))
                            
                        elif operation == 'retweet':
                            tweet_rlc = self.get_node_parameter('tweetId', i)
                            tweet_id = self.return_id(tweet_rlc)
                            
                            # Get current user
                            user = self.twitter_api_request('GET', '/users/me')
                            user_id = user.get('data', {}).get('id')
                            
                            body = {
                                'tweet_id': tweet_id
                            }
                            
                            response_data = self.twitter_api_request('POST', f'/users/{user_id}/retweets', body)
                            result_items.append(NodeExecutionData(json_data=response_data, binary_data=None))
                            
                    elif resource == 'list':
                        if operation == 'add':
                            user_rlc = self.get_node_parameter('user', i)
                            list_rlc = self.get_node_parameter('list', i)
                            
                            # Get user ID from username if needed
                            user_id = self.return_id_from_username(user_rlc)
                            
                            # Get list ID
                            if list_rlc.get('mode') == 'url':
                                list_id = self._extract_list_id_from_url(list_rlc.get('value'))
                            else:
                                list_id = list_rlc.get('value')
                            
                            body = {
                                'user_id': user_id
                            }
                            
                            response_data = self.twitter_api_request('POST', f'/lists/{list_id}/members', body)
                            result_items.append(NodeExecutionData(json_data=response_data, binary_data=None))
                            
                    elif resource == 'directMessage':
                        if operation == 'create':
                            user_rlc = self.get_node_parameter('user', i)
                            text = self.get_node_parameter('text', i, '')
                            additional_fields = self.get_node_parameter('additionalFields', i, {})
                            
                            # Get user ID from username if needed
                            user_id = self.return_id_from_username(user_rlc)
                            
                            body = {
                                'text': text
                            }
                            
                            if 'attachments' in additional_fields:
                                body['attachments'] = [{
                                    'media_id': additional_fields['attachments']
                                }]
                            
                            response_data = self.twitter_api_request(
                                'POST',
                                f'/dm_conversations/with/{user_id}/messages',
                                body
                            )
                            result_items.append(NodeExecutionData(json_data=response_data, binary_data=None))
                
                except Exception as e:
                    error_data = {
                        'error': str(e),
                        'resource': resource if 'resource' in locals() else 'unknown',
                        'operation': operation if 'operation' in locals() else 'unknown',
                        'item_index': i
                    }
                    result_items.append(NodeExecutionData(json_data=error_data, binary_data=None))
        
            return [result_items]
            
        except Exception as e:
            import traceback
            error_data = {
                'error': str(e),
                'traceback': traceback.format_exc()
            }
            return [[NodeExecutionData(json_data=error_data, binary_data=None)]]
