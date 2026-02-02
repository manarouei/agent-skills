"""
Slack node for Slack API operations.
Based on n8n's SlackV2 node implementation.

Supported Resources:
- Message: Send, update, delete, search messages
- Channel: Create, archive, get, list, invite, kick, join, leave, rename channels
- File: Upload, get, list files
- Reaction: Add, get, remove reactions
- Star: Add, delete, get starred items
- User: Get user info, list users, get presence, get/update profile
- User Group: Create, enable, disable, update, list user groups
"""
import requests
import json
import logging
import io
from typing import Dict, List, Optional, Any
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class SlackNode(BaseNode):
    """
    Slack node for interacting with Slack API
    """

    type = "slack"
    version = 2

    description = {
        "displayName": "Slack",
        "name": "slack",
        "icon": "file:slack.svg",
        "group": ["output"],
        "description": "Consume Slack API",
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
                    {"name": "Channel", "value": "channel"},
                    {"name": "File", "value": "file"},
                    {"name": "Message", "value": "message"},
                    {"name": "Reaction", "value": "reaction"},
                    {"name": "Star", "value": "star"},
                    {"name": "User", "value": "user"},
                    {"name": "User Group", "value": "userGroup"},
                ],
                "default": "message",
                "description": "The resource to operate on",
            },
            
            # ============ MESSAGE OPERATIONS ============
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Delete", "value": "delete", "description": "Delete a message"},
                    {"name": "Get Permalink", "value": "getPermalink", "description": "Get a message permalink"},
                    {"name": "Search", "value": "search", "description": "Search for messages"},
                    {"name": "Send", "value": "post", "description": "Send a message"},
                    {"name": "Update", "value": "update", "description": "Update a message"},
                ],
                "default": "post",
                "display_options": {"show": {"resource": ["message"]}},
            },
            
            # Message: Send/Post
            {
                "name": "select",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Send Message To",
                "options": [
                    {"name": "Channel", "value": "channel"},
                    {"name": "User", "value": "user"},
                ],
                "default": "channel",
                "display_options": {"show": {"resource": ["message"], "operation": ["post"]}},
            },
            {
                "name": "channelId",
                "type": NodeParameterType.STRING,
                "display_name": "Channel",
                "default": "",
                "required": True,
                "description": "The Slack channel ID or name (e.g., C1234567890 or #general)",
                "display_options": {"show": {"resource": ["message"], "operation": ["post"], "select": ["channel"]}},
            },
            {
                "name": "user",
                "type": NodeParameterType.STRING,
                "display_name": "User",
                "default": "",
                "required": True,
                "description": "The Slack user ID or username (e.g., U1234567890 or @username)",
                "display_options": {"show": {"resource": ["message"], "operation": ["post"], "select": ["user"]}},
            },
            {
                "name": "messageType",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Message Type",
                "options": [
                    {"name": "Simple Text Message", "value": "text"},
                    {"name": "Blocks", "value": "block"},
                    {"name": "Attachments", "value": "attachment"},
                ],
                "default": "text",
                "display_options": {"show": {"resource": ["message"], "operation": ["post"]}},
            },
            {
                "name": "text",
                "type": NodeParameterType.STRING,
                "display_name": "Message Text",
                "default": "",
                "required": True,
                "description": "The message text to post. Supports markdown by default.",
                "display_options": {"show": {"resource": ["message"], "operation": ["post"], "messageType": ["text"]}},
            },
            {
                "name": "blocksUi",
                "type": NodeParameterType.STRING,
                "display_name": "Blocks",
                "default": "",
                "required": True,
                "description": "JSON output from Slack's Block Kit Builder",
                "display_options": {"show": {"resource": ["message"], "operation": ["post"], "messageType": ["block"]}},
            },
            
            # Message: Update
            {
                "name": "channelId",
                "type": NodeParameterType.STRING,
                "display_name": "Channel",
                "default": "",
                "required": True,
                "description": "The Slack channel ID",
                "display_options": {"show": {"resource": ["message"], "operation": ["update", "getPermalink"]}},
            },
            {
                "name": "ts",
                "type": NodeParameterType.STRING,
                "display_name": "Message Timestamp",
                "default": "",
                "required": True,
                "description": "Timestamp of the message (e.g., 1663233118.856619)",
                "display_options": {"show": {"resource": ["message"], "operation": ["update", "getPermalink"]}},
            },
            {
                "name": "text",
                "type": NodeParameterType.STRING,
                "display_name": "Message Text",
                "default": "",
                "description": "The updated message text",
                "display_options": {"show": {"resource": ["message"], "operation": ["update"]}},
            },
            
            # Message: Delete
            {
                "name": "select",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Delete Message From",
                "options": [
                    {"name": "Channel", "value": "channel"},
                    {"name": "User", "value": "user"},
                ],
                "default": "channel",
                "display_options": {"show": {"resource": ["message"], "operation": ["delete"]}},
            },
            {
                "name": "channelId",
                "type": NodeParameterType.STRING,
                "display_name": "Channel",
                "default": "",
                "required": True,
                "display_options": {"show": {"resource": ["message"], "operation": ["delete"], "select": ["channel"]}},
            },
            {
                "name": "user",
                "type": NodeParameterType.STRING,
                "display_name": "User",
                "default": "",
                "required": True,
                "display_options": {"show": {"resource": ["message"], "operation": ["delete"], "select": ["user"]}},
            },
            {
                "name": "timestamp",
                "type": NodeParameterType.STRING,
                "display_name": "Message Timestamp",
                "default": "",
                "required": True,
                "display_options": {"show": {"resource": ["message"], "operation": ["delete"]}},
            },
            
            # Message: Search
            {
                "name": "query",
                "type": NodeParameterType.STRING,
                "display_name": "Search Query",
                "default": "",
                "required": True,
                "description": "The text to search for within messages",
                "display_options": {"show": {"resource": ["message"], "operation": ["search"]}},
            },
            {
                "name": "returnAll",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Return All",
                "default": False,
                "display_options": {"show": {"resource": ["message"], "operation": ["search"]}},
            },
            {
                "name": "limit",
                "type": NodeParameterType.NUMBER,
                "display_name": "Limit",
                "default": 25,
                "display_options": {"show": {"resource": ["message"], "operation": ["search"], "returnAll": [False]}},
            },
            
            # ============ CHANNEL OPERATIONS ============
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Archive", "value": "archive"},
                    {"name": "Create", "value": "create"},
                    {"name": "Get", "value": "get"},
                    {"name": "Get Many", "value": "getAll"},
                    {"name": "History", "value": "history"},
                    {"name": "Invite", "value": "invite"},
                    {"name": "Join", "value": "join"},
                    {"name": "Kick", "value": "kick"},
                    {"name": "Leave", "value": "leave"},
                    {"name": "Rename", "value": "rename"},
                ],
                "default": "create",
                "display_options": {"show": {"resource": ["channel"]}},
            },
            {
                "name": "channelId",
                "type": NodeParameterType.STRING,
                "display_name": "Channel",
                "default": "",
                "required": True,
                "display_options": {"show": {"resource": ["channel"], "operation": ["archive", "get", "history", "invite", "join", "kick", "leave", "rename"]}},
            },
            {
                "name": "name",
                "type": NodeParameterType.STRING,
                "display_name": "Name",
                "default": "",
                "required": True,
                "display_options": {"show": {"resource": ["channel"], "operation": ["create", "rename"]}},
            },
            {
                "name": "userIds",
                "type": NodeParameterType.STRING,
                "display_name": "User IDs",
                "default": "",
                "description": "Comma-separated user IDs to invite or kick",
                "display_options": {"show": {"resource": ["channel"], "operation": ["invite", "kick"]}},
            },
            
            # ============ FILE OPERATIONS ============
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Get", "value": "get"},
                    {"name": "Get Many", "value": "getAll"},
                    {"name": "Upload", "value": "upload"},
                ],
                "default": "upload",
                "display_options": {"show": {"resource": ["file"]}},
            },
            {
                "name": "binaryData",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Binary File",
                "default": True,
                "description": "Whether to upload from binary data",
                "display_options": {"show": {"resource": ["file"], "operation": ["upload"]}},
            },
            {
                "name": "binaryPropertyName",
                "type": NodeParameterType.STRING,
                "display_name": "Binary Property Name",
                "default": "data",
                "required": True,
                "display_options": {"show": {"resource": ["file"], "operation": ["upload"], "binaryData": [True]}},
            },
            {
                "name": "channelId",
                "type": NodeParameterType.STRING,
                "display_name": "Channel",
                "default": "",
                "description": "Channel to send the file to",
                "display_options": {"show": {"resource": ["file"], "operation": ["upload"]}},
            },
            {
                "name": "fileName",
                "type": NodeParameterType.STRING,
                "display_name": "File Name",
                "default": "",
                "display_options": {"show": {"resource": ["file"], "operation": ["upload"]}},
            },
            {
                "name": "fileId",
                "type": NodeParameterType.STRING,
                "display_name": "File ID",
                "default": "",
                "required": True,
                "display_options": {"show": {"resource": ["file"], "operation": ["get"]}},
            },
            
            # ============ REACTION OPERATIONS ============
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Add", "value": "add"},
                    {"name": "Get", "value": "get"},
                    {"name": "Remove", "value": "remove"},
                ],
                "default": "add",
                "display_options": {"show": {"resource": ["reaction"]}},
            },
            {
                "name": "channelId",
                "type": NodeParameterType.STRING,
                "display_name": "Channel",
                "default": "",
                "required": True,
                "display_options": {"show": {"resource": ["reaction"]}},
            },
            {
                "name": "timestamp",
                "type": NodeParameterType.STRING,
                "display_name": "Message Timestamp",
                "default": "",
                "required": True,
                "display_options": {"show": {"resource": ["reaction"]}},
            },
            {
                "name": "name",
                "type": NodeParameterType.STRING,
                "display_name": "Emoji Code",
                "default": "",
                "required": True,
                "description": "Emoji code like +1, not an actual emoji",
                "display_options": {"show": {"resource": ["reaction"], "operation": ["add", "remove"]}},
            },
            
            # ============ STAR OPERATIONS ============
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Add", "value": "add"},
                    {"name": "Delete", "value": "delete"},
                    {"name": "Get Many", "value": "getAll"},
                ],
                "default": "add",
                "display_options": {"show": {"resource": ["star"]}},
            },
            
            # ============ USER OPERATIONS ============
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Get", "value": "info"},
                    {"name": "Get Many", "value": "getAll"},
                    {"name": "Get Presence", "value": "getPresence"},
                    {"name": "Get Profile", "value": "getProfile"},
                    {"name": "Update Profile", "value": "updateProfile"},
                ],
                "default": "info",
                "display_options": {"show": {"resource": ["user"]}},
            },
            {
                "name": "user",
                "type": NodeParameterType.STRING,
                "display_name": "User",
                "default": "",
                "required": True,
                "display_options": {"show": {"resource": ["user"], "operation": ["info", "getPresence", "getProfile"]}},
            },
            
            # ============ USER GROUP OPERATIONS ============
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Create", "value": "create"},
                    {"name": "Disable", "value": "disable"},
                    {"name": "Enable", "value": "enable"},
                    {"name": "Get Many", "value": "getAll"},
                    {"name": "Update", "value": "update"},
                ],
                "default": "create",
                "display_options": {"show": {"resource": ["userGroup"]}},
            },
            {
                "name": "name",
                "type": NodeParameterType.STRING,
                "display_name": "Name",
                "default": "",
                "required": True,
                "display_options": {"show": {"resource": ["userGroup"], "operation": ["create"]}},
            },
            {
                "name": "userGroupId",
                "type": NodeParameterType.STRING,
                "display_name": "User Group ID",
                "default": "",
                "required": True,
                "display_options": {"show": {"resource": ["userGroup"], "operation": ["disable", "enable", "update"]}},
            },
        ],
        "credentials": [
            {"name": "slackApi", "required": False},
            {"name": "slackOAuth2Api", "required": False},
        ],
    }

    icon = "slack.svg"
    color = "#4A154B"

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Slack operation and return properly formatted data"""
        try:
            input_data = self.get_input_data()
            result_items: List[NodeExecutionData] = []

            # Process each input item
            for i, item in enumerate(input_data):
                try:
                    resource = self.get_node_parameter("resource", i, "message")
                    operation = self.get_node_parameter("operation", i, "post")

                    # Route to appropriate handler
                    if resource == "message":
                        result = self._handle_message(i, operation)
                    elif resource == "channel":
                        result = self._handle_channel(i, operation)
                    elif resource == "file":
                        result = self._handle_file(i, operation)
                    elif resource == "reaction":
                        result = self._handle_reaction(i, operation)
                    elif resource == "star":
                        result = self._handle_star(i, operation)
                    elif resource == "user":
                        result = self._handle_user(i, operation)
                    elif resource == "userGroup":
                        result = self._handle_user_group(i, operation)
                    else:
                        raise ValueError(f"Unsupported resource: {resource}")

                    # Add result to items
                    if isinstance(result, list):
                        for res_item in result:
                            result_items.append(NodeExecutionData(json_data=res_item, binary_data=None))
                    else:
                        result_items.append(NodeExecutionData(json_data=result, binary_data=None))

                except Exception as e:
                    logger.error(f"Error processing item {i}: {str(e)}")
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": self.get_node_parameter("resource", i, "message"),
                            "operation": self.get_node_parameter("operation", i, ""),
                            "item_index": i,
                        },
                        binary_data=None,
                    )
                    result_items.append(error_item)

            return [result_items]

        except Exception as e:
            logger.error(f"Error in Slack node: {str(e)}")
            error_data = [
                NodeExecutionData(
                    json_data={"error": f"Error in Slack node: {str(e)}"},
                    binary_data=None,
                )
            ]
            return [error_data]

    def _get_api_headers(self) -> Dict[str, str]:
        """
        Get headers for Slack API requests.
        
        Supports both slackApi (token-based) and slackOAuth2Api (OAuth2) credentials.
        """
        access_token = None
        
        # Try OAuth2 credentials first (preferred)
        try:
            oauth2_credentials = self.get_credentials("slackOAuth2Api")
            if oauth2_credentials:
                # Get token from OAuth2 token data
                oauth_token_data = oauth2_credentials.get("oauthTokenData", {})
                if oauth_token_data:
                    # Prefer bot token, fall back to user token
                    access_token = (
                        oauth_token_data.get("access_token") or
                        oauth_token_data.get("bot_token") or
                        oauth_token_data.get("user_access_token")
                    )
        except Exception:
            pass
        
        # Fall back to simple API credentials
        if not access_token:
            try:
                api_credentials = self.get_credentials("slackApi")
                if api_credentials:
                    access_token = api_credentials.get("accessToken")
            except Exception:
                pass
        
        if not access_token:
            raise ValueError("Slack credentials not found. Please configure either slackApi or slackOAuth2Api credentials.")

        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=utf-8"
        }

    def _slack_api_request(
        self, method: str, endpoint: str, body: Optional[Dict] = None, qs: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make a request to the Slack API
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., /chat.postMessage)
            body: Request body
            qs: Query string parameters
            
        Returns:
            API response data
        """
        url = f"https://slack.com/api{endpoint}"
        headers = self._get_api_headers()
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=qs, timeout=30)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=body, params=qs, timeout=30)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            data = response.json()
            
            # Check for Slack API errors
            if not data.get("ok", False):
                error_msg = data.get("error", "Unknown error")
                raise ValueError(f"Slack API error: {error_msg}")
            
            return data
            
        except requests.RequestException as e:
            raise ValueError(f"HTTP error: {str(e)}")

    # ============ MESSAGE HANDLERS ============
    
    def _handle_message(self, item_index: int, operation: str) -> Any:
        """Handle message operations"""
        if operation == "post":
            return self._message_post(item_index)
        elif operation == "update":
            return self._message_update(item_index)
        elif operation == "delete":
            return self._message_delete(item_index)
        elif operation == "getPermalink":
            return self._message_get_permalink(item_index)
        elif operation == "search":
            return self._message_search(item_index)
        else:
            raise ValueError(f"Unsupported message operation: {operation}")

    def _message_post(self, item_index: int) -> Dict[str, Any]:
        """Send a message to Slack"""
        select = self.get_node_parameter("select", item_index, "channel")
        message_type = self.get_node_parameter("messageType", item_index, "text")
        
        # Get target (channel or user)
        if select == "channel":
            target = self.get_node_parameter("channelId", item_index, "")
        else:
            target = self.get_node_parameter("user", item_index, "")
        
        if not target:
            raise ValueError(f"Target {select} is required")
        
        # Build message body
        body = {"channel": target}
        
        if message_type == "text":
            text = self.get_node_parameter("text", item_index, "")
            if not text:
                raise ValueError("Message text is required")
            body["text"] = text
        elif message_type == "block":
            blocks_json = self.get_node_parameter("blocksUi", item_index, "")
            if not blocks_json:
                raise ValueError("Blocks JSON is required")
            try:
                blocks = json.loads(blocks_json) if isinstance(blocks_json, str) else blocks_json
                body["blocks"] = blocks
                # Optional notification text for blocks
                notification_text = self.get_node_parameter("text", item_index, "")
                if notification_text:
                    body["text"] = notification_text
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON in blocks")
        
        # Make API request
        response = self._slack_api_request("POST", "/chat.postMessage", body)
        return response.get("message", response)

    def _message_update(self, item_index: int) -> Dict[str, Any]:
        """Update a message"""
        channel = self.get_node_parameter("channelId", item_index, "")
        ts = self.get_node_parameter("ts", item_index, "")
        text = self.get_node_parameter("text", item_index, "")
        
        if not channel or not ts:
            raise ValueError("Channel and timestamp are required")
        
        body = {
            "channel": channel,
            "ts": ts,
            "text": text
        }
        
        response = self._slack_api_request("POST", "/chat.update", body)
        return response.get("message", response)

    def _message_delete(self, item_index: int) -> Dict[str, Any]:
        """Delete a message"""
        select = self.get_node_parameter("select", item_index, "channel")
        timestamp = self.get_node_parameter("timestamp", item_index, "")
        
        if select == "channel":
            channel = self.get_node_parameter("channelId", item_index, "")
        else:
            channel = self.get_node_parameter("user", item_index, "")
        
        if not channel or not timestamp:
            raise ValueError("Channel and timestamp are required")
        
        body = {
            "channel": channel,
            "ts": timestamp
        }
        
        response = self._slack_api_request("POST", "/chat.delete", body)
        return {"ok": response.get("ok"), "channel": channel, "ts": timestamp}

    def _message_get_permalink(self, item_index: int) -> Dict[str, Any]:
        """Get a message permalink"""
        channel = self.get_node_parameter("channelId", item_index, "")
        ts = self.get_node_parameter("ts", item_index, "")
        
        if not channel or not ts:
            raise ValueError("Channel and timestamp are required")
        
        qs = {
            "channel": channel,
            "message_ts": ts
        }
        
        response = self._slack_api_request("GET", "/chat.getPermalink", qs=qs)
        return {"permalink": response.get("permalink"), "channel": channel, "message_ts": ts}

    def _message_search(self, item_index: int) -> List[Dict[str, Any]]:
        """Search for messages"""
        query = self.get_node_parameter("query", item_index, "")
        return_all = self.get_node_parameter("returnAll", item_index, False)
        limit = self.get_node_parameter("limit", item_index, 25) if not return_all else 100
        
        if not query:
            raise ValueError("Search query is required")
        
        qs = {
            "query": query,
            "count": limit,
            "sort": "timestamp",
            "sort_dir": "desc"
        }
        
        response = self._slack_api_request("GET", "/search.messages", qs=qs)
        messages = response.get("messages", {}).get("matches", [])
        
        return messages

    # ============ CHANNEL HANDLERS ============
    
    def _handle_channel(self, item_index: int, operation: str) -> Any:
        """Handle channel operations"""
        if operation == "create":
            return self._channel_create(item_index)
        elif operation == "archive":
            return self._channel_archive(item_index)
        elif operation == "get":
            return self._channel_get(item_index)
        elif operation == "getAll":
            return self._channel_get_all(item_index)
        elif operation == "history":
            return self._channel_history(item_index)
        elif operation == "invite":
            return self._channel_invite(item_index)
        elif operation == "join":
            return self._channel_join(item_index)
        elif operation == "kick":
            return self._channel_kick(item_index)
        elif operation == "leave":
            return self._channel_leave(item_index)
        elif operation == "rename":
            return self._channel_rename(item_index)
        else:
            raise ValueError(f"Unsupported channel operation: {operation}")

    def _channel_create(self, item_index: int) -> Dict[str, Any]:
        """Create a new channel"""
        name = self.get_node_parameter("name", item_index, "")
        if not name:
            raise ValueError("Channel name is required")
        
        # Remove # if present
        name = name.lstrip("#")
        
        body = {"name": name}
        response = self._slack_api_request("POST", "/conversations.create", body)
        return response.get("channel", response)

    def _channel_archive(self, item_index: int) -> Dict[str, Any]:
        """Archive a channel"""
        channel = self.get_node_parameter("channelId", item_index, "")
        if not channel:
            raise ValueError("Channel ID is required")
        
        body = {"channel": channel}
        response = self._slack_api_request("POST", "/conversations.archive", body)
        return {"ok": response.get("ok"), "channel": channel}

    def _channel_get(self, item_index: int) -> Dict[str, Any]:
        """Get channel information"""
        channel = self.get_node_parameter("channelId", item_index, "")
        if not channel:
            raise ValueError("Channel ID is required")
        
        qs = {"channel": channel}
        response = self._slack_api_request("GET", "/conversations.info", qs=qs)
        return response.get("channel", response)

    def _channel_get_all(self, item_index: int) -> List[Dict[str, Any]]:
        """Get all channels"""
        # TODO: Implement pagination support
        qs = {"types": "public_channel,private_channel", "limit": 100}
        response = self._slack_api_request("GET", "/conversations.list", qs=qs)
        return response.get("channels", [])

    def _channel_history(self, item_index: int) -> List[Dict[str, Any]]:
        """Get channel message history"""
        channel = self.get_node_parameter("channelId", item_index, "")
        if not channel:
            raise ValueError("Channel ID is required")
        
        qs = {"channel": channel, "limit": 100}
        response = self._slack_api_request("GET", "/conversations.history", qs=qs)
        return response.get("messages", [])

    def _channel_invite(self, item_index: int) -> Dict[str, Any]:
        """Invite users to a channel"""
        channel = self.get_node_parameter("channelId", item_index, "")
        user_ids = self.get_node_parameter("userIds", item_index, "")
        
        if not channel or not user_ids:
            raise ValueError("Channel and user IDs are required")
        
        body = {"channel": channel, "users": user_ids}
        response = self._slack_api_request("POST", "/conversations.invite", body)
        return response.get("channel", response)

    def _channel_join(self, item_index: int) -> Dict[str, Any]:
        """Join a channel"""
        channel = self.get_node_parameter("channelId", item_index, "")
        if not channel:
            raise ValueError("Channel ID is required")
        
        body = {"channel": channel}
        response = self._slack_api_request("POST", "/conversations.join", body)
        return response.get("channel", response)

    def _channel_kick(self, item_index: int) -> Dict[str, Any]:
        """Kick a user from a channel"""
        channel = self.get_node_parameter("channelId", item_index, "")
        user_id = self.get_node_parameter("userIds", item_index, "")
        
        if not channel or not user_id:
            raise ValueError("Channel and user ID are required")
        
        body = {"channel": channel, "user": user_id}
        response = self._slack_api_request("POST", "/conversations.kick", body)
        return {"ok": response.get("ok"), "channel": channel}

    def _channel_leave(self, item_index: int) -> Dict[str, Any]:
        """Leave a channel"""
        channel = self.get_node_parameter("channelId", item_index, "")
        if not channel:
            raise ValueError("Channel ID is required")
        
        body = {"channel": channel}
        response = self._slack_api_request("POST", "/conversations.leave", body)
        return {"ok": response.get("ok"), "channel": channel}

    def _channel_rename(self, item_index: int) -> Dict[str, Any]:
        """Rename a channel"""
        channel = self.get_node_parameter("channelId", item_index, "")
        name = self.get_node_parameter("name", item_index, "")
        
        if not channel or not name:
            raise ValueError("Channel ID and name are required")
        
        body = {"channel": channel, "name": name}
        response = self._slack_api_request("POST", "/conversations.rename", body)
        return response.get("channel", response)

    # ============ FILE HANDLERS ============
    
    def _handle_file(self, item_index: int, operation: str) -> Any:
        """Handle file operations"""
        if operation == "upload":
            return self._file_upload(item_index)
        elif operation == "get":
            return self._file_get(item_index)
        elif operation == "getAll":
            return self._file_get_all(item_index)
        else:
            raise ValueError(f"Unsupported file operation: {operation}")

    def _file_upload(self, item_index: int) -> Dict[str, Any]:
        """Upload a file to Slack"""
        binary_data = self.get_node_parameter("binaryData", item_index, True)
        channel = self.get_node_parameter("channelId", item_index, "")
        file_name = self.get_node_parameter("fileName", item_index, "file")
        
        if binary_data:
            # Get binary data from input
            input_items = self.get_input_data() or []
            current = input_items[item_index] if 0 <= item_index < len(input_items) else None
            
            if not current or not current.binary_data:
                raise ValueError("No binary data found on input")
            
            binary_property = self.get_node_parameter("binaryPropertyName", item_index, "data")
            binary_entry = current.binary_data.get(binary_property)
            
            if not binary_entry:
                raise ValueError(f"Binary property '{binary_property}' not found")
            
            # Extract binary content
            file_content = self._binary_entry_to_bytes(binary_entry)
            file_name = binary_entry.get("fileName", file_name)
            mime_type = binary_entry.get("mimeType", "application/octet-stream")
            
            # TODO: Implement file upload using files.upload endpoint
            # For now, return a placeholder
            return {
                "ok": True,
                "file": {
                    "name": file_name,
                    "size": len(file_content),
                    "mimetype": mime_type
                },
                "message": "File upload not yet fully implemented - TODO"
            }
        else:
            raise ValueError("File content is required")

    def _file_get(self, item_index: int) -> Dict[str, Any]:
        """Get file information"""
        file_id = self.get_node_parameter("fileId", item_index, "")
        if not file_id:
            raise ValueError("File ID is required")
        
        qs = {"file": file_id}
        response = self._slack_api_request("GET", "/files.info", qs=qs)
        return response.get("file", response)

    def _file_get_all(self, item_index: int) -> List[Dict[str, Any]]:
        """Get all files"""
        qs = {"count": 100}
        response = self._slack_api_request("GET", "/files.list", qs=qs)
        return response.get("files", [])

    def _binary_entry_to_bytes(self, entry: Dict[str, Any]) -> bytes:
        """Convert binary entry to bytes"""
        import base64
        data = entry.get("data", "")
        if isinstance(data, str):
            return base64.b64decode(data)
        return data

    # ============ REACTION HANDLERS ============
    
    def _handle_reaction(self, item_index: int, operation: str) -> Any:
        """Handle reaction operations"""
        if operation == "add":
            return self._reaction_add(item_index)
        elif operation == "get":
            return self._reaction_get(item_index)
        elif operation == "remove":
            return self._reaction_remove(item_index)
        else:
            raise ValueError(f"Unsupported reaction operation: {operation}")

    def _reaction_add(self, item_index: int) -> Dict[str, Any]:
        """Add a reaction to a message"""
        channel = self.get_node_parameter("channelId", item_index, "")
        timestamp = self.get_node_parameter("timestamp", item_index, "")
        name = self.get_node_parameter("name", item_index, "")
        
        if not all([channel, timestamp, name]):
            raise ValueError("Channel, timestamp, and emoji name are required")
        
        body = {
            "channel": channel,
            "timestamp": timestamp,
            "name": name.lstrip(":")
        }
        
        response = self._slack_api_request("POST", "/reactions.add", body)
        return {"ok": response.get("ok"), "reaction": name}

    def _reaction_get(self, item_index: int) -> Dict[str, Any]:
        """Get reactions for a message"""
        channel = self.get_node_parameter("channelId", item_index, "")
        timestamp = self.get_node_parameter("timestamp", item_index, "")
        
        if not all([channel, timestamp]):
            raise ValueError("Channel and timestamp are required")
        
        qs = {"channel": channel, "timestamp": timestamp}
        response = self._slack_api_request("GET", "/reactions.get", qs=qs)
        return response

    def _reaction_remove(self, item_index: int) -> Dict[str, Any]:
        """Remove a reaction from a message"""
        channel = self.get_node_parameter("channelId", item_index, "")
        timestamp = self.get_node_parameter("timestamp", item_index, "")
        name = self.get_node_parameter("name", item_index, "")
        
        if not all([channel, timestamp, name]):
            raise ValueError("Channel, timestamp, and emoji name are required")
        
        body = {
            "channel": channel,
            "timestamp": timestamp,
            "name": name.lstrip(":")
        }
        
        response = self._slack_api_request("POST", "/reactions.remove", body)
        return {"ok": response.get("ok"), "reaction": name}

    # ============ STAR HANDLERS ============
    
    def _handle_star(self, item_index: int, operation: str) -> Any:
        """Handle star operations"""
        if operation == "add":
            return self._star_add(item_index)
        elif operation == "delete":
            return self._star_delete(item_index)
        elif operation == "getAll":
            return self._star_get_all(item_index)
        else:
            raise ValueError(f"Unsupported star operation: {operation}")

    def _star_add(self, item_index: int) -> Dict[str, Any]:
        """Add a star"""
        # TODO: Implement star add
        return {"ok": True, "message": "Star add not yet implemented - TODO"}

    def _star_delete(self, item_index: int) -> Dict[str, Any]:
        """Remove a star"""
        # TODO: Implement star delete
        return {"ok": True, "message": "Star delete not yet implemented - TODO"}

    def _star_get_all(self, item_index: int) -> List[Dict[str, Any]]:
        """Get all starred items"""
        qs = {"limit": 100}
        response = self._slack_api_request("GET", "/stars.list", qs=qs)
        return response.get("items", [])

    # ============ USER HANDLERS ============
    
    def _handle_user(self, item_index: int, operation: str) -> Any:
        """Handle user operations"""
        if operation == "info":
            return self._user_info(item_index)
        elif operation == "getAll":
            return self._user_get_all(item_index)
        elif operation == "getPresence":
            return self._user_get_presence(item_index)
        elif operation == "getProfile":
            return self._user_get_profile(item_index)
        elif operation == "updateProfile":
            return self._user_update_profile(item_index)
        else:
            raise ValueError(f"Unsupported user operation: {operation}")

    def _user_info(self, item_index: int) -> Dict[str, Any]:
        """Get user information"""
        user = self.get_node_parameter("user", item_index, "")
        if not user:
            raise ValueError("User ID is required")
        
        qs = {"user": user}
        response = self._slack_api_request("GET", "/users.info", qs=qs)
        return response.get("user", response)

    def _user_get_all(self, item_index: int) -> List[Dict[str, Any]]:
        """Get all users"""
        qs = {"limit": 100}
        response = self._slack_api_request("GET", "/users.list", qs=qs)
        return response.get("members", [])

    def _user_get_presence(self, item_index: int) -> Dict[str, Any]:
        """Get user presence"""
        user = self.get_node_parameter("user", item_index, "")
        if not user:
            raise ValueError("User ID is required")
        
        qs = {"user": user}
        response = self._slack_api_request("GET", "/users.getPresence", qs=qs)
        return response

    def _user_get_profile(self, item_index: int) -> Dict[str, Any]:
        """Get user profile"""
        user = self.get_node_parameter("user", item_index, "")
        if not user:
            raise ValueError("User ID is required")
        
        qs = {"user": user}
        response = self._slack_api_request("GET", "/users.profile.get", qs=qs)
        return response.get("profile", response)

    def _user_update_profile(self, item_index: int) -> Dict[str, Any]:
        """Update user profile"""
        # TODO: Implement user profile update
        return {"ok": True, "message": "User profile update not yet implemented - TODO"}

    # ============ USER GROUP HANDLERS ============
    
    def _handle_user_group(self, item_index: int, operation: str) -> Any:
        """Handle user group operations"""
        if operation == "create":
            return self._user_group_create(item_index)
        elif operation == "disable":
            return self._user_group_disable(item_index)
        elif operation == "enable":
            return self._user_group_enable(item_index)
        elif operation == "getAll":
            return self._user_group_get_all(item_index)
        elif operation == "update":
            return self._user_group_update(item_index)
        else:
            raise ValueError(f"Unsupported user group operation: {operation}")

    def _user_group_create(self, item_index: int) -> Dict[str, Any]:
        """Create a user group"""
        name = self.get_node_parameter("name", item_index, "")
        if not name:
            raise ValueError("User group name is required")
        
        body = {"name": name}
        response = self._slack_api_request("POST", "/usergroups.create", body)
        return response.get("usergroup", response)

    def _user_group_disable(self, item_index: int) -> Dict[str, Any]:
        """Disable a user group"""
        user_group_id = self.get_node_parameter("userGroupId", item_index, "")
        if not user_group_id:
            raise ValueError("User group ID is required")
        
        body = {"usergroup": user_group_id}
        response = self._slack_api_request("POST", "/usergroups.disable", body)
        return response.get("usergroup", response)

    def _user_group_enable(self, item_index: int) -> Dict[str, Any]:
        """Enable a user group"""
        user_group_id = self.get_node_parameter("userGroupId", item_index, "")
        if not user_group_id:
            raise ValueError("User group ID is required")
        
        body = {"usergroup": user_group_id}
        response = self._slack_api_request("POST", "/usergroups.enable", body)
        return response.get("usergroup", response)

    def _user_group_get_all(self, item_index: int) -> List[Dict[str, Any]]:
        """Get all user groups"""
        qs = {"include_count": True, "include_disabled": True}
        response = self._slack_api_request("GET", "/usergroups.list", qs=qs)
        return response.get("usergroups", [])

    def _user_group_update(self, item_index: int) -> Dict[str, Any]:
        """Update a user group"""
        user_group_id = self.get_node_parameter("userGroupId", item_index, "")
        if not user_group_id:
            raise ValueError("User group ID is required")
        
        body = {"usergroup": user_group_id}
        # TODO: Add support for update fields
        response = self._slack_api_request("POST", "/usergroups.update", body)
        return response.get("usergroup", response)
