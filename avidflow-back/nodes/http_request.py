import requests
import json
import base64
from typing import Dict, Any, List
from models import NodeExecutionData
from .base import BaseNode
import logging
import email
from email.mime.multipart import MIMEMultipart
from email.header import decode_header

logger = logging.getLogger(__name__)


class HttpRequestNode(BaseNode):
    """HTTP Request Node for making API calls"""
    
    type = "http_request"
    version = 1
    description = {
        "displayName": "HTTP Request",
        "name": "httpRequest",
        "group": ["input"],
        "version": 1,
        "description": "Makes HTTP requests to fetch or send data",
        "defaults": {
            "name": "HTTP Request"
        },
        "inputs": [
            {
                "name": "main",
                "type": "main",
                "required": False
            }
        ],
        "outputs": [
            {
                "name": "main",
                "type": "main",
                "required": False
            }
        ]
    }
    
    properties = {
        "parameters": [
            {
                "name": "url",
                "type": "string",
                "required": True,
                "default": "",
                "displayName": "URL",
                "description": "The URL to make the request to"
            },
            {
                "name": "method",
                "type": "options",
                "required": True,
                "default": "GET",
                "displayName": "Method",
                "description": "The request method to use",
                "options": [
                    {"name": "GET", "value": "GET"},
                    {"name": "POST", "value": "POST"},
                    {"name": "PUT", "value": "PUT"},
                    {"name": "DELETE", "value": "DELETE"},
                    {"name": "HEAD", "value": "HEAD"},
                    {"name": "PATCH", "value": "PATCH"}
                ]
            },
            {
                "name": "authentication",
                "type": "options",
                "default": "none",
                "displayName": "Authentication",
                "description": "The way to authenticate",
                "options": [
                    {"name": "None", "value": "none"},
                    {"name": "Basic Auth", "value": "basicAuth"},
                    {"name": "Header Auth", "value": "headerAuth"},
                    {"name": "OAuth2", "value": "oauth2"}
                ]
            },
            {
                "name": "headerParameters",
                "type": "collection",
                "default": {},
                "displayName": "Headers",
                "placeholder": "Add Header"
            },
            {
                "name": "queryParameters",
                "type": "collection",
                "default": {},
                "displayName": "Query Parameters",
                "placeholder": "Add Query Parameter"
            },
            {
                "name": "bodyContent",
                "type": "json",
                "default": {},
                "displayName": "Body",
                "description": "The request body"
            },
            {
                "name": "options",
                "type": "collection",
                "default": {},
                "displayName": "Options",
                "placeholder": "Add Option",
                "options": [
                    {
                        "name": "fullResponse",
                        "type": "boolean",
                        "default": False,
                        "displayName": "Full Response",
                        "description": "Return the full response data instead of only the body"
                    },
                    {
                        "name": "timeout",
                        "type": "number",
                        "default": 10000,
                        "displayName": "Timeout",
                        "description": "Request timeout in milliseconds"
                    },
                    {
                        "name": "allowUnauthorizedCerts",
                        "type": "boolean",
                        "default": False,
                        "displayName": "Allow Unauthorized Certificates",
                        "description": "Allow connections to sites with invalid certificates"
                    }
                ]
            }
        ],
        "credentials": [
            {
                "name": "httpBasicAuth",
                "required": True,
                "displayOptions": {
                    "show": {
                        "authentication": ["basicAuth"]
                    }
                }
            },
            {
                "name": "httpHeaderAuth", 
                "required": True,
                "displayOptions": {
                    "show": {
                        "authentication": ["headerAuth"]
                    }
                }
            },
            {
                "name": "oAuth2Api",
                "required": True,
                "displayOptions": {
                    "show": {
                        "authentication": ["oauth2"]
                    }
                }
            }
        ]
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute HTTP request and return the response"""
        result_items: List[NodeExecutionData] = []
        items = self.get_input_data()

        for i, item in enumerate(items):
            url = self.get_parameter("url", i)
            method = self.get_parameter("method", i, "GET")
            auth_type = self.get_parameter("authentication", i, None)
            headers = self.get_parameter("headerParameters", i, {})
            query_params = self.get_parameter("queryParameters", i, {})
            body = self.get_parameter("bodyContent", i, {})
            options = self.get_parameter("options", i, {})

            # Setup authentication
            auth = None
            if auth_type == "basicAuth":
                creds = self.get_credentials("httpBasicAuth")
                if creds:
                    auth = (creds.get("username", ""), creds.get("password", ""))
            elif auth_type == "headerAuth":
                creds = self.get_credentials("httpHeaderAuth")
                if creds:
                    headers[creds.get("name", "Authorization")] = creds.get("value", "")
            elif auth_type == "oauth2":
                creds = self.get_credentials("oAuth2Api")
                if creds:
                    # Implement OAuth2 logic - simplified for example
                    oauth_token_data = creds.get("oauthTokenData", {})
                    access_token = oauth_token_data.get("access_token", "")
                    headers["Authorization"] = f"Bearer {access_token}"

            # Request options
            timeout = options.get("timeout", 10000) / 1000  # Convert to seconds
            verify_ssl = not options.get("allowUnauthorizedCerts", False)

            try:
                # Setup request
                request_kwargs = {
                    "url": url,
                    "headers": headers,
                    "params": query_params,
                    "timeout": timeout,
                    "verify": verify_ssl,
                    "auth": auth,
                }

                if method != "GET" and body:
                    request_kwargs["json"] = body

                # Make the request
                response = requests.request(method, **request_kwargs)

                # Process response
                result = {
                    "statusCode": response.status_code,
                    "headers": dict(response.headers),
                }

                try:
                    result["body"] = response.json()
                except json.JSONDecodeError:
                    result["body"] = response.text

                output_item = NodeExecutionData(**{'json_data': result})
                result_items.append(output_item)

            except Exception as e:
                output_item = NodeExecutionData(**{
                    "json_data": {
                        "error": str(e),
                        "url": url,
                        "method": method
                    },
                    "binary_data": None
                })
                result_items.append(output_item)

        return [result_items]
