import requests
import json
import logging
import copy
import time
import base64
from urllib.parse import urlencode
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from models import NodeExecutionData, Node, WorkflowModel
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class GoogleDocsNode(BaseNode):
    """
    Google Docs node for managing document operations
    """
    
    type = "googleDocs"
    version = 2.0
    
    description = {
        "displayName": "Google Docs",
        "name": "googleDocs",
        "icon": "file:googleDocs.svg",
        "group": ["input", "output"],
        "description": "Consume Google Docs API",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
        "credentials": [
            {
                "name": "googleOAuth2Api",
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
                    {"name": "Document", "value": "document"}
                ],
                "default": "document",
                "description": "The resource to operate on"
            },
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Create", "value": "create", "description": "Create a new document"},
                    {"name": "Get", "value": "get", "description": "Get a document"},
                    {"name": "Update", "value": "update", "description": "Update a document"}
                ],
                "default": "create",
                "display_options": {"show": {"resource": ["document"]}}
            },
            # Create operation parameters
            {
                "name": "title",
                "type": NodeParameterType.STRING,
                "display_name": "Title",
                "default": "",
                "required": True,
                "description": "The title of the document",
                "display_options": {"show": {"resource": ["document"], "operation": ["create"]}}
            },
            {
                "name": "folderId",
                "type": NodeParameterType.STRING,
                "display_name": "Folder ID",
                "default": "",
                "required": False,
                "description": "ID of the folder where the document should be created",
                "display_options": {"show": {"resource": ["document"], "operation": ["create"]}}
            },
            # Get and Update operation parameters - documentId is required for both
            # Note: Removing 'required': True to avoid validation issues, will validate manually
            {
                "name": "documentId",
                "type": NodeParameterType.STRING,
                "display_name": "Document ID",
                "default": "",
                "required": False,  # Changed to False, will validate manually in methods
                "description": "ID of the document",
                "display_options": {"show": {"resource": ["document"], "operation": ["get", "update"]}}
            },
            {
                "name": "continueOnFail",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Continue On Fail",
                "default": False,
                "description": "Whether to continue execution even when the node encounters an error",
                "display_options": {"show": {"resource": ["document"]}}
            },
            {
                "name": "simple",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Simple",
                "default": False,
                "description": "Whether to return a simplified version of the response",
                "display_options": {"show": {"resource": ["document"], "operation": ["get", "update"]}}
            },
            {
                "name": "writeControlObject",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Write Control",
                "default": {},
                "description": "Control document revisions during updates",
                "options": [
                    {
                        "name": "revisionId",
                        "type": NodeParameterType.STRING,
                        "display_name": "Revision ID",
                        "default": "",
                        "description": "The revision ID of the document to update"
                    },
                    {
                        "name": "requiredRevisionId",
                        "type": NodeParameterType.STRING,
                        "display_name": "Required Revision ID",
                        "default": "",
                        "description": "The revision ID that is required to update the document"
                    }
                ],
                "display_options": {"show": {"resource": ["document"], "operation": ["update"]}}
            },
            # Get operation specific parameters
            {
                "name": "suggestionsViewMode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Suggestions View Mode",
                "options": [
                    {"name": "Default for Current Access Level", "value": "DEFAULT_FOR_CURRENT_ACCESS_LEVEL"},
                    {"name": "Suggestions Inline", "value": "SUGGESTIONS_INLINE"},
                    {"name": "Preview Suggestions Accepted", "value": "PREVIEW_SUGGESTIONS_ACCEPTED"},
                    {"name": "Preview Without Suggestions", "value": "PREVIEW_WITHOUT_SUGGESTIONS"}
                ],
                "default": "DEFAULT_FOR_CURRENT_ACCESS_LEVEL",
                "description": "The suggestions view mode to apply to the document",
                "display_options": {"show": {"resource": ["document"], "operation": ["get"]}}
            },
            # Update operation parameters
            {
                "name": "actionsUi",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Actions",
                "default": {},
                "placeholder": "Add Action",
                "required": False,
                "options": [
                    {
                        "name": "replaceAllText",
                        "type": NodeParameterType.COLLECTION,
                        "display_name": "Replace All Text",
                        "default": {},
                        "description": "Replace all instances of text",
                        "options": [
                            {
                                "name": "text",
                                "type": NodeParameterType.STRING,
                                "display_name": "Text",
                                "default": "",
                                "description": "The text to replace"
                            },
                            {
                                "name": "replaceText",
                                "type": NodeParameterType.STRING,
                                "display_name": "Replace Text",
                                "default": "",
                                "description": "The text to replace it with"
                            },
                            {
                                "name": "matchCase",
                                "type": NodeParameterType.BOOLEAN,
                                "display_name": "Match Case",
                                "default": False,
                                "description": "Whether the search should respect case"
                            }
                        ]
                    },
                    {
                        "name": "insertText",
                        "type": NodeParameterType.COLLECTION,
                        "display_name": "Insert Text",
                        "default": {},
                        "description": "Insert text at a specific location",
                        "options": [
                            {
                                "name": "text",
                                "type": NodeParameterType.STRING,
                                "display_name": "Text",
                                "default": "",
                                "description": "The text to insert"
                            },
                            {
                                "name": "location",
                                "type": NodeParameterType.OPTIONS,
                                "display_name": "Location",
                                "options": [
                                    {"name": "End of Document", "value": "END_OF_DOCUMENT"},
                                    {"name": "Start of Document", "value": "START_OF_DOCUMENT"},
                                    {"name": "Specific Index", "value": "SPECIFIC_INDEX"}
                                ],
                                "default": "END_OF_DOCUMENT"
                            },
                            {
                                "name": "index",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Index",
                                "default": 1,
                                "description": "The character index where to insert the text",
                                "display_options": {"show": {"location": ["SPECIFIC_INDEX"]}}
                            }
                        ]
                    },
                    {
                        "name": "insertTable",
                        "type": NodeParameterType.COLLECTION,
                        "display_name": "Insert Table",
                        "default": {},
                        "description": "Insert a table",
                        "options": [
                            {
                                "name": "rows",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Rows",
                                "default": 2,
                                "description": "The number of rows in the table"
                            },
                            {
                                "name": "columns",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Columns",
                                "default": 2,
                                "description": "The number of columns in the table"
                            },
                            {
                                "name": "location",
                                "type": NodeParameterType.OPTIONS,
                                "display_name": "Location",
                                "options": [
                                    {"name": "End of Document", "value": "END_OF_DOCUMENT"},
                                    {"name": "Start of Document", "value": "START_OF_DOCUMENT"},
                                    {"name": "Specific Index", "value": "SPECIFIC_INDEX"}
                                ],
                                "default": "END_OF_DOCUMENT"
                            },
                            {
                                "name": "index",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Index",
                                "default": 1,
                                "description": "The character index where to insert the table",
                                "display_options": {"show": {"location": ["SPECIFIC_INDEX"]}}
                            }
                        ]
                    },
                    {
                        "name": "updateTableCellProperties",
                        "type": NodeParameterType.COLLECTION,
                        "display_name": "Update Table Cell Properties",
                        "default": {},
                        "description": "Update properties of a table cell",
                        "options": [
                            {
                                "name": "tableStartIndex",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Table Start Index",
                                "default": 0,
                                "description": "The start index of the table"
                            },
                            {
                                "name": "rowIndex",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Row Index",
                                "default": 0,
                                "description": "The index of the row"
                            },
                            {
                                "name": "columnIndex",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Column Index",
                                "default": 0,
                                "description": "The index of the column"
                            },
                            {
                                "name": "backgroundColor",
                                "type": NodeParameterType.STRING,
                                "display_name": "Background Color",
                                "default": "",
                                "description": "Cell background color in hex format (#RRGGBB)"
                            }
                        ]
                    },
                    {
                        "name": "insertBulletedList",
                        "type": NodeParameterType.COLLECTION,
                        "display_name": "Insert Bulleted List",
                        "default": {},
                        "description": "Insert a bulleted list",
                        "options": [
                            {
                                "name": "items",
                                "type": NodeParameterType.ARRAY,
                                "display_name": "List Items",
                                "default": [],
                                "description": "Items in the bulleted list"
                            },
                            {
                                "name": "location",
                                "type": NodeParameterType.OPTIONS,
                                "display_name": "Location",
                                "options": [
                                    {"name": "End of Document", "value": "END_OF_DOCUMENT"},
                                    {"name": "Start of Document", "value": "START_OF_DOCUMENT"},
                                    {"name": "Specific Index", "value": "SPECIFIC_INDEX"}
                                ],
                                "default": "END_OF_DOCUMENT"
                            },
                            {
                                "name": "index",
                                "type": NodeParameterType.NUMBER,
                                "display_name": "Index",
                                "default": 1,
                                "description": "The character index where to insert the list",
                                "display_options": {"show": {"location": ["SPECIFIC_INDEX"]}}
                            }
                        ]
                    },
                    {
                        "name": "insertHeader",
                        "type": NodeParameterType.COLLECTION,
                        "display_name": "Insert Header",
                        "default": {},
                        "description": "Insert a header",
                        "options": [
                            {
                                "name": "text",
                                "type": NodeParameterType.STRING,
                                "display_name": "Header Text",
                                "default": "",
                                "description": "Text to insert in the header"
                            }
                        ]
                    },
                    {
                        "name": "insertFooter",
                        "type": NodeParameterType.COLLECTION,
                        "display_name": "Insert Footer",
                        "default": {},
                        "description": "Insert a footer",
                        "options": [
                            {
                                "name": "text",
                                "type": NodeParameterType.STRING,
                                "display_name": "Footer Text",
                                "default": "",
                                "description": "Text to insert in the footer"
                            }
                        ]
                    }
                ],
                "display_options": {"show": {"resource": ["document"], "operation": ["update"]}}
            }
        ],
        "credentials": [
            {
                "name": "googleDocsApi",
                "required": True
            }
        ]
    }
    
    icon = "googleDocs.svg"
    color = "#4285F4"
    base_url = "https://docs.googleapis.com/v1"

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
                    raise ValueError(f"OAuth token invalid (invalid_grant). User must reconnect their Google Docs account.")
                
                raise Exception(f"Token refresh failed with status {response.status_code}: {error_data.get('error', 'Unknown error')}")
                
        except requests.RequestException as e:
            raise Exception(f"Token refresh request failed: {str(e)}")
        except ValueError:
            raise
        except Exception as e:
            raise Exception(f"Token refresh failed: {str(e)}")

    def _get_access_token(self) -> str:
        """Get a valid access token for Google Docs API from the credentials"""
        try:
            credentials = self.get_credentials("googleDocsApi")
            if not credentials:
                raise ValueError("Google Docs API credentials not found")

            if not self.has_access_token(credentials):
                raise ValueError("Google Docs API access token not found")

            oauth_token_data = credentials.get('oauthTokenData', {})
            if self._is_token_expired(oauth_token_data):
                credentials = self.refresh_token(credentials)

            return credentials['oauthTokenData']['access_token']
            
        except Exception as e:
            logger.error(f"Error getting Google Docs access token: {str(e)}")
            raise ValueError(f"Failed to get Google Docs access token: {str(e)}")
        

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Google Docs operation and return properly formatted data"""
        
        try:
            # Get input data using the same pattern as Gmail node
            input_data = self.get_input_data()
            
            # Handle empty input data case
            if not input_data:
                input_data = [NodeExecutionData(json_data={}, binary_data=None)]
                
            # Flatten nested input data if needed
            if input_data and isinstance(input_data[0], list):
                flattened_data = []
                for sublist in input_data:
                    flattened_data.extend(sublist)
                input_data = flattened_data
        
            result_items = []
        
            # Process each input item
            for i, item in enumerate(input_data):
                try:
                    # Extract json_data properly
                    if hasattr(item, 'json_data'):
                        item_data = item.json_data if item.json_data else {}
                    elif isinstance(item, dict) and 'json_data' in item:
                        item_data = item['json_data'] if item['json_data'] else {}
                        # Convert dict to NodeExecutionData
                        item = NodeExecutionData(**item)
                    else:
                        item_data = {}
                
                    # Get parameters for this item
                    resource = self.get_node_parameter("resource", i, "document")
                    operation = self.get_node_parameter("operation", i, "create")
                    continue_on_fail = self.get_node_parameter("continueOnFail", i, False)
            
                    # Execute the appropriate operation
                    if resource == 'document':
                        if operation == 'create':
                            result = self._create_document(i)
                        elif operation == 'get':
                            result = self._get_document(i)
                        elif operation == 'update':
                            result = self._update_document(i)
                        else:
                            raise ValueError(f"Unsupported operation '{operation}' for resource '{resource}'")
                    else:
                        raise ValueError(f"Unsupported resource '{resource}'")
                
                    # Add result to items
                    if isinstance(result, list):
                        for res_item in result:
                            result_items.append(NodeExecutionData(
                                json_data=res_item,
                                binary_data=None
                            ))
                    else:
                        result_items.append(NodeExecutionData(
                            json_data=result,
                            binary_data=None
                        ))
                
                except Exception as e:
                    logger.error(f"Google Docs Node - Error processing item {i}: {str(e)}", exc_info=True)
                    # Create error data
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": self.get_node_parameter("resource", i, "document"),
                            "operation": self.get_node_parameter("operation", i, "create"),
                            "item_index": i
                        },
                        binary_data=None
                    )
                    
                    result_items.append(error_item)
                    
                    # If continueOnFail is False, stop processing and return error
                    if not continue_on_fail:
                        break
        
            return [result_items]
        
        except Exception as e:
            logger.error(f"Google Docs Node - Execute error: {str(e)}", exc_info=True)
            error_data = [NodeExecutionData(
                json_data={"error": f"Error in Google Docs node: {str(e)}"},
                binary_data=None
            )]
            return [error_data]

    def _create_document(self, item_index: int) -> Dict[str, Any]:
        """Create a new Google Docs document"""
        try:
            access_token = self._get_access_token()
            
            # Get parameters
            title = self.get_node_parameter("title", item_index, "")
            folder_id = self.get_node_parameter("folderId", item_index, "")
            
            if not title:
                raise ValueError("Title is required for creating a document")
            
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            
            # Create document
            create_url = f"{self.base_url}/documents"
            body = {"title": title}

            response = requests.post(create_url, headers=headers, json=body, timeout=30)
            
            if response.status_code == 200:
                doc_data = response.json()
                
                # Move to folder if specified
                if folder_id:
                    self._move_document_to_folder(doc_data['documentId'], folder_id, access_token)
                
                result = {
                    "documentId": doc_data.get('documentId'),
                    "title": doc_data.get('title'),
                    "revisionId": doc_data.get('revisionId'),
                    "documentUrl": f"https://docs.google.com/document/d/{doc_data.get('documentId')}/edit",
                    "status": "created"
                }
                
                return result
            else:
                error_text = response.text
                raise ValueError(f"Create document API failed with status {response.status_code}: {error_text}")
                        
        except Exception as e:
            logger.error(f"Error creating Google Docs document: {str(e)}", exc_info=True)
            raise

    def _get_document(self, item_index: int) -> Dict[str, Any]:
        """Get a Google Docs document"""
        try:
            access_token = self._get_access_token()
            
            # Get parameters - manually validate documentId for get operation
            document_id = self.get_node_parameter("documentId", item_index, "")
            suggestions_view_mode = self.get_node_parameter("suggestionsViewMode", item_index, "DEFAULT_FOR_CURRENT_ACCESS_LEVEL")
            simple = self.get_node_parameter("simple", item_index, False)
            
            if not document_id:
                raise ValueError("Document ID is required for get operation")
            
            headers = {"Authorization": f"Bearer {access_token}"}
            
            # Get document
            get_url = f"{self.base_url}/documents/{document_id}"
            params = {"suggestionsViewMode": suggestions_view_mode}
            
            response = requests.get(get_url, headers=headers, params=params, timeout=30)
            
            if response.status_code == 200:
                doc_data = response.json()
                
                # Extract text content
                text_content = self._extract_text_content(doc_data)
                
                # Return simplified version if simple flag is set
                if simple:
                    return {
                        "documentId": doc_data.get('documentId'),
                        "title": doc_data.get('title'),
                        "textContent": text_content
                    }
                
                # Return detailed version
                result = {
                    "documentId": doc_data.get('documentId'),
                    "title": doc_data.get('title'),
                    "revisionId": doc_data.get('revisionId'),
                    "documentUrl": f"https://docs.google.com/document/d/{document_id}/edit",
                    "textContent": text_content,
                    "rawDocument": doc_data
                }
                
                return result
            else:
                error_text = response.text
                raise ValueError(f"Get document API failed: {error_text}")
                        
        except Exception as e:
            logger.error(f"Error getting Google Docs document: {str(e)}", exc_info=True)
            raise

    def _update_document(self, item_index: int) -> Dict[str, Any]:
        """Update a Google Docs document - only process ONE action at a time"""
        try:
            access_token = self._get_access_token()
            
            # Get parameters - manually validate documentId for update operation
            document_id = self.get_node_parameter("documentId", item_index, "")
            actions_ui = self.get_node_parameter("actionsUi", item_index, {})
            simple = self.get_node_parameter("simple", item_index, False)
            write_control_object = self.get_node_parameter("writeControlObject", item_index, {})

            if not document_id:
                raise ValueError("Document ID is required for update operation")
            
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            
            # Build requests array from actions - ONLY PROCESS THE FIRST VALID ACTION
            requests_array = []
            action_processed = None
            
            # Define action priority order (most commonly used first)
            action_priority = [
                "insertText",
                "replaceAllText", 
                "insertTable",
                "insertBulletedList",
                "updateTableCellProperties",
                "insertHeader",
                "insertFooter"
            ]
            
            # Process actions in priority order - STOP after first valid action
            for action_name in action_priority:
                if action_name in actions_ui and not action_processed:
                    action_config = actions_ui[action_name]
                    
                    # Validate if this action has meaningful data
                    if self._is_valid_action(action_name, action_config):
                        if action_name == "replaceAllText":
                            requests_array.extend(self._build_replace_text_requests(action_config, item_index))
                            action_processed = "replaceAllText"
                            
                        elif action_name == "insertText":
                            requests_array.extend(self._build_insert_text_requests(action_config, document_id, headers, item_index))
                            action_processed = "insertText"
                            
                        elif action_name == "insertTable":
                            requests_array.extend(self._build_insert_table_requests(action_config, document_id, headers))
                            action_processed = "insertTable"
                            
                        elif action_name == "insertBulletedList":
                            requests_array.extend(self._build_insert_list_requests(action_config, document_id, headers))
                            action_processed = "insertBulletedList"
                            
                        elif action_name == "updateTableCellProperties":
                            requests_array.extend(self._build_update_cell_requests(action_config))
                            action_processed = "updateTableCellProperties"
                            
                        elif action_name == "insertHeader":
                            requests_array.extend(self._build_insert_header_requests(action_config, item_index))
                            action_processed = "insertHeader"
                            
                        elif action_name == "insertFooter":
                            requests_array.extend(self._build_insert_footer_requests(action_config, item_index))
                            action_processed = "insertFooter"
                        
                        # Stop after processing the first valid action
                        break
            
            if not requests_array:
                raise ValueError("No valid actions specified for update operation")

            
            # Prepare body with requests and optional write control
            body = {"requests": requests_array}
            
            # Add write control for revision control if specified
            if write_control_object:
                if "revisionId" in write_control_object:
                    body["writeControl"] = {"requiredRevisionId": write_control_object["revisionId"]}
                elif "requiredRevisionId" in write_control_object:
                    body["writeControl"] = {"requiredRevisionId": write_control_object["requiredRevisionId"]}
            
            # Execute batch update
            update_url = f"{self.base_url}/documents/{document_id}:batchUpdate"
            response = requests.post(update_url, headers=headers, json=body, timeout=30)
            
            if response.status_code == 200:
                update_data = response.json()
                
                # Handle simple response format
                if simple:
                    result = {
                        "documentId": document_id,
                        "success": True,
                        "actionProcessed": action_processed
                    }
                else:
                    result = {
                        "documentId": document_id,
                        "status": "updated",
                        "actionProcessed": action_processed,
                        "documentUrl": f"https://docs.google.com/document/d/{document_id}/edit",
                        "replies": update_data.get("replies", []),
                        "writeControl": update_data.get("writeControl", {})
                    }
                
                return result
            else:
                error_text = response.text
                raise ValueError(f"Update document API failed: {error_text}")
                        
        except Exception as e:
            logger.error(f"Error updating Google Docs document: {str(e)}", exc_info=True)
            raise

    def _move_document_to_folder(self, document_id: str, folder_id: str, access_token: str) -> None:
        """Move document to a specific folder using Google Drive API"""
        try:
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            
            # Use Google Drive API to move the file
            drive_url = f"https://www.googleapis.com/drive/v3/files/{document_id}"
            
            # First, get current parents
            get_response = requests.get(f"{drive_url}?fields=parents", headers=headers, timeout=30)
            if get_response.status_code == 200:
                current_parents = get_response.json().get("parents", [])
                
                # Update parents (remove current, add new)
                update_params = {
                    "addParents": folder_id,
                    "removeParents": ",".join(current_parents)
                }
                
                update_response = requests.patch(drive_url, headers=headers, params=update_params, timeout=30)
                if update_response.status_code != 200:
                    raise ValueError(f"Failed to move document to folder: {update_response.text}")
            else:
                raise ValueError(f"Failed to get current parents: {get_response.text}")
                
        except Exception as e:
            logger.warning(f"Error moving document to folder: {str(e)}")

    def _extract_text_content(self, doc_data: Dict[str, Any]) -> str:
        """Extract plain text content from Google Docs document"""
        try:
            body = doc_data.get("body", {})
            content = body.get("content", [])
            
            text_parts = []
            
            for element in content:
                if "paragraph" in element:
                    paragraph = element["paragraph"]
                    paragraph_elements = paragraph.get("elements", [])
                    
                    for para_element in paragraph_elements:
                        if "textRun" in para_element:
                            text_run = para_element["textRun"]
                            content_text = text_run.get("content", "")
                            text_parts.append(content_text)
                
                elif "table" in element:
                    table = element["table"]
                    table_rows = table.get("tableRows", [])
                    
                    for row in table_rows:
                        table_cells = row.get("tableCells", [])
                        for cell in table_cells:
                            cell_content = cell.get("content", [])
                            for cell_element in cell_content:
                                if "paragraph" in cell_element:
                                    paragraph = cell_element["paragraph"]
                                    paragraph_elements = paragraph.get("elements", [])
                                    
                                    for para_element in paragraph_elements:
                                        if "textRun" in para_element:
                                            text_run = para_element["textRun"]
                                            content_text = text_run.get("content", "")
                                            text_parts.append(content_text)
                        text_parts.append("\t")  # Tab between cells
                    text_parts.append("\n")  # New line between rows
            
            return "".join(text_parts)
            
        except Exception as e:
            logger.warning(f"Error extracting text content: {str(e)}")
            return ""

    def _hex_to_rgb(self, hex_color: str) -> Dict[str, float]:
        """Convert hex color to RGB dictionary"""
        try:
            hex_color = hex_color.lstrip("#")
            length = len(hex_color)
            
            if length == 6:
                r = int(hex_color[0:2], 16)
                g = int(hex_color[2:4], 16)
                b = int(hex_color[4:6], 16)
            elif length == 3:
                r = int(hex_color[0:1] * 2, 16)
                g = int(hex_color[1:2] * 2, 16)
                b = int(hex_color[2:3] * 2, 16)
            else:
                raise ValueError("Invalid hex color format")
            
            return {"red": r / 255, "green": g / 255, "blue": b / 255}
        except Exception as e:
            logger.warning(f"Error converting hex to rgb: {str(e)}")
            return {"red": 0, "green": 0, "blue": 0}

    def trigger(self) -> List[List[NodeExecutionData]]:
        """Google Docs nodes cannot be used as triggers"""
        raise NotImplementedError("Google Docs node cannot be used as a trigger")

    def _is_valid_action(self, action_name: str, action_config: Dict[str, Any]) -> bool:
        """Check if an action has valid/meaningful configuration"""
        if not action_config:
            return False
        
        if action_name == "insertText":
            return bool(action_config.get("text", "").strip())
        
        elif action_name == "replaceAllText":
            return (bool(action_config.get("text", "").strip()) and 
                    action_config.get("replaceText") is not None)
        
        elif action_name == "insertTable":
            rows = action_config.get("rows", 2)
            columns = action_config.get("columns", 2)
            # Only valid if it's NOT the default values that appear automatically
            return not (rows == 2 and columns == 2 and 
                       action_config.get("location") == "END_OF_DOCUMENT" and 
                       action_config.get("index", 1) == 1)
        
        elif action_name == "insertBulletedList":
            items = action_config.get("items", [])
            return bool(items and len(items) > 0)
        
        elif action_name == "updateTableCellProperties":
            return bool(action_config.get("backgroundColor", "").strip())
        
        elif action_name in ["insertHeader", "insertFooter"]:
            return bool(action_config.get("text", "").strip())
        
        return False

    def _build_insert_text_requests(self, action_config: Dict[str, Any], document_id: str, headers: Dict[str, str], item_index: int = 0) -> List[Dict[str, Any]]:
        """Build insert text request with expression evaluation"""

        # Get input data and debug it first
        input_data = self.get_input_data()
        
        if input_data and len(input_data) > item_index:
            current_item = input_data[item_index]

        # actions_ui_raw = self.get_node_parameter("actionsUi", item_index, {})
        
        # text = actions_ui_raw.get("insertText", {}).get("text", "")
        # location = actions_ui_raw.get("insertText", {}).get("location", "END_OF_DOCUMENT")
        # Replace the current approach:


        # With dot notation:
        text = self.get_node_parameter("actionsUi.insertText.text", item_index, "")
        location = self.get_node_parameter("actionsUi.insertText.location", item_index, "END_OF_DOCUMENT")
        if not text:
            ValueError("Text is required for insertText action")
                    
        # Ensure we have valid text
        if not text or text is None:
            logger.warning("Google Docs - No text provided, using placeholder")
            text = "[No content available]"
        
        # Determine insertion location
        if location == "END_OF_DOCUMENT":
            insertion_location = {"location": {"index": 1}}
            # Get document length first
            try:
                doc_response = requests.get(f"{self.base_url}/documents/{document_id}", headers=headers, timeout=30)
                if doc_response.status_code == 200:
                    doc_data = doc_response.json()
                    body = doc_data.get("body", {})
                    content = body.get("content", [])
                    end_index = content[-1].get("endIndex", 1) if content else 1
                    insertion_location = {"location": {"index": end_index - 1}}
            except Exception as e:
                logger.warning(f"Google Docs - Could not get document length: {str(e)}")
    
        elif location == "START_OF_DOCUMENT":
            insertion_location = {"location": {"index": 1}}
        else:  # SPECIFIC_INDEX
            index = self.get_node_parameter("actionsUi.insertText.index", item_index, 1)
            insertion_location = {"location": {"index": index}}

        return [{
            "insertText": {
                "text": str(text),
                **insertion_location
            }
        }]

    def _build_replace_text_requests(self, action_config: Dict[str, Any], item_index: int = 0) -> List[Dict[str, Any]]:
        """Build replace all text request with expression evaluation"""
    
        search_text = self.get_node_parameter("actionsUi.replaceAllText.text", item_index, "")
        replace_text = self.get_node_parameter("actionsUi.replaceAllText.replaceText", item_index, "")
        match_case = self.get_node_parameter("actionsUi.replaceAllText.matchCase", item_index, False)
        return [{
            "replaceAllText": {
                "containsText": {
                    "text": str(search_text),
                    "matchCase": match_case
                },
                "replaceText": str(replace_text)
            }
        }]

    def _build_insert_header_requests(self, action_config: Dict[str, Any], item_index: int = 0) -> List[Dict[str, Any]]:
        """Build insert header requests with expression evaluation"""

        header_text = self.get_node_parameter("actionsUi.insertHeader.text", item_index, "")
    
        return [
            {
                "updateDocumentStyle": {
                    "documentStyle": {
                        "defaultHeaderId": "header-id"
                    },
                    "fields": "defaultHeaderId"
                }
            },
            {
                "createHeader": {
                    "headerId": "header-id",
                    "sectionBreakLocation": {"index": 1}
                }
            },
            {
                "insertText": {
                    "location": {"segmentId": "header-id", "index": 0},
                    "text": str(header_text)
                }
            }
        ]

    def _build_insert_footer_requests(self, action_config: Dict[str, Any], item_index: int = 0) -> List[Dict[str, Any]]:
        """Build insert footer requests with expression evaluation"""
    
        #actions_ui = self.get_node_parameter("actionsUi", item_index, {})
        #footer_text = actions_ui.get("insertFooter", {}).get("text", "")
        footer_text = self.get_node_parameter("actionsUi.insertFooter.text", item_index, "")
        if not footer_text:
            footer_text = "[No footer content available]"
    
        return [
            {
                "updateDocumentStyle": {
                    "documentStyle": {
                        "defaultFooterId": "footer-id"
                    },
                    "fields": "defaultFooterId"
                }
            },
            {
                "createFooter": {
                    "footerId": "footer-id",
                    "sectionBreakLocation": {"index": 1}
                }
            },
            {
                "insertText": {
                    "location": {"segmentId": "footer-id", "index": 0},
                    "text": str(footer_text)
                }
            }
        ]

    def _build_insert_list_requests(self, action_config: Dict[str, Any], document_id: str, headers: Dict[str, str], item_index: int = 0) -> List[Dict[str, Any]]:
        """Build insert bulleted list requests with expression evaluation"""
    
        actions_ui = self.get_node_parameter("actionsUi", item_index, {})
        #list_action = actions_ui.get("insertBulletedList", {})
        list_action = self.get_node_parameter("actionsUi.insertBulletedList", item_index, list_action)
    
        list_items = self.get_node_parameter("actionsUi.insertBulletedList.items", item_index, [])
        location = self.get_node_parameter("actionsUi.insertBulletedList.location", item_index, "END_OF_DOCUMENT")

        # Determine insertion location
        insertion_location = {"location": {"index": 1}}
        if location == "END_OF_DOCUMENT":
            doc_response = requests.get(f"{self.base_url}/documents/{document_id}", headers=headers, timeout=30)
            if doc_response.status_code == 200:
                doc_data = doc_response.json()
                body = doc_data.get("body", {})
                content = body.get("content", [])
                end_index = content[-1].get("endIndex", 1) if content else 1
                insertion_location = {"location": {"index": end_index - 1}}
        elif location == "START_OF_DOCUMENT":
            insertion_location = {"location": {"index": 1}}
        else:  # SPECIFIC_INDEX
            index = list_action.get("index", 1)
            insertion_location = {"location": {"index": index}}
    
        requests = []
        current_index = insertion_location["location"]["index"]
    
        # Create bullet list
        for item in list_items:
            # First insert the text
            requests.append({
                "insertText": {
                    "text": str(item) + "\n",
                    "location": {"index": current_index}
                }
            })
            
            # Then create bullet formatting
            end_index = current_index + len(str(item)) + 1
            requests.append({
                "createParagraphBullets": {
                    "range": {
                        "startIndex": current_index,
                        "endIndex": end_index
                    },
                    "bulletPreset": "BULLET_DISC"
                }
            })
            
            # Update index for next item
            current_index = end_index
    
        return requests

    def _get_nested_field_value(self, data: Dict[str, Any], field_path: str) -> Any:
        """Get nested field value using dot notation"""
        if not field_path:
            return data
    
        keys = field_path.split('.')
        current = data
    
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
    
        return current