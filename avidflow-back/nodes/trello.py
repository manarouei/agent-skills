"""
Trello node for managing boards, cards, lists, and other Trello resources
Mirrors the functionality of n8n v1 Trello node
"""
import requests
from typing import Dict, List, Optional, Any, Union
import logging

from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class TrelloNode(BaseNode):
    """
    Trello node for managing boards, cards, lists, checklists, labels, and attachments
    Implements all operations from n8n v1 Trello node
    """
    
    type = "trello"
    version = 1.0
    
    description = {
        "displayName": "Trello",
        "name": "trello",
        "icon": "file:trello.svg",
        "group": ["transform"],
        "description": "Create, change and delete boards and cards",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
    }
    
    properties = {
        "parameters": [
            # Resource selection
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "options": [
                    {"name": "Board", "value": "board"},
                    {"name": "Card", "value": "card"},
                    {"name": "List", "value": "list"},
                    {"name": "Label", "value": "label"},
                    {"name": "Checklist", "value": "checklist"},
                    {"name": "Card Comment", "value": "cardComment"},
                    {"name": "Attachment", "value": "attachment"},
                    {"name": "Board Member", "value": "boardMember"},
                ],
                "default": "card",
                "description": "The resource to operate on",
            },
            
            # ========== BOARD OPERATIONS ==========
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Create", "value": "create", "description": "Create a new board"},
                    {"name": "Delete", "value": "delete", "description": "Delete a board"},
                    {"name": "Get", "value": "get", "description": "Get the data of a board"},
                    {"name": "Update", "value": "update", "description": "Update a board"},
                ],
                "default": "create",
                "display_options": {"show": {"resource": ["board"]}},
            },
            
            # Board: Create fields
            {
                "name": "name",
                "type": NodeParameterType.STRING,
                "display_name": "Name",
                "default": "",
                "required": True,
                "description": "The name of the board",
                "display_options": {"show": {"resource": ["board"], "operation": ["create"]}},
            },
            {
                "name": "description",
                "type": NodeParameterType.STRING,
                "display_name": "Description",
                "default": "",
                "description": "The description of the board",
                "display_options": {"show": {"resource": ["board"], "operation": ["create"]}},
            },
            {
                "name": "boardId",
                "type": NodeParameterType.STRING,
                "display_name": "Board ID",
                "default": "",
                "required": True,
                "description": "The ID of the board",
                "display_options": {"show": {"resource": ["board"], "operation": ["get", "delete", "update"]}},
            },
            
            # ========== CARD OPERATIONS ==========
            {
                "name": "cardOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Create", "value": "create", "description": "Create a new card"},
                    {"name": "Delete", "value": "delete", "description": "Delete a card"},
                    {"name": "Get", "value": "get", "description": "Get the data of a card"},
                    {"name": "Update", "value": "update", "description": "Update a card"},
                ],
                "default": "create",
                "display_options": {"show": {"resource": ["card"]}},
            },
            
            # Card: Create fields
            {
                "name": "listId",
                "type": NodeParameterType.STRING,
                "display_name": "List ID",
                "default": "",
                "required": True,
                "description": "The ID of the list to create card in",
                "display_options": {"show": {"resource": ["card"], "cardOperation": ["create"]}},
            },
            {
                "name": "cardName",
                "type": NodeParameterType.STRING,
                "display_name": "Card Name",
                "default": "",
                "required": True,
                "description": "The name of the card",
                "display_options": {"show": {"resource": ["card"], "cardOperation": ["create"]}},
            },
            {
                "name": "cardDesc",
                "type": NodeParameterType.STRING,
                "display_name": "Card Description",
                "default": "",
                "description": "The description of the card",
                "display_options": {"show": {"resource": ["card"], "cardOperation": ["create"]}},
            },
            {
                "name": "cardId",
                "type": NodeParameterType.STRING,
                "display_name": "Card ID",
                "default": "",
                "required": True,
                "description": "The ID of the card",
                "display_options": {"show": {"resource": ["card"], "cardOperation": ["get", "delete", "update"]}},
            },
            {
                "name": "updateFields",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Update Fields",
                "default": {},
                "description": "Fields to update on the card",
                "display_options": {"show": {"resource": ["card"], "cardOperation": ["update"]}},
                "options": [
                    {
                        "name": "name",
                        "type": NodeParameterType.STRING,
                        "display_name": "Name",
                        "description": "New name of the card"
                    },
                    {
                        "name": "description",
                        "type": NodeParameterType.STRING,
                        "display_name": "Description",
                        "description": "New description of the card"
                    },
                    {
                        "name": "closed",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Closed",
                        "description": "Whether the card is archived/closed"
                    },
                    {
                        "name": "idBoard",
                        "type": NodeParameterType.STRING,
                        "display_name": "Board ID",
                        "description": "The ID of the board the card should be moved to"
                    },
                    {
                        "name": "idList",
                        "type": NodeParameterType.STRING,
                        "display_name": "List ID",
                        "description": "The ID of the list the card should be moved to"
                    },
                    {
                        "name": "due",
                        "type": NodeParameterType.STRING,
                        "display_name": "Due Date",
                        "description": "Due date for the card (ISO format)"
                    },
                    {
                        "name": "dueComplete",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Due Complete",
                        "description": "Whether the card is marked as complete"
                    },
                    {
                        "name": "idLabels",
                        "type": NodeParameterType.STRING,
                        "display_name": "Label IDs",
                        "description": "Comma-separated list of label IDs to add to the card"
                    },
                    {
                        "name": "idMembers",
                        "type": NodeParameterType.STRING,
                        "display_name": "Member IDs",
                        "description": "Comma-separated list of member IDs to assign to the card"
                    },
                    {
                        "name": "idAttachmentCover",
                        "type": NodeParameterType.STRING,
                        "display_name": "Attachment Cover",
                        "description": "The ID of the image attachment to use as cover"
                    },
                    {
                        "name": "pos",
                        "type": NodeParameterType.STRING,
                        "display_name": "Position",
                        "description": "Position of the card (top, bottom, or positive float)"
                    },
                    {
                        "name": "subscribed",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Subscribed",
                        "description": "Whether the current user is subscribed to the card"
                    }
                ]
            },
            
            # ========== LIST OPERATIONS ==========
            {
                "name": "listOperation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Create", "value": "create"},
                    {"name": "Get", "value": "get"},
                    {"name": "Get All", "value": "getAll"},
                    {"name": "Get Cards", "value": "getCards"},
                    {"name": "Archive", "value": "archive"},
                    {"name": "Update", "value": "update"},
                ],
                "default": "getAll",
                "display_options": {"show": {"resource": ["list"]}},
            },
            
            {
                "name": "listIdParam",
                "type": NodeParameterType.STRING,
                "display_name": "List ID",
                "default": "",
                "required": True,
                "description": "The ID of the list",
                "display_options": {"show": {"resource": ["list"]}},
            },
            {
                "name": "listName",
                "type": NodeParameterType.STRING,
                "display_name": "List Name",
                "default": "",
                "required": True,
                "description": "The name of the list",
                "display_options": {"show": {"resource": ["list"], "listOperation": ["create"]}},
            },
            
            {
                "name": "updateListName",
                "type": NodeParameterType.STRING,
                "display_name": "New List Name",
                "default": "",
                "description": "The new name of the list",
                "display_options": {"show": {"resource": ["list"], "listOperation": ["update"]}},
            },
            {
                "name": "archiveStatus",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Archive Status",
                "options": [
                    {"name": "Archive List", "value": "true"},
                    {"name": "Unarchive List", "value": "false"}
                ],
                "default": "true",
                "description": "Whether to archive or unarchive the list",
                "display_options": {"show": {"resource": ["list"], "listOperation": ["archive"]}},
            },
            # Additional options
            {
                "name": "returnAll",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Return All",
                "default": False,
                "description": "Whether to return all results",
                "display_options": {"show": {"resource": ["list"], "listOperation": ["getAll", "getCards"]}},
            },
            {
                "name": "limit",
                "type": NodeParameterType.NUMBER,
                "display_name": "Limit",
                "default": 10,
                "description": "Max number of results",
                "display_options": {"show": {"resource": ["list"], "listOperation": ["getAll", "getCards"], "returnAll": [False]}},
            },
        ],
        "credentials": [{"name": "trelloOAuth1Api", "required": True}],
    }
    
    icon = "trello.svg"
    color = "#0079bf"
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Trello operation and return properly formatted data"""
        
        try:
            input_data = self.get_input_data() #FIX
            result_items: List[NodeExecutionData] = []
            
            for i, item in enumerate(input_data):
                try:
                    resource = self.get_node_parameter("resource", i, "card")
                    
                    # Route to appropriate resource handler
                    if resource == "board":
                        result = self._handle_board(i)
                    elif resource == "card":
                        result = self._handle_card(i)
                    elif resource == "attachment":
                        result = self._handle_attachment(i)
                    elif resource == "list":
                        result = self._handle_list(i)
                    else:
                        raise ValueError(f"Unsupported resource '{resource}'")
                    
                    # Convert result to list if needed #FIX
                    if isinstance(result, list):
                        for res_item in result:
                            result_items.append(
                                NodeExecutionData(json_data=res_item, binary_data=None)
                            )
                    else:
                        result_items.append(
                            NodeExecutionData(json_data=result, binary_data=None)
                        )
                
                except Exception as e:
                    logger.error(f"Error processing item {i}: {str(e)}")
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": self.get_node_parameter("resource", i, "card"),
                            "item_index": i,
                        },
                        binary_data=None,
                    )
                    result_items.append(error_item)
            
            return [result_items]
        
        except Exception as e:
            logger.error(f"Error in Trello node: {str(e)}")
            return [[NodeExecutionData(
                json_data={"error": f"Error in Trello node: {str(e)}"},
                binary_data=None,
            )]]
    def _get_oauth_headers(self, method: str, url: str, params: Optional[Dict[str, Any]] = None, body: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Get OAuth1 authentication headers for Trello API requests
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            url: Request URL
            params: Query parameters
            body: Request body (for signature calculation)
            
        Returns:
            Dictionary with Authorization header
        """
        credentials = self.get_credentials("trelloOAuth1Api")
        if not credentials:
            raise ValueError("Trello OAuth1 credentials not found")
        
        # For Trello, we can use simpler authentication with API key and token
        # when user has already authorized the app
        api_key = credentials.get("consumerKey", "")
        api_token = credentials.get("consumerSecret", "")  # In Trello, this is the token
        
        if not api_key or not api_token:
            raise ValueError("API Key and Token are required")
        
        # Add credentials to params (Trello's simpler auth method)
        if params is None:
            params = {}
        
        params["key"] = api_key
        params["token"] = api_token
        
        return {}
    
    def _api_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        item_index: int = 0
    ) -> Any:
        """
        Make API request to Trello
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            params: Query parameters
            body: Request body
            item_index: Index for getting credentials if needed per item
            
        Returns:
            API response data
        """
        base_url = self._get_api_url()
        url = f"{base_url}/{endpoint}"
        
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        
        # Initialize params
        params = params or {}
        body = body or {}
        
        # Add authentication credentials to params
        try:
            credentials = self.get_credentials("trelloOAuth1Api")
            if not credentials:
                raise ValueError("Trello API credentials not found")
            
            # Use apiKey and apiToken fields (matching n8n's TrelloApi)
            api_key = credentials.get("apiKey", "")
            api_token = credentials.get("apiToken", "")
            
            if not api_key or not api_token:
                raise ValueError("API Key and Token are required")
            
            # Add credentials to params
            params["key"] = api_key
            params["token"] = api_token
            
            logger.info(f"Added auth params to request - key: {api_key[:10]}..., token: {api_token[:10]}...")
            
        except Exception as e:
            logger.error(f"Failed to add auth params: {e}")
            raise
        
        try:
            if method == "GET":
                response = requests.get(url, params=params, headers=headers, timeout=30)
            elif method == "POST":
                response = requests.post(url, params=params, json=body, headers=headers, timeout=30)
            elif method == "PUT":
                response = requests.put(url, params=params, json=body, headers=headers, timeout=30)
            elif method == "DELETE":
                response = requests.delete(url, params=params, headers=headers, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            # Handle different response types
            if method == "DELETE" and response.status_code in [200, 204]:
                return {"success": True}
            
            if response.content:
                return response.json()
            return {}
        
        except requests.exceptions.HTTPError as e:
            logger.error(f"Trello API HTTP error: {e}")
            logger.error(f"Request URL: {response.url if 'response' in dir() else url}")
            logger.error(f"Request params: {params}")
            raise ValueError(f"Trello API error: {e.response.text if hasattr(e, 'response') and e.response else str(e)}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Trello API request error: {e}")
            raise ValueError(f"Request failed: {str(e)}")
    
    def _get_api_url(self) -> str:
        """Get Trello API base URL"""
        return "https://api.trello.com/1"
    
    def _handle_board(self, item_index: int) -> Dict[str, Any]:
        """Handle board operations"""
        operation = self.get_node_parameter("operation", item_index, "create")
        
        if operation == "create":
            return self._create_board(item_index)
        elif operation == "delete":
            return self._delete_board(item_index)
        elif operation == "get":
            return self._get_board(item_index)
        elif operation == "update":
            return self._update_board(item_index)
        else:
            raise ValueError(f"Unsupported board operation: {operation}")
    
    def _create_board(self, item_index: int) -> Dict[str, Any]:
        """Create a new board"""
        name = self.get_node_parameter("name", item_index, "")
        desc = self.get_node_parameter("description", item_index, "")
        
        body = {
            "name": name,
            "desc": desc,
        }
        
        return self._api_request("POST", "boards", body=body, item_index=item_index)
    
    def _delete_board(self, item_index: int) -> Dict[str, Any]:
        """Delete a board"""
        board_id = self.get_node_parameter("boardId", item_index, "")
        if not board_id:
            raise ValueError("Board ID is required")
        
        return self._api_request("DELETE", f"boards/{board_id}", item_index=item_index)
    
    def _get_board(self, item_index: int) -> Dict[str, Any]:
        """Get board data"""
        board_id = self.get_node_parameter("boardId", item_index, "")
        if not board_id:
            raise ValueError("Board ID is required")
        
        try:
            return self._api_request("GET", f"boards/{board_id}", item_index=item_index)
        except ValueError as e:
            # Check if the error is a 404 (board not found)
            error_str = str(e)
            if "404" in error_str or "not found" in error_str.lower():
                raise ValueError(f"Board with ID '{board_id}' not found. Please check the board ID and try again.")
            raise
    
    def _update_board(self, item_index: int) -> Dict[str, Any]:
        """Update a board"""
        board_id = self.get_node_parameter("boardId", item_index, "")
        if not board_id:
            raise ValueError("Board ID is required")
        
        # Get update fields from parameters
        uf = self.get_node_parameter("updateFields", item_index, {}) or {}

        body = {}
        
        update_name = uf.get("name", "")
        update_desc = uf.get("description", "")
        if update_name:
            body["name"] = update_name
        
        if update_desc:
            body["desc"] = update_desc
        
        # If no update fields provided, return error
        # if not body:
            # raise ValueError("At least one update field (name or description) is required")
        
        try:
            return self._api_request("PUT", f"boards/{board_id}", body=body, item_index=item_index)
        except ValueError as e:
            # Check if the error is a 404 (board not found)
            error_str = str(e)
            if "404" in error_str or "not found" in error_str.lower():
                raise ValueError(f"Board with ID '{board_id}' not found. Please check the board ID and try again.")
            raise
    def _handle_card(self, item_index: int) -> Dict[str, Any]:
        """Handle card operations"""
        operation = self.get_node_parameter("cardOperation", item_index, "create")
        
        if operation == "create":
            return self._create_card(item_index)
        elif operation == "delete":
            return self._delete_card(item_index)
        elif operation == "get":
            return self._get_card(item_index)
        elif operation == "update":
            return self._update_card(item_index)
        else:
            raise ValueError(f"Unsupported card operation: {operation}")
    
    def _create_card(self, item_index: int) -> Dict[str, Any]:
        """Create a new card"""
        list_id = self.get_node_parameter("listId", item_index, "")
        name = self.get_node_parameter("cardName", item_index, "")
        desc = self.get_node_parameter("cardDesc", item_index, "")
        
        body = {
            "idList": list_id,
            "name": name,
            "desc": desc,
        }
        
        return self._api_request("POST", "cards", body=body, item_index=item_index)
    
    def _delete_card(self, item_index: int) -> Dict[str, Any]:
        """Delete a card"""
        card_id = self.get_node_parameter("cardId", item_index, "")
        if not card_id:
            raise ValueError("Card ID is required")
        
        return self._api_request("DELETE", f"cards/{card_id}", item_index=item_index)
    
    def _get_card(self, item_index: int) -> Dict[str, Any]:
        """Get card data"""
        card_id = self.get_node_parameter("cardId", item_index, "")
        if not card_id:
            raise ValueError("Card ID is required")
        
        return self._api_request("GET", f"cards/{card_id}", item_index=item_index)
    
    def _update_card(self, item_index: int) -> Dict[str, Any]:
        """Update a card"""
        card_id = self.get_node_parameter("cardId", item_index, "")
        uf = self.get_node_parameter("updateFields", item_index, {}) or {}

        if not card_id:
            raise ValueError("Card ID is required")
        
        # Build body from updateFields
        body = {}
        
        # Simple string fields
        if uf.get("name"):
            body["name"] = uf.get("name")
        if uf.get("description"):
            body["desc"] = uf.get("description")
        if uf.get("idBoard"):
            body["idBoard"] = uf.get("idBoard")
        if uf.get("idList"):
            body["idList"] = uf.get("idList")
        if uf.get("due"):
            body["due"] = uf.get("due")
        if uf.get("pos"):
            body["pos"] = uf.get("pos")
        if uf.get("idAttachmentCover"):
            body["idAttachmentCover"] = uf.get("idAttachmentCover")
        
        # Boolean fields
        if "closed" in uf:
            body["closed"] = uf.get("closed")
        if "dueComplete" in uf:
            body["dueComplete"] = uf.get("dueComplete")
        if "subscribed" in uf:
            body["subscribed"] = uf.get("subscribed")
        
        # Handle comma-separated lists
        if uf.get("idLabels"):
            labels = uf.get("idLabels", "")
            body["idLabels"] = [label.strip() for label in labels.split(",") if label.strip()]
        
        if uf.get("idMembers"):
            members = uf.get("idMembers", "")
            body["idMembers"] = [member.strip() for member in members.split(",") if member.strip()]
        
        return self._api_request("PUT", f"cards/{card_id}", body=body, item_index=item_index)
    def _handle_attachment(self, item_index: int) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Handle attachment operations"""
        operation = self.get_node_parameter("attachmentOperation", item_index, "getAll")
        
        if operation == "create":
            return self._create_attachment(item_index)
        elif operation == "delete":
            return self._delete_attachment(item_index)
        elif operation == "get":
            return self._get_attachment(item_index)
        elif operation == "getAll":
            return self._get_all_attachments(item_index)
        else:
            raise ValueError(f"Unsupported attachment operation: {operation}")

    def _create_attachment(self, item_index: int) -> Dict[str, Any]:
        """Create a new attachment"""
        card_id = self.get_node_parameter("attachmentCardId", item_index, "")
        if not card_id:
            raise ValueError("Card ID is required")
        
        url = self.get_node_parameter("attachmentUrl", item_index, "")
        uf = self.get_node_parameter("additionalFields", item_index, "")
        
        if not url:
            raise ValueError("URL is required")
        
        body = {"url": url}
        
        # Optional fields #FIX LIKE GMAIN BINARY HANDLING
        name = uf.get("name", "")
        mime_type = uf.get("mimeType", "")
        
        if name:
            body["name"] = name
        if mime_type:
            body["mimeType"] = mime_type
        
        return self._api_request("POST", f"cards/{card_id}/attachments", body=body, item_index=item_index)

    def _delete_attachment(self, item_index: int) -> Dict[str, Any]:
        """Delete an attachment"""
        card_id = self.get_node_parameter("attachmentCardId", item_index, "")
        attachment_id = self.get_node_parameter("attachmentId", item_index, "")
        
        if not card_id or not attachment_id:
            raise ValueError("Card ID and Attachment ID are required")
        
        return self._api_request("DELETE", f"cards/{card_id}/attachments/{attachment_id}", item_index=item_index)

    def _get_attachment(self, item_index: int) -> Dict[str, Any]:
        """Get attachment data"""
        card_id = self.get_node_parameter("attachmentCardId", item_index, "")
        attachment_id = self.get_node_parameter("attachmentId", item_index, "")
        
        if not card_id or not attachment_id:
            raise ValueError("Card ID and Attachment ID are required")
        
        params = {}
        fields = self.get_node_parameter("attachmentFields", item_index, "all")
        if fields and fields != "all":
            params["fields"] = fields
        
        return self._api_request("GET", f"cards/{card_id}/attachments/{attachment_id}", params=params, item_index=item_index)

    def _get_all_attachments(self, item_index: int) -> List[Dict[str, Any]]:
        """Get all attachments for a card"""
        card_id = self.get_node_parameter("attachmentCardId", item_index, "")
        if not card_id:
            raise ValueError("Card ID is required")
        
        params = {}
        fields = self.get_node_parameter("attachmentFields", item_index, "all")
        if fields and fields != "all":
            params["fields"] = fields
        
        result = self._api_request("GET", f"cards/{card_id}/attachments", params=params, item_index=item_index)
        
        return result if isinstance(result, list) else []
    def _handle_list(self, item_index: int) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        """Handle list operations"""
        operation = self.get_node_parameter("listOperation", item_index, "getAll")
        
        if operation == "create":
            return self._create_list(item_index)
        elif operation == "get":
            return self._get_list(item_index)
        elif operation == "getAll":
            return self._get_all_lists(item_index)
        elif operation == "getCards":
            return self._get_list_cards(item_index)
        elif operation == "archive":
            return self._archive_list(item_index)
        elif operation == "update":
            return self._update_list(item_index)
        else:
            raise ValueError(f"Unsupported list operation: {operation}")
    
    def _create_list(self, item_index: int) -> Dict[str, Any]:
        """Create a new list"""
        board_id = self.get_node_parameter("boardId", item_index, "")
        name = self.get_node_parameter("listName", item_index, "")
        
        if not board_id:
            raise ValueError("Board ID is required")
        
        body = {
            "idBoard": board_id,
            "name": name,
        }
        
        return self._api_request("POST", "lists", body=body, item_index=item_index)
    
    def _get_list(self, item_index: int) -> Dict[str, Any]:
        """Get list data"""
        list_id = self.get_node_parameter("listIdParam", item_index, "")
        if not list_id:
            raise ValueError("List ID is required")
        
        return self._api_request("GET", f"lists/{list_id}", item_index=item_index)
    
    def _get_all_lists(self, item_index: int) -> List[Dict[str, Any]]:
        """Get all lists for a board"""
        board_id = self.get_node_parameter("boardId", item_index, "")
        if not board_id:
            raise ValueError("Board ID is required")
        
        return_all = self.get_node_parameter("returnAll", item_index, False)
        limit = None if return_all else self.get_node_parameter("limit", item_index, 10)
        
        result = self._api_request("GET", f"boards/{board_id}/lists", item_index=item_index)
        
        if not return_all and limit and isinstance(result, list):
            result = result[:limit]
        
        return result if isinstance(result, list) else []
    
    def _get_list_cards(self, item_index: int) -> List[Dict[str, Any]]:
        """Get all cards in a list"""
        list_id = self.get_node_parameter("listIdParam", item_index, "")
        if not list_id:
            raise ValueError("List ID is required")
        
        return_all = self.get_node_parameter("returnAll", item_index, False)
        limit = None if return_all else self.get_node_parameter("limit", item_index, 10)
        
        result = self._api_request("GET", f"lists/{list_id}/cards", item_index=item_index)
        
        if not return_all and limit and isinstance(result, list):
            result = result[:limit]
        
        return result if isinstance(result, list) else []
    
    def _archive_list(self, item_index: int) -> Dict[str, Any]:
        """Archive/unarchive a list"""
        list_id = self.get_node_parameter("listIdParam", item_index, "")
        if not list_id:
            raise ValueError("List ID is required")
        
        # Get archive status from parameter
        archive_status = self.get_node_parameter("archiveStatus", item_index, "true")
        body = {"value": archive_status}
        
        return self._api_request("PUT", f"lists/{list_id}/closed", body=body, item_index=item_index)
    
    def _update_list(self, item_index: int) -> Dict[str, Any]:
        """Update a list"""
        list_id = self.get_node_parameter("listIdParam", item_index, "")
        if not list_id:
            raise ValueError("List ID is required")
        
        # Get update fields from parameters
        uf = self.get_node_parameter("updateFields", item_index, {}) or {}

        # summary     = uf.get("summary", "")
        body = {}
        
        update_name = uf.get("name", "")
        if update_name:
            body["name"] = update_name
        
        # If no update fields provided, return error
        if not body:
            raise ValueError("At least one update field (name) is required")
        
        return self._api_request("PUT", f"lists/{list_id}", body=body, item_index=item_index)