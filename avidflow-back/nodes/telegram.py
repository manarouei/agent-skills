import requests
import json
import copy
import logging
import io , mimetypes
from typing import Dict, List, Optional, Any, Union
from models import NodeExecutionData, Node, WorkflowModel
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)

OFFICE_MIME_TO_EXT = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "application/pdf": ".pdf",
        "application/zip": ".zip",
    }
class TelegramNode(BaseNode):
    """
    Telegram node for bot operations
    """

    type = "telegram"
    version = 2.0

    description = {
        "displayName": "Telegram",
        "name": "telegram",
        "icon": "file:telegram.svg",
        "group": ["input", "output"],
        "description": "Send messages and interact with Telegram bots",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
    }

    properties = {
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "options": [
                    {"name": "Message", "value": "message"},
                    {"name": "Chat", "value": "chat"},
                    {"name": "Callback", "value": "callback"},
                ],
                "default": "message",
                "description": "The resource to operate on",
            },
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {
                        "name": "Send Message",
                        "value": "sendMessage",
                        "description": "Send a text message",
                    },
                    {
                        "name": "Send Photo",
                        "value": "sendPhoto",
                        "description": "Send a photo",
                    },
                    {
                        "name": "Send Document",
                        "value": "sendDocument",
                        "description": "Send a document",
                    },
                    {
                        "name": "Edit Message",
                        "value": "editMessage",
                        "description": "Edit a message",
                    },
                    {
                        "name": "Delete Message",
                        "value": "deleteMessage",
                        "description": "Delete a message",
                    },
                ],
                "default": "sendMessage",
                "display_options": {"show": {"resource": ["message"]}},
            },
            {
                "name": "chatId",
                "type": NodeParameterType.STRING,
                "display_name": "Chat ID",
                "default": "",
                "required": True,
                "description": "Unique identifier for the target chat or username",
                "display_options": {"show": {"resource": ["message", "chat"]}},
            },
            {
                "name": "text",
                "type": NodeParameterType.STRING,
                "display_name": "Text",
                "default": "",
                "required": True,
                "description": "Text of the message to be sent",
                "display_options": {
                    "show": {
                        "resource": ["message"],
                        "operation": ["sendMessage", "editMessage"],
                    }
                },
            },
            {
                "name": "parseMode",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Parse Mode",
                "options": [
                    {"name": "None", "value": ""},
                    {"name": "Markdown", "value": "Markdown"},
                    {"name": "MarkdownV2", "value": "MarkdownV2"},
                    {"name": "HTML", "value": "HTML"},
                ],
                "default": "",
                "description": "Mode for parsing entities in the message text",
                "display_options": {
                    "show": {
                        "resource": ["message"],
                        "operation": ["sendMessage", "editMessage"],
                    }
                },
            },
            {
                "name": "disableWebPagePreview",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Disable Web Page Preview",
                "default": False,
                "description": "Disables link previews for links in this message",
                "display_options": {
                    "show": {
                        "resource": ["message"],
                        "operation": ["sendMessage", "editMessage"],
                    }
                },
            },
            {
                "name": "disableNotification",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Disable Notification",
                "default": False,
                "description": "Sends the message silently",
                "display_options": {
                    "show": {
                        "resource": ["message"],
                        "operation": ["sendMessage", "sendPhoto", "sendDocument"],
                    }
                },
            },
            {
                "name": "replyToMessageId",
                "type": NodeParameterType.STRING,
                "display_name": "Reply to Message ID",
                "default": "",
                "description": "If the message is a reply, ID of the original message",
                "display_options": {
                    "show": {
                        "resource": ["message"],
                        "operation": ["sendMessage", "sendPhoto", "sendDocument"],
                    }
                },
            },
            {
                "name": "messageId",
                "type": NodeParameterType.STRING,
                "display_name": "Message ID",
                "default": "",
                "required": False,
                "description": "Identifier of the message to edit or delete",
                "display_options": {
                    "show": {
                        "resource": ["message"],
                        "operation": ["editMessage", "deleteMessage"],
                    }
                },
            },
            {
                "name": "photo",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Photo",
                "default": "url_file_id",
                "required": False,
                "options": [
                    {"name": "URL OR File ID", "value": "url_file_id"},
                    {"name": "Binary", "value": "binary"},
                ],
                "description": "Photo to send (URL, or file_id)",
                "display_options": {"show": {"resource": ["message"], "operation": ["sendPhoto"]}}
            },
            {
                "name": "caption",
                "type": NodeParameterType.STRING,
                "display_name": "Caption",
                "default": "",
                "description": "Photo caption (may also be used when resending photos)",
                "display_options": {
                    "show": {"resource": ["message"], "operation": ["sendPhoto", "sendDocument"]}
                },
            },
            {
                "name": "document",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Document",
                "default": "",
                "required": False,
                "options": [
                    {"name": "URL OR File ID", "value": "url_file_id"},
                    {"name": "Binary", "value": "binary"},
                ],
                "description": "File to send (file path, URL, or file_id)",
                "display_options": {
                    "show": {"resource": ["message"], "operation": ["sendDocument"]}
                },
            },
            {
                "name": "url_file_id",
                "type": NodeParameterType.STRING,
                "display_name": "Url Or File Id",
                "default": "",
                "required": True,
                "description": "URL or file id to send",
                "display_options": {
                    "show": {
                        "resource": ["message"],
                        "operation": ["sendDocument"],
                        "document": ["url_file_id"],
                    }
                },
            },
            {
                "name": "binary_property",
                "type": NodeParameterType.STRING,
                "display_name": "Binary Property",
                "default": "",
                "required": True,
                "description": "Binary data to send",
                "display_options": {
                    "show": {
                        "resource": ["message"],
                        "operation": ["sendDocument"],
                        "document": ["binary"],
                    }
                },
            },
            {
                "name": "url_file_id",
                "type": NodeParameterType.STRING,
                "display_name": "Url Or File Id",
                "default": "",
                "required": True,
                "description": "URL or file id to send",
                "display_options": {
                    "show": {
                        "resource": ["message"],
                        "operation": ["sendPhoto"],
                        "photo": ["url_file_id"],
                    }
                },
            },
            {
                "name": "binary_property",
                "type": NodeParameterType.STRING,
                "display_name": "Binary Property",
                "default": "",
                "required": True,
                "description": "Binary data to send",
                "display_options": {
                    "show": {
                        "resource": ["message"],
                        "operation": ["sendPhoto"],
                        "photo": ["binary"],
                    }
                },
            },
        ],
        "credentials": [{"name": "telegramApi", "required": True}],
    }

    icon = "telegram.svg"
    color = "#0088cc"

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Telegram operation and return properly formatted data"""

        try:
            # Get input data using the new method signature
            input_data = self.get_input_data()

            result_items: List[NodeExecutionData] = []

            # Process each input item
            for i, item in enumerate(input_data):
                try:
                    # Get parameters for this item using the new method
                    resource = self.get_node_parameter("resource", i, "message")
                    operation = self.get_node_parameter("operation", i, "sendMessage")

                    # Execute the appropriate operation
                    if resource == "message":
                        if operation == "sendMessage":
                            result = self._send_message(i)
                        elif operation == "sendPhoto":
                            result = self._send_photo(i)
                        elif operation == "sendDocument":
                            result = self._send_document(i)
                        elif operation == "editMessage":
                            result = self._edit_message(i)
                        elif operation == "deleteMessage":
                            result = self._delete_message(i)
                        else:
                            raise ValueError(
                                f"Unsupported operation '{operation}' for resource '{resource}'"
                            )
                    else:
                        raise ValueError(f"Unsupported resource '{resource}'")

                    # Add result to items
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
                    # Create error data following project pattern
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": self.get_node_parameter(
                                "resource", i, "message"
                            ),
                            "operation": self.get_node_parameter(
                                "operation", i, "sendMessage"
                            ),
                            "item_index": i,
                        },
                        binary_data=None,
                    )

                    result_items.append(error_item)

            return [result_items]

        except Exception as e:
            error_data = [
                NodeExecutionData(
                    json_data={"error": f"Error in Telegram node: {str(e)}"},
                    binary_data=None,
                )
            ]
            return [error_data]

    def _get_api_url(self) -> str:
        """Get Telegram API URL with bot token"""
        credentials = self.get_credentials("telegramApi")
        if not credentials:
            raise ValueError("Telegram credentials not found")

        access_token = credentials.get("accessToken")
        api_url = credentials.get("apiUrl", "https://api.telegram.org")

        if not access_token:
            raise ValueError("Access token is required for Telegram API")

        return f"{api_url.rstrip('/')}/bot{access_token}"
    

    def _ensure_filename_and_mime(self, entry: dict, raw: bytes) -> tuple[str, str]:
        name = entry.get("fileName") or entry.get("filename") or "document"
        mime = entry.get("mimeType")

        # 1) Prefer declared MIME; else guess from name; else quick sniff; else octet-stream
        if not mime:
            mime = mimetypes.guess_type(name)[0]
        if not mime and raw:
            head = raw[:16]
            if head.startswith(b"%PDF-"): mime = "application/pdf"
            elif head.startswith(b"\x89PNG\r\n\x1a\n"): mime = "image/png"
            elif head[:3] == b"\xff\xd8\xff": mime = "image/jpeg"
            elif head[:4] == b"PK\x03\x04": mime = "application/zip"  # xlsx/docx/pptx are ZIP-based

        if not mime:
            mime = "application/octet-stream"

        # 2) Ensure filename has a sensible extension that matches MIME
        base = name.rsplit("/", 1)[-1]
        has_ext = "." in base
        if not has_ext:
            ext = OFFICE_MIME_TO_EXT.get(mime) or mimetypes.guess_extension(mime) or ""
            if ext and not name.endswith(ext):
                name += ext
        return name, mime

    def _resolve_binary_entry(
        self, bin_map: Dict[str, Any], attachment: str
    ) -> Dict[str, Any]:
        """
        Accepts either:
        1) n8n-style map: { "<attachment>": { data, fileName, mimeType, size } }
        2) legacy flat object: { data, fileName, mimeType, size }
        Returns a dict suitable for _binary_entry_to_bytes().
        """
        entry = None

        # Case 1: Proper n8n-style keyed entry
        if isinstance(bin_map, dict) and attachment in bin_map and isinstance(bin_map[attachment], dict):
            entry = bin_map[attachment]

        # Case 2: Legacy flat object passed directly in binary_data
        elif isinstance(bin_map, dict) and "data" in bin_map and isinstance(bin_map["data"], str):
            # Only accept it if caller referenced the root key (common choice: "data")
            # or if there is only one candidate-like payload in this map.
            if attachment == "data" or len([k for k, v in bin_map.items() if k == "data" or (isinstance(v, dict) and "data" in v)]) <= 1:
                entry = bin_map

        if not isinstance(entry, dict) or "data" not in entry:
            raise ValueError("Invalid binary document")

        # Normalize field naming (n8n uses fileName; your Set node sometimes uses filename)
        if "filename" in entry and "fileName" not in entry:
            entry["fileName"] = entry["filename"]

        return entry
    
    


    def _send_message(self, item_index: int) -> Dict[str, Any]:
        """Send a text message"""
        try:
            api_url = self._get_api_url()

            # Get parameters using the new method
            chat_id = self.get_node_parameter("chatId", item_index, "")
            text = self.get_node_parameter("text", item_index, "")
            parse_mode = self.get_node_parameter("parseMode", item_index, "")
            disable_web_page_preview = self.get_node_parameter(
                "disableWebPagePreview", item_index, False
            )
            disable_notification = self.get_node_parameter(
                "disableNotification", item_index, False
            )
            reply_to_message_id = self.get_node_parameter(
                "replyToMessageId", item_index, ""
            )

            if not chat_id or not text:
                raise ValueError("Chat ID and text are required for sending message")

            payload = {
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": disable_web_page_preview,
                "disable_notification": disable_notification,
            }

            if parse_mode:
                payload["parse_mode"] = parse_mode

            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id

            response = requests.post(f"{api_url}/sendMessage", json=payload, timeout=30)

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return {
                        "message_id": result["result"]["message_id"],
                        "chat_id": result["result"]["chat"]["id"],
                        "text": result["result"]["text"],
                        "date": result["result"]["date"],
                        "status": "sent",
                    }
                else:
                    raise ValueError(
                        f"Telegram API error: {result.get('description', 'Unknown error')}"
                    )
            else:
                raise ValueError(f"HTTP error {response.status_code}: {response.text}")

        except Exception as e:
            raise ValueError(f"Error sending message: {str(e)}")

    def _send_photo(self, item_index: int) -> Dict[str, Any]:
        """Send a photo"""
        try:
            api_url = self._get_api_url()

            # Get parameters using the new method
            chat_id = self.get_node_parameter("chatId", item_index, "")
            photo = self.get_node_parameter("photo", item_index, "")
            caption = self.get_node_parameter("caption", item_index, "")
            parse_mode = self.get_node_parameter("parseMode", item_index, "")
            disable_notification = self.get_node_parameter(
                "disableNotification", item_index, False
            )
            reply_to_message_id = self.get_node_parameter(
                "replyToMessageId", item_index, ""
            )

            if not chat_id or not photo:
                raise ValueError("Chat ID and photo are required for sending photo")

            file = None
            if photo == "binary":
                input_items = self.get_input_data() or []
                current = (
                    input_items[item_index]
                    if 0 <= item_index < len(input_items)
                    else None
                )
                bin_map: Dict[str, Any] = (
                    getattr(current, "binary_data", None) if current else None
                )
                if bin_map:
                    attachment = self.get_node_parameter("binary_property", item_index, "")
                    entry = bin_map.get(attachment, None)
                    if not entry or not isinstance(entry, dict):
                        raise ValueError("Invalid binary document")
                    file = io.BytesIO(
                        self._binary_entry_to_bytes(
                            entry
                        )
                    )
                    file.name = entry.get("fileName", "photo")
            else:
                file = self.get_node_parameter("url_file_id", item_index, None)

            files = {"photo": file}

            payload = {
                "chat_id": chat_id,
                "disable_notification": disable_notification
            } | (files if type(file) is str else {})
            if caption:
                payload["caption"] = caption

            if parse_mode:
                payload["parse_mode"] = parse_mode

            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id

            response = requests.post(
                f"{api_url}/sendPhoto", data=payload, timeout=30,
                **{"files": files} if files['photo'] is not str else {}
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return {
                        "message_id": result["result"]["message_id"],
                        "chat_id": result["result"]["chat"]["id"],
                        "photo": result["result"]["photo"],
                        "caption": result["result"].get("caption", ""),
                        "date": result["result"]["date"],
                        "status": "sent",
                    }
                else:
                    raise ValueError(
                        f"Telegram API error: {result.get('description', 'Unknown error')}"
                    )
            else:
                raise ValueError(f"HTTP error {response.status_code}: {response.text}")

        except Exception as e:
            raise ValueError(f"Error sending photo: {str(e)}")

    def _send_document(self, item_index: int) -> Dict[str, Any]:
        """Send a document"""
        try:
            api_url = self._get_api_url()

            # Get parameters using the new method
            chat_id = self.get_node_parameter("chatId", item_index, "")
            document = self.get_node_parameter("document", item_index, "")
            caption = self.get_node_parameter("caption", item_index, "")
            parse_mode = self.get_node_parameter("parseMode", item_index, "")
            disable_notification = self.get_node_parameter(
                "disableNotification", item_index, False
            )
            reply_to_message_id = self.get_node_parameter(
                "replyToMessageId", item_index, ""
            )

            if not chat_id or not document:
                raise ValueError(
                    "Chat ID and document are required for sending document"
                )

            file = None
            if document == "binary":
                input_items = self.get_input_data() or []
                current = (
                    input_items[item_index]
                    if 0 <= item_index < len(input_items)
                    else None
                )
                bin_map: Dict[str, Any] = (
                    getattr(current, "binary_data", None) if current else None
                )
                
                if not bin_map:
                    raise ValueError("No binary_data found on input")
                
                if bin_map:
                    attachment = self.get_node_parameter("binary_property", item_index, "data")
                    entry = self._resolve_binary_entry(bin_map, attachment)   # must return dict with "data"
                    raw = self._binary_entry_to_bytes(entry)                  # -> bytes

                    # Ensure filename + mime (adds extension if missing)
                    filename, mime = self._ensure_filename_and_mime(entry, raw)

                    file = io.BytesIO(raw)
                    file.name = filename
                    files = {"document": file}

            else:
                #file = self.get_node_parameter("url_file_id", item_index, None)
                url_or_file_id = self.get_node_parameter("url_file_id", item_index, None)
                if not url_or_file_id:
                    raise ValueError("Document mode is URL/FileID but no url_file_id provided")
                payload["document"] = url_or_file_id

            # files = {
            #     "document": (url_or_file_id, open(url_or_file_id, "rb"), "application/octet-stream")
            # }       

            payload = {
                "chat_id": chat_id,
                "disable_notification": disable_notification,
            } | (files if type(file) is str else {})

            if caption:
                payload["caption"] = caption

            if parse_mode:
                payload["parse_mode"] = parse_mode

            if reply_to_message_id:
                payload["reply_to_message_id"] = reply_to_message_id   

        
            if files is not None:
                response = requests.post(
                    f"{api_url}/sendDocument", data=payload, timeout=30,
                    **{"files": files} if files['document'] is not str else {}
                )

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return {
                        "message_id": result["result"]["message_id"],
                        "chat_id": result["result"]["chat"]["id"],
                        "document": result["result"]["document"],
                        "caption": result["result"].get("caption", ""),
                        "date": result["result"]["date"],
                        "status": "sent",
                    }
                raise ValueError(
                    f"Telegram API error: {result.get('description', 'Unknown error')}"
                )
            else:
                raise ValueError(f"HTTP error {response.status_code}: {response.text}")

        except Exception as e:
            raise ValueError(f"Error sending document: {str(e)}")

    def _edit_message(self, item_index: int) -> Dict[str, Any]:
        """Edit a message"""
        try:
            api_url = self._get_api_url()

            # Get parameters using the new method
            chat_id = self.get_node_parameter("chatId", item_index, "")
            message_id = self.get_node_parameter("messageId", item_index, "")
            text = self.get_node_parameter("text", item_index, "")
            parse_mode = self.get_node_parameter("parseMode", item_index, "")
            disable_web_page_preview = self.get_node_parameter(
                "disableWebPagePreview", item_index, False
            )

            if not chat_id or not message_id or not text:
                raise ValueError(
                    "Chat ID, message ID, and text are required for editing message"
                )

            payload = {
                "chat_id": chat_id,
                "message_id": message_id,
                "text": text,
                "disable_web_page_preview": disable_web_page_preview,
            }

            if parse_mode:
                payload["parse_mode"] = parse_mode

            response = requests.post(
                f"{api_url}/editMessageText", json=payload, timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return {
                        "message_id": result["result"]["message_id"],
                        "chat_id": result["result"]["chat"]["id"],
                        "text": result["result"]["text"],
                        "date": result["result"]["date"],
                        "edit_date": result["result"]["edit_date"],
                        "status": "edited",
                    }
                else:
                    raise ValueError(
                        f"Telegram API error: {result.get('description', 'Unknown error')}"
                    )
            else:
                raise ValueError(f"HTTP error {response.status_code}: {response.text}")

        except Exception as e:
            raise ValueError(f"Error editing message: {str(e)}")

    def _delete_message(self, item_index: int) -> Dict[str, Any]:
        """Delete a message"""
        try:
            api_url = self._get_api_url()

            # Get parameters using the new method
            chat_id = self.get_node_parameter("chatId", item_index, "")
            message_id = self.get_node_parameter("messageId", item_index, "")

            if not chat_id or not message_id:
                raise ValueError(
                    "Chat ID and message ID are required for deleting message"
                )

            payload = {"chat_id": chat_id, "message_id": message_id}

            response = requests.post(
                f"{api_url}/deleteMessage", json=payload, timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return {
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "status": "deleted",
                    }
                else:
                    raise ValueError(
                        f"Telegram API error: {result.get('description', 'Unknown error')}"
                    )
            else:
                raise ValueError(f"HTTP error {response.status_code}: {response.text}")

        except Exception as e:
            raise ValueError(f"Error deleting message: {str(e)}")
