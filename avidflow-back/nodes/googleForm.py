import requests
import json
import logging
import time
import base64
from urllib.parse import urlencode
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType
from utils.expression_evaluator import ExpressionEngine

logger = logging.getLogger(__name__)


class GoogleFormNode(BaseNode):
    """
    Google Forms node for managing forms and responses
    """
    
    type = "googleForm"
    version = 1.0
    
    description = {
        "displayName": "Google Forms",
        "name": "googleForm",
        "icon": "file:googleForms.svg",
        "group": ["input", "output"],
        "description": "Create and manage Google Forms and collect responses",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
        "credentials": [
            {
                "name": "googleFormApi",
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
                "options": [
                    {"name": "Form", "value": "form"},
                    {"name": "Question", "value": "question"},
                    {"name": "Response", "value": "response"}
                ],
                "default": "form",
                "description": "The resource to operate on"
            },
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Create", "value": "create"},
                    {"name": "Get", "value": "get"},
                    {"name": "Update", "value": "update"},
                    {"name": "Delete", "value": "delete"},
                    {"name": "List", "value": "list"}
                ],
                "default": "get",
                "description": "The operation to perform"
            },
            # Form operations
            {
                "name": "formId",
                "type": NodeParameterType.STRING,
                "display_name": "Form ID",
                "default": "",
                "description": "The ID of the form",
                "displayOptions": {
                    "show": {
                        "resource": ["form", "question", "response"],
                        "operation": ["get", "update", "delete"]
                    }
                }
            },
            {
                "name": "formTitle",
                "type": NodeParameterType.STRING,
                "display_name": "Form Title",
                "default": "",
                "description": "Title of the form",
                "displayOptions": {
                    "show": {
                        "resource": ["form"],
                        "operation": ["create", "update"]
                    }
                }
            },
            {
                "name": "formDescription",
                "type": NodeParameterType.STRING,
                "display_name": "Form Description",
                "default": "",
                "description": "Description of the form",
                "displayOptions": {
                    "show": {
                        "resource": ["form"],
                        "operation": ["create", "update"]
                    }
                }
            },
            # Question operations
            {
                "name": "questionType",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Question Type",
                "options": [
                    {"name": "Text", "value": "TEXT"},
                    {"name": "Paragraph Text", "value": "PARAGRAPH_TEXT"},
                    {"name": "Multiple Choice", "value": "MULTIPLE_CHOICE"},
                    {"name": "Checkboxes", "value": "CHECKBOXES"},
                    {"name": "Dropdown", "value": "DROPDOWN"},
                    {"name": "Linear Scale", "value": "LINEAR_SCALE"},
                    {"name": "Date", "value": "DATE"},
                    {"name": "Time", "value": "TIME"}
                ],
                "default": "TEXT",
                "description": "Type of question to add",
                "displayOptions": {
                    "show": {
                        "resource": ["question"],
                        "operation": ["create", "update"]
                    }
                }
            },
            {
                "name": "questionTitle",
                "type": NodeParameterType.STRING,
                "display_name": "Question Title",
                "default": "",
                "description": "Title of the question",
                "displayOptions": {
                    "show": {
                        "resource": ["question"],
                        "operation": ["create", "update"]
                    }
                }
            },
            {
                "name": "questionRequired",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Required",
                "default": False,
                "description": "Whether the question is required",
                "displayOptions": {
                    "show": {
                        "resource": ["question"],
                        "operation": ["create", "update"]
                    }
                }
            },
            {
                "name": "questionChoices",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Choices",
                "default": {},
                "description": "Options for multiple choice, checkbox, or dropdown questions",
                "placeholder": "Add choice",
                "typeOptions": {
                    "multipleValues": True
                },
                "options": [
                    {
                        "name": "value",
                        "type": NodeParameterType.STRING,
                        "display_name": "Choice",
                        "default": "",
                        "description": "Option value"
                    }
                ],
                "displayOptions": {
                    "show": {
                        "resource": ["question"],
                        "operation": ["create", "update"],
                        "questionType": ["MULTIPLE_CHOICE", "CHECKBOXES", "DROPDOWN"]
                    }
                }
            },
            # Response operations
            {
                "name": "includeResponses",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Include Responses",
                "default": True,
                "description": "Whether to include response values",
                "displayOptions": {
                    "show": {
                        "resource": ["response"],
                        "operation": ["get", "list"]
                    }
                }
            },
            {
                "name": "returnAll",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Return All",
                "default": False,
                "description": "Whether to return all results or only up to a given limit",
                "displayOptions": {
                    "show": {
                        "resource": ["form", "response"],
                        "operation": ["list"]
                    }
                }
            },
            {
                "name": "limit",
                "type": NodeParameterType.NUMBER,
                "display_name": "Limit",
                "default": 100,
                "description": "Max number of results to return",
                "typeOptions": {
                    "minValue": 1
                },
                "displayOptions": {
                    "show": {
                        "resource": ["form", "response"],
                        "operation": ["list"],
                        "returnAll": [False]
                    }
                }
            }
        ],
        "credentials": [
            {
                "name": "googleFormApi",
                "required": True
            }
        ]
    }
    
    icon = "googleForms.svg"
    color = "#673AB7"
    
    def __init__(self, *args, **kwargs):
        """Initialize with framework args and set up API URLs"""
        super().__init__(*args, **kwargs)
        # Use Drive API as primary approach since Forms API is restricted
        self.base_url = "https://www.googleapis.com/drive/v3"
        self.forms_url = "https://forms.googleapis.com/v1"  # Keep as fallback

    def _validate_parameter(self, param_value: Any) -> Any:
        """Validate parameter and ensure it's not a failed expression"""
        if isinstance(param_value, str) and param_value.startswith('=') and ('None' in param_value or 'null' in param_value):
            logger.warning(f"Parameter contains an invalid expression: {param_value}")
            return None
        return param_value

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Google Forms operations"""
        try:
            input_data = self.get_input_data()
            result_items = []
            
            for i, item in enumerate(input_data):
                try:
                    # Use get_parameter to properly evaluate expressions
                    resource = self.get_parameter("resource", i, "form")
                    operation = self.get_parameter("operation", i, "get")
                    
                    if resource == 'form':
                        if operation == 'create':
                            result = self._create_form(i)
                        elif operation == 'get':
                            result = self._get_form(i)
                        elif operation == 'update':
                            result = self._update_form(i)
                        elif operation == 'delete':
                            result = self._delete_form(i)
                        elif operation == 'list':
                            result = self._list_forms(i)
                        else:
                            raise ValueError(f"Unsupported form operation: {operation}")
                    
                    elif resource == 'question':
                        if operation == 'create':
                            result = self._create_question(i)
                        elif operation == 'get':
                            result = self._get_question(i)
                        elif operation == 'update':
                            result = self._update_question(i)
                        elif operation == 'delete':
                            result = self._delete_question(i)
                        else:
                            raise ValueError(f"Unsupported question operation: {operation}")
                    
                    elif resource == 'response':
                        if operation == 'get':
                            result = self._get_responses(i)
                        elif operation == 'list':
                            result = self._list_responses(i)
                        else:
                            raise ValueError(f"Unsupported response operation: {operation}")
                    
                    else:
                        raise ValueError(f"Unsupported resource: {resource}")
                    
                    result_items.append(NodeExecutionData(
                        json_data=result,
                        item_index=i,
                        binary_data=None
                    ))
                    
                except Exception as e:
                    logger.error(f"Google Forms Node - Error processing item {i}: {str(e)}")
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": self.get_parameter("resource", i, "form"),
                            "operation": self.get_parameter("operation", i, "get"),
                            "item_index": i
                        },
                        binary_data=None
                    )
                    result_items.append(error_item)
            
            return [result_items]
            
        except Exception as e:
            logger.error(f"Google Forms Node - Execute error: {str(e)}")
            error_data = [NodeExecutionData(
                json_data={"error": f"Error in Google Forms node: {str(e)}"},
                binary_data=None
            )]
            return [error_data]

    @staticmethod
    def has_access_token(credentials_data: Dict[str, Any]) -> bool:
        """Check if credentials have access token (n8n's approach)"""
        # Handle nested structure from credential system
        if 'data' in credentials_data:
            credentials_data = credentials_data['data']
        
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
        """Refresh OAuth2 access token with proper invalid_grant handling"""
            
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
                
                error_code = error_data.get("error", "")
                # Handle invalid_grant - user needs to reconnect
                if error_code == "invalid_grant":
                    raise ValueError(f"OAuth token invalid (invalid_grant). User must reconnect their Google Forms account.")
                
                raise Exception(f"Token refresh failed with status {response.status_code}: {error_data.get('error', 'Unknown error')}")
                
        except requests.RequestException as e:
            raise Exception(f"Token refresh request failed: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Token refresh failed: {str(e)}")

    def _get_access_token(self) -> str:
        """Get a valid access token for Google Forms API from the credentials"""
        try:
            credentials = self.get_credentials("googleFormApi")
            if not credentials:
                raise ValueError("Google Forms API credentials not found")

            if not self.has_access_token(credentials):
                raise ValueError("Google Forms API access token not found")

            oauth_token_data = credentials.get('oauthTokenData', {})
            if self._is_token_expired(oauth_token_data):
                credentials = self.refresh_token(credentials)

            return credentials['oauthTokenData']['access_token']
            
        except Exception as e:
            logger.error(f"Error getting Google Forms access token: {str(e)}")
            raise ValueError(f"Failed to get Google Forms access token: {str(e)}")
        
    def google_api_request(self, method: str, url: str, body: Dict[str, Any] = None, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """Make a request to Google API"""
        access_token = self._get_access_token()
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            logger.debug(f"Google Forms API request: {method} {url} params={params}")
            
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=body, params=params, timeout=30)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=body, params=params, timeout=30)
            elif method.upper() == 'PATCH':
                response = requests.patch(url, headers=headers, json=body, params=params, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, params=params, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            logger.debug(f"Google Forms API response status: {response.status_code}")
            response.raise_for_status()
            
            if response.content:
                return response.json()
            else:
                return {"success": True}
                
        except requests.RequestException as e:
            error_msg = str(e)
            try:
                if hasattr(e, 'response') and e.response:
                    error_data = e.response.json()
                    if 'error' in error_data:
                        if isinstance(error_data['error'], dict):
                            error_msg = f"Google Forms API Error: {error_data['error'].get('message', 'Unknown error')}"
                        else:
                            error_msg = f"Google Forms API Error: {error_data['error']}"
                    
                    # Add special handling for Forms API restrictions
                    if "forms.googleapis.com" in url and e.response.status_code == 404:
                        error_msg = "Google Forms API access is restricted. The Forms API requires joining Google's Early Access Program. Using Drive API for basic operations only."
            except:
                pass
            logger.error(f"Google Forms API request failed: {error_msg}")
            raise ValueError(error_msg)

    def _create_form(self, item_index: int) -> Dict[str, Any]:
        """Create a new Google Form using Drive API"""
        try:
            # Use get_parameter to properly evaluate expressions
            form_title = self.get_parameter("formTitle", item_index, "")
            form_description = self.get_parameter("formDescription", item_index, "")
            
            # Validate parameters
            form_title = self._validate_parameter(form_title)
            form_description = self._validate_parameter(form_description)
            
            if not form_title:
                raise ValueError("Form title is required")
            
            # Use only Drive API to create the form
            metadata = {
                "name": form_title,
                "description": form_description,
                "mimeType": "application/vnd.google-apps.form"
            }
            
            url = f"{self.base_url}/files"
            response = self.google_api_request('POST', url, body=metadata)
            
            form_id = response.get('id')
            
            # Return form details
            return {
                "id": form_id,
                "title": form_title,
                "description": form_description,
                "formUrl": f"https://docs.google.com/forms/d/{form_id}/viewform",
                "editUrl": f"https://docs.google.com/forms/d/{form_id}/edit",
                "createdTime": response.get('createdTime')
            }
            
        except Exception as e:
            logger.error(f"Error creating form: {str(e)}")
            raise

    def _get_form(self, item_index: int) -> Dict[str, Any]:
        """Get a Google Form by ID"""
        try:
            # Use get_parameter to properly evaluate expressions
            form_id = self.get_parameter("formId", item_index, "")
            
            # Validate evaluated parameters
            form_id = self._validate_parameter(form_id)
            
            if not form_id:
                raise ValueError("Form ID is required")
            
            url = f"{self.base_url}/files/{form_id}"
            
            # First, get basic information from Drive API
            response = self.google_api_request('GET', url)
            
            # Build standard response
            form_data = {
                "id": form_id,
                "title": response.get('name', ''),
                "description": response.get('description', ''),
                "formUrl": f"https://docs.google.com/forms/d/{form_id}/viewform",
                "editUrl": f"https://docs.google.com/forms/d/{form_id}/edit",
                "createdTime": response.get('createdTime'),
                "modifiedTime": response.get('modifiedTime')
            }
            
            # Try to get additional form information from Forms API
            try:
                forms_url = f"{self.forms_url}/forms/{form_id}"
                forms_response = self.google_api_request('GET', forms_url)
                
                # If Forms API response is available, add detailed information
                if forms_response:
                    form_data.update({
                        "info": forms_response.get('info', {}),
                        "settings": forms_response.get('settings', {}),
                        "items": forms_response.get('items', [])
                    })
            except Exception as forms_api_error:
                # Log but don't fail - Forms API might be restricted
                logger.warning(f"Could not get detailed form information from Forms API: {str(forms_api_error)}")
            
            return form_data
            
        except Exception as e:
            logger.error(f"Error getting form: {str(e)}")
            raise

    def _update_form(self, item_index: int) -> Dict[str, Any]:
        """Update a Google Form"""
        try:
            # Use get_parameter to properly evaluate expressions
            form_id = self.get_parameter("formId", item_index, "")
            form_title = self.get_parameter("formTitle", item_index, "")
            form_description = self.get_parameter("formDescription", item_index, "")
            
            # Validate evaluated parameters
            form_id = self._validate_parameter(form_id)
            form_title = self._validate_parameter(form_title)
            form_description = self._validate_parameter(form_description)
            
            if not form_id:
                raise ValueError("Form ID is required")
            
            # Prepare update metadata for Drive API
            metadata = {}
            if form_title:
                metadata["name"] = form_title
            if form_description:
                metadata["description"] = form_description
            
            if not metadata:
                raise ValueError("No update data provided")
            
            # Update using Drive API
            url = f"{self.base_url}/files/{form_id}"
            response = self.google_api_request('PATCH', url, body=metadata)
            
            return {
                "id": form_id,
                "title": response.get('name', ''),
                "description": response.get('description', ''),
                "formUrl": f"https://docs.google.com/forms/d/{form_id}/viewform",
                "editUrl": f"https://docs.google.com/forms/d/{form_id}/edit",
                "modifiedTime": response.get('modifiedTime'),
                "success": True
            }
            
        except Exception as e:
            logger.error(f"Error updating form: {str(e)}")
            raise

    def _delete_form(self, item_index: int) -> Dict[str, Any]:
        """Delete a Google Form"""
        try:
            # Use get_parameter to properly evaluate expressions
            form_id = self.get_parameter("formId", item_index, "")
            
            # Validate evaluated parameters
            form_id = self._validate_parameter(form_id)
            
            if not form_id:
                raise ValueError("Form ID is required")
            
            # For Google Forms, we need to use the Drive API to delete the form
            url = f"{self.base_url}/files/{form_id}"
            self.google_api_request('DELETE', url)
            
            return {
                "success": True,
                "formId": form_id,
                "message": "Form deleted successfully"
            }
            
        except Exception as e:
            logger.error(f"Error deleting form: {str(e)}")
            raise

    def _list_forms(self, item_index: int) -> Dict[str, Any]:
        """List Google Forms"""
        try:
            # Get parameters
            return_all = self.get_parameter("returnAll", item_index, False)
            limit = None if return_all else self.get_parameter("limit", item_index, 100)
            
            # Validate parameters
            return_all = self._validate_parameter(return_all)
            limit = self._validate_parameter(limit)
            
            # Use Drive API to list forms
            params = {
                'q': "mimeType='application/vnd.google-apps.form'",
                'fields': 'nextPageToken,files(id,name,description,createdTime,modifiedTime,webViewLink)'
            }
            
            if limit:
                params['pageSize'] = limit
            
            url = f"{self.base_url}/files"
            response = self.google_api_request('GET', url, params=params)
            
            # Transform response to match our expected format
            forms = []
            for form in response.get('files', []):
                forms.append({
                    "id": form.get('id'),
                    "title": form.get('name'),
                    "description": form.get('description', ''),
                    "formUrl": form.get('webViewLink', f"https://docs.google.com/forms/d/{form.get('id')}/viewform"),
                    "editUrl": f"https://docs.google.com/forms/d/{form.get('id')}/edit",
                    "createdTime": form.get('createdTime'),
                    "modifiedTime": form.get('modifiedTime')
                })
            
            return {
                "forms": forms,
                "nextPageToken": response.get('nextPageToken'),
                "totalForms": len(forms)
            }
            
        except Exception as e:
            logger.error(f"Error listing forms: {str(e)}")
            raise

    def _create_question(self, item_index: int) -> Dict[str, Any]:
        """Add a question to a Google Form"""
        try:
            # Get parameters
            form_id = self.get_parameter("formId", item_index, "")
            question_title = self.get_parameter("questionTitle", item_index, "")
            question_type = self.get_parameter("questionType", item_index, "TEXT")
            question_required = self.get_parameter("questionRequired", item_index, False)
            
            # Validate parameters
            form_id = self._validate_parameter(form_id)
            question_title = self._validate_parameter(question_title)
            question_type = self._validate_parameter(question_type)
            question_required = self._validate_parameter(question_required)
            
            if not form_id:
                raise ValueError("Form ID is required")
            
            if not question_title:
                raise ValueError("Question title is required")
            
            # For choices, handle separately since it's a collection
            choice_items = []
            if question_type in ["MULTIPLE_CHOICE", "CHECKBOXES", "DROPDOWN"]:
                choices = self.get_parameter("questionChoices", item_index, [])
                choices = self._validate_parameter(choices)
                
                if not choices:
                    raise ValueError(f"{question_type} question requires options")
                
                # Prepare choice items
                for choice in choices:
                    choice_value = choice.get("value", "")
                    choice_value = self._validate_parameter(choice_value)
                    
                    if not choice_value:
                        choice_value = ""
                    
                    choice_items.append({"value": choice_value})
            
            # Check if Forms API is available
            try:
                # Try to access the form using Forms API
                form_url = f"{self.forms_url}/forms/{form_id}"
                current_form = self.google_api_request('GET', form_url)
                
                # Prepare the question based on type
                question_item = {
                    "title": question_title,
                    "questionItem": {
                        "question": {
                            "required": question_required,
                            "textQuestion": {}  # Default for TEXT type
                        }
                    }
                }
                
                # Set question type
                if question_type == "TEXT":
                    question_item["questionItem"]["question"]["textQuestion"] = {}
                elif question_type == "PARAGRAPH_TEXT":
                    question_item["questionItem"]["question"]["textQuestion"] = {"paragraph": True}
                elif question_type in ["MULTIPLE_CHOICE", "CHECKBOXES", "DROPDOWN"]:
                    # Get choices for multiple choice questions
                    if question_type == "MULTIPLE_CHOICE":
                        question_item["questionItem"]["question"]["choiceQuestion"] = {
                            "type": "RADIO",
                            "options": choice_items
                        }
                    elif question_type == "CHECKBOXES":
                        question_item["questionItem"]["question"]["choiceQuestion"] = {
                            "type": "CHECKBOX",
                            "options": choice_items
                        }
                    elif question_type == "DROPDOWN":
                        question_item["questionItem"]["question"]["choiceQuestion"] = {
                            "type": "DROP_DOWN",
                            "options": choice_items
                        }
                elif question_type == "LINEAR_SCALE":
                    question_item["questionItem"]["question"]["scaleQuestion"] = {
                        "low": 1,
                        "high": 5,
                        "lowLabel": "Low",
                        "highLabel": "High"
                    }
                elif question_type == "DATE":
                    question_item["questionItem"]["question"]["dateQuestion"] = {"includeTime": False}
                elif question_type == "TIME":
                    question_item["questionItem"]["question"]["timeQuestion"] = {}
                    
                # Create the request
                request_body = {
                    "requests": [
                        {
                            "createItem": {
                                "item": question_item,
                                "location": {"index": len(current_form.get('items', []))}
                            }
                        }
                    ]
                }
                
                # Add the question
                batch_url = f"{self.forms_url}/forms/{form_id}:batchUpdate"
                response = self.google_api_request('POST', batch_url, body=request_body)
                
                # Get the updated form to find the created question
                updated_form = self.google_api_request('GET', form_url)
                created_item = updated_form.get('items', [])[-1]  # Last item should be our new question
                
                return {
                    "formId": form_id,
                    "questionId": created_item.get('itemId'),
                    "title": question_title,
                    "type": question_type,
                    "required": question_required,
                    "success": True
                }
                
            except Exception as forms_api_error:
                # Forms API failed - inform user
                logger.error(f"Failed to create question using Forms API: {str(forms_api_error)}")
                raise ValueError("Google Forms API access is restricted. Creating questions requires joining Google's Forms API Early Access Program.")
            
        except Exception as e:
            logger.error(f"Error creating question: {str(e)}")
            raise

    def _get_question(self, item_index: int) -> Dict[str, Any]:
        """Get a question from a Google Form"""
        try:
            # Get parameters
            form_id = self.get_parameter("formId", item_index, "")
            question_id = self.get_parameter("questionId", item_index, "")
            
            # Validate parameters
            form_id = self._validate_parameter(form_id)
            question_id = self._validate_parameter(question_id)
            
            if not form_id:
                raise ValueError("Form ID is required")
            
            if not question_id:
                raise ValueError("Question ID is required")
            
            # Get the form
            form_url = f"{self.forms_url}/forms/{form_id}"
            form = self.google_api_request('GET', form_url)
            
            # Find the question by ID
            question = None
            for item in form.get('items', []):
                if item.get('itemId') == question_id:
                    question = item
                    break
            
            if not question:
                raise ValueError(f"Question with ID {question_id} not found")
            
            return question
            
        except Exception as e:
            logger.error(f"Error getting question: {str(e)}")
            raise

    def _update_question(self, item_index: int) -> Dict[str, Any]:
        """Update a question in a Google Form"""
        try:
            # Get parameters
            form_id = self.get_parameter("formId", item_index, "")
            question_id = self.get_parameter("questionId", item_index, "")
            question_title = self.get_parameter("questionTitle", item_index, "")
            question_required = self.get_parameter("questionRequired", item_index, None)
            
            # Validate parameters
            form_id = self._validate_parameter(form_id)
            question_id = self._validate_parameter(question_id)
            question_title = self._validate_parameter(question_title)
            question_required = self._validate_parameter(question_required)
            
            if not form_id:
                raise ValueError("Form ID is required")
            
            if not question_id:
                raise ValueError("Question ID is required")
            
            # Get current form to find the question
            form_url = f"{self.forms_url}/forms/{form_id}"
            current_form = self.google_api_request('GET', form_url)
            
            # Find the question by ID
            question_index = None
            question = None
            for i, item in enumerate(current_form.get('items', [])):
                if item.get('itemId') == question_id:
                    question_index = i
                    question = item
                    break
            
            if question_index is None:
                raise ValueError(f"Question with ID {question_id} not found")
            
            # Prepare the update mask and data
            update_mask = []
            update_data = {}
            
            if question_title:
                update_data["title"] = question_title
                update_mask.append("title")
            
            if question_required is not None:
                # Determine the question type to build the correct path
                if "questionItem" in question:
                    question_item = question["questionItem"]
                    if "question" in question_item:
                        question_data = question_item["question"]
                        
                        # Set required field in the update data
                        if "questionItem" not in update_data:
                            update_data["questionItem"] = {}
                        if "question" not in update_data["questionItem"]:
                            update_data["questionItem"]["question"] = {}
                        
                        update_data["questionItem"]["question"]["required"] = question_required
                        update_mask.append("questionItem.question.required")
            
            if not update_mask:
                raise ValueError("No update data provided")
            
            # Create the request
            request_body = {
                "requests": [
                    {
                        "updateItem": {
                            "item": update_data,
                            "location": {"index": question_index},
                            "updateMask": ",".join(update_mask)
                        }
                    }
                ]
            }
            
            # Update the question
            batch_url = f"{self.base_url}/forms/{form_id}:batchUpdate"
            response = self.google_api_request('POST', batch_url, body=request_body)
            
            return {
                "formId": form_id,
                "questionId": question_id,
                "success": True,
                "message": "Question updated successfully"
            }
            
        except Exception as e:
            logger.error(f"Error updating question: {str(e)}")
            raise

    def _delete_question(self, item_index: int) -> Dict[str, Any]:
        """Delete a question from a Google Form"""
        try:
            # Get parameters
            form_id = self.get_parameter("formId", item_index, "")
            question_id = self.get_parameter("questionId", item_index, "")
            
            # Validate parameters
            form_id = self._validate_parameter(form_id)
            question_id = self._validate_parameter(question_id)
            
            if not form_id:
                raise ValueError("Form ID is required")
            
            if not question_id:
                raise ValueError("Question ID is required")
            
            # Create the request
            request_body = {
                "requests": [
                    {
                        "deleteItem": {
                            "location": {"itemId": question_id}
                        }
                    }
                ]
            }
            
            # Delete the question
            batch_url = f"{self.base_url}/forms/{form_id}:batchUpdate"
            response = self.google_api_request('POST', batch_url, body=request_body)
            
            return {
                "formId": form_id,
                "questionId": question_id,
                "success": True,
                "message": "Question deleted successfully"
            }
            
        except Exception as e:
            logger.error(f"Error deleting question: {str(e)}")
            raise

    def _get_responses(self, item_index: int) -> Dict[str, Any]:
        """Get responses for a Google Form"""
        try:
            # Get parameters
            form_id = self.get_parameter("formId", item_index, "")
            include_responses = self.get_parameter("includeResponses", item_index, True)
            
            # Validate parameters
            form_id = self._validate_parameter(form_id)
            include_responses = self._validate_parameter(include_responses)
            
            if not form_id:
                raise ValueError("Form ID is required")
            
            # Build query parameters
            params = {}
            if include_responses:
                params['responseId'] = '*'
            
            # Get the responses
            responses_url = f"{self.forms_url}/forms/{form_id}/responses"
            response = self.google_api_request('GET', responses_url, params=params)
            
            # Get the form to include question text
            form_url = f"{self.forms_url}/forms/{form_id}"
            form = self.google_api_request('GET', form_url)
            
            # Create a mapping of question IDs to questions
            questions = {}
            for item in form.get('items', []):
                if 'questionItem' in item:
                    questions[item.get('itemId')] = {
                        'title': item.get('title', ''),
                        'type': self._get_question_type(item)
                    }
            
            # Add question titles to responses
            enriched_responses = []
            for resp in response.get('responses', []):
                enriched_resp = {
                    'responseId': resp.get('responseId', ''),
                    'createTime': resp.get('createTime', ''),
                    'lastSubmittedTime': resp.get('lastSubmittedTime', ''),
                    'answers': {}
                }
                
                # Process each answer
                for question_id, answer in resp.get('answers', {}).items():
                    if question_id in questions:
                        question_title = questions[question_id]['title']
                        question_type = questions[question_id]['type']
                        
                        # Extract answer value based on type
                        answer_value = self._extract_answer_value(answer, question_type)
                        
                        enriched_resp['answers'][question_id] = {
                            'questionId': question_id,
                            'questionTitle': question_title,
                            'questionType': question_type,
                            'value': answer_value
                        }
                
                enriched_responses.append(enriched_resp)
            
            return {
                "formId": form_id,
                "responseCount": response.get('responseSize', 0),
                "responses": enriched_responses,
                "questions": questions
            }
            
        except Exception as e:
            logger.error(f"Error getting responses: {str(e)}")
            raise

    def _list_responses(self, item_index: int) -> Dict[str, Any]:
        """List responses for a Google Form with pagination"""
        try:
            # Get parameters
            form_id = self.get_parameter("formId", item_index, "")
            include_responses = self.get_parameter("includeResponses", item_index, True)
            return_all = self.get_parameter("returnAll", item_index, False)
            limit = None if return_all else self.get_parameter("limit", item_index, 100)
            
            # Validate parameters
            form_id = self._validate_parameter(form_id)
            include_responses = self._validate_parameter(include_responses)
            return_all = self._validate_parameter(return_all)
            limit = self._validate_parameter(limit)
            
            if not form_id:
                raise ValueError("Form ID is required")
            
            # Build query parameters
            params = {}
            if include_responses:
                params['responseId'] = '*'
            
            if limit:
                params['pageSize'] = limit
            
            # Get the responses
            responses_url = f"{self.forms_url}/forms/{form_id}/responses"
            response = self.google_api_request('GET', responses_url, params=params)
            
            # Get the form to include question text
            form_url = f"{self.forms_url}/forms/{form_id}"
            form = self.google_api_request('GET', form_url)
            
            # Create a mapping of question IDs to questions
            questions = {}
            for item in form.get('items', []):
                if 'questionItem' in item:
                    questions[item.get('itemId')] = {
                        'title': item.get('title', ''),
                        'type': self._get_question_type(item)
                    }
            
            # Add question titles to responses
            enriched_responses = []
            for resp in response.get('responses', []):
                enriched_resp = {
                    'responseId': resp.get('responseId', ''),
                    'createTime': resp.get('createTime', ''),
                    'lastSubmittedTime': resp.get('lastSubmittedTime', ''),
                    'answers': {}
                }
                
                # Process each answer
                for question_id, answer in resp.get('answers', {}).items():
                    if question_id in questions:
                        question_title = questions[question_id]['title']
                        question_type = questions[question_id]['type']
                        
                        # Extract answer value based on type
                        answer_value = self._extract_answer_value(answer, question_type)
                        
                        enriched_resp['answers'][question_id] = {
                            'questionId': question_id,
                            'questionTitle': question_title,
                            'questionType': question_type,
                            'value': answer_value
                        }
                
                enriched_responses.append(enriched_resp)
            
            return {
                "formId": form_id,
                "responseCount": response.get('responseSize', 0),
                "responses": enriched_responses,
                "questions": questions,
                "nextPageToken": response.get('nextPageToken')
            }
            
        except Exception as e:
            logger.error(f"Error listing responses: {str(e)}")
            raise

    def _get_question_type(self, item: Dict[str, Any]) -> str:
        """Determine the question type from the item data"""
        if 'questionItem' not in item:
            return "UNKNOWN"
        
        question = item.get('questionItem', {}).get('question', {})
        
        if 'textQuestion' in question:
            if question.get('textQuestion', {}).get('paragraph', False):
                return "PARAGRAPH_TEXT"
            return "TEXT"
        elif 'choiceQuestion' in question:
            choice_type = question.get('choiceQuestion', {}).get('type', '')
            if choice_type == 'RADIO':
                return "MULTIPLE_CHOICE"
            elif choice_type == 'CHECKBOX':
                return "CHECKBOXES"
            elif choice_type == 'DROP_DOWN':
                return "DROPDOWN"
        elif 'scaleQuestion' in question:
            return "LINEAR_SCALE"
        elif 'dateQuestion' in question:
            return "DATE"
        elif 'timeQuestion' in question:
            return "TIME"
        
        return "UNKNOWN"

    def _extract_answer_value(self, answer: Dict[str, Any], question_type: str) -> Any:
        """Extract the answer value based on question type"""
        if 'textAnswers' in answer:
            # For text, paragraph, etc.
            text_values = [text.get('value', '') for text in answer.get('textAnswers', {}).get('answers', [])]
            if len(text_values) == 1:
                return text_values[0]
            return text_values
        elif 'choiceAnswers' in answer:
            # For multiple choice, checkboxes, dropdown
            choice_values = [choice.get('value', '') for choice in answer.get('choiceAnswers', {}).get('answers', [])]
            if question_type == "MULTIPLE_CHOICE" or question_type == "DROPDOWN":
                return choice_values[0] if choice_values else ""
            return choice_values
        elif 'scaleAnswers' in answer:
            # For linear scale
            scale_values = [scale.get('value', 0) for scale in answer.get('scaleAnswers', {}).get('answers', [])]
            return scale_values[0] if scale_values else 0
        elif 'dateAnswers' in answer:
            # For date
            date_values = []
            for date in answer.get('dateAnswers', {}).get('answers', []):
                date_obj = {}
                if 'day' in date:
                    date_obj['day'] = date['day']
                if 'month' in date:
                    date_obj['month'] = date['month']
                if 'year' in date:
                    date_obj['year'] = date['year']
                date_values.append(date_obj)
            return date_values[0] if date_values else {}
        elif 'timeAnswers' in answer:
            # For time
            time_values = []
            for time in answer.get('timeAnswers', {}).get('answers', []):
                time_obj = {}
                if 'hours' in time:
                    time_obj['hours'] = time['hours']
                if 'minutes' in time:
                    time_obj['minutes'] = time['minutes']
                if 'seconds' in time:
                    time_obj['seconds'] = time['seconds']
                time_values.append(time_obj)
            return time_values[0] if time_values else {}
        
        return None