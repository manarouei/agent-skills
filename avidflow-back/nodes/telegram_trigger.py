import base64
import logging
from typing import Any, Dict, List, Optional

import requests

from .base import BaseNode, NodeParameterType
from models import NodeExecutionData

logger = logging.getLogger(__name__)


class TelegramTriggerNode(BaseNode):
    """
    Telegram Trigger (webhook) node.
    - Exposes a webhook (POST).
    - Optionally validates Telegram secret token header.
    - Can restrict by chat/user IDs.
    - Can download images/files into binary data.
    """

    type = "telegramTrigger"
    version = 2

    description = {
        "displayName": "Telegram Trigger",
        "name": "telegramTrigger",
        "icon": "file:telegram.svg",
        "group": ["trigger"],
        "version": [1, 1.1, 1.2],
        "defaultVersion": 1.2,
        "description": "Starts the workflow on a Telegram update",
        "defaults": {"name": "Telegram Trigger"},
        "inputs": [],
        "outputs": [{"name": "main", "type": "main", "required": True}],
    }

    properties = {
        "parameters": [
            {
              "name": "test_path",
              "type": "string",
              "display_name": "Test Path",
              "default": "{api_base_address}/webhook/test/execute/telegram_trigger/${webhook_id}",
              "readonly": True,
              "description": "The test path for call in editor execution"
            },
            {
              "name": "path",
              "type": "string",
              "display_name": "Path",
              "default": "{api_base_address}/webhook/${webhook_id}/telegram_trigger",
              "readonly": True,
              "description": "The path to register the webhook under"
            },
            {
                "name": "httpMethod",
                "type": NodeParameterType.OPTIONS,
                "display_name": "HTTP Method",
                "default": "POST",
                "options": [{"name": "POST", "value": "POST"}],
                "description": "HTTP method to accept",
            },
            {
                "name": "updates",
                "type": NodeParameterType.MULTI_OPTIONS,
                "display_name": "Trigger On",
                "options": [
                    {"name": "*", "value": "*", "description": "All updates"},
                    {"name": "Callback Query", "value": "callback_query"},
                    {"name": "Channel Post", "value": "channel_post"},
                    {"name": "Edited Channel Post", "value": "edited_channel_post"},
                    {"name": "Edited Message", "value": "edited_message"},
                    {"name": "Inline Query", "value": "inline_query"},
                    {"name": "Message", "value": "message"},
                    {"name": "Poll", "value": "poll"},
                    {"name": "Pre-Checkout Query", "value": "pre_checkout_query"},
                    {"name": "Shipping Query", "value": "shipping_query"},
                ],
                "required": True,
                "default": [],
            },
            {
                "name": "additionalFields",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Additional Fields",
                "placeholder": "Add Field",
                "default": {},
                "options": [
                    {
                        "name": "download",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Download Images/Files",
                        "default": False,
                        "description": "Whether to download images/files from the update",
                    },
                    {
                        "name": "imageSize",
                        "type": NodeParameterType.OPTIONS,
                        "display_name": "Image Size",
                        "options": [
                            {"name": "Small", "value": "small"},
                            {"name": "Medium", "value": "medium"},
                            {"name": "Large", "value": "large"},
                            {"name": "Extra Large", "value": "extraLarge"},
                        ],
                        "default": "large",
                        "description": "The size of the image to be downloaded",
                        "display_options": {"show": {"download": [True]}},
                    },
                    {
                        "name": "chatIds",
                        "type": NodeParameterType.STRING,
                        "display_name": "Restrict to Chat IDs",
                        "default": "",
                        "description": "Comma-separated chat IDs to accept",
                    },
                    {
                        "name": "userIds",
                        "type": NodeParameterType.STRING,
                        "display_name": "Restrict to User IDs",
                        "default": "",
                        "description": "Comma-separated user IDs to accept",
                    },
                    {
                        "name": "secretToken",
                        "type": NodeParameterType.STRING,
                        "display_name": "Secret Token",
                        "default": "",
                        "description": "If set, require matching x-telegram-bot-api-secret-token header",
                    },
                ],
            },
        ],
        "credentials": [{"name": "telegramApi", "required": True}],
    }

    icon = "telegram.svg"
    color = "#0088cc"

    # Trigger nodes should implement trigger(), not execute()
    def trigger(self) -> List[List[NodeExecutionData]]:
        """
        Consume webhook payload (provided by the workflow engine as the first item).
        Returns a single item with:
          - json_data: original Telegram update
          - binary_data: optional downloaded files
        """
        envelope = self.execution_data if hasattr(self, "execution_data") else []
        if not envelope or envelope == {}:
            return [[NodeExecutionData(json_data={"warning": "no payload"}, binary_data=None)]]

        # Expect a single envelope with the router's webhook_data
        body = envelope.get("webhookData") or envelope.get("body") or {}

        headers = envelope.get("headers") or {}
        update: Dict[str, Any] = body if isinstance(body, dict) else {}

        # Filters
        updates_filter = self.get_node_parameter("updates", 0, []) or []
        additional = self.get_node_parameter("additionalFields", 0, {}) or {}

        # Optional secret token header check
        secret_param = (additional.get("secretToken") or "").strip()
        if secret_param:
            header_secret = headers.get("x-telegram-bot-api-secret-token") or headers.get(
                "X-Telegram-Bot-Api-Secret-Token"
            )
            if not header_secret or str(header_secret) != secret_param:
                logger.warning("TelegramTrigger: Secret token mismatch; ignoring update")
                return [[]]  # Drop silently

        # Restrict by chatIds/userIds
        chat_ids_raw = (additional.get("chatIds") or "").strip()
        user_ids_raw = (additional.get("userIds") or "").strip()
        if chat_ids_raw:
            allowed_chats = {c.strip() for c in chat_ids_raw.split(",") if c.strip()}
            update_chat_id = None
            if "message" in update and update["message"].get("chat"):
                update_chat_id = str(update["message"]["chat"].get("id"))
            elif "channel_post" in update and update["channel_post"].get("chat"):
                update_chat_id = str(update["channel_post"]["chat"].get("id"))
            if update_chat_id and update_chat_id not in allowed_chats:
                return [[]]

        if user_ids_raw:
            allowed_users = {u.strip() for u in user_ids_raw.split(",") if u.strip()}
            update_user_id = None
            if "message" in update and update["message"].get("from"):
                update_user_id = str(update["message"]["from"].get("id"))
            elif "callback_query" in update and update["callback_query"].get("from"):
                update_user_id = str(update["callback_query"]["from"].get("id"))
            if update_user_id and update_user_id not in allowed_users:
                return [[]]

        # Filter by update type if not wildcard
        if updates_filter and "*" not in updates_filter:
            if not any(k in update for k in updates_filter):
                return [[]]

        # Optionally download files
        binary: Dict[str, Any] = None
        try:
            if additional.get("download") is True:
                binary = self._download_assets(update, additional)
        except Exception as e:
            logger.warning(f"TelegramTrigger: Download failed: {e}")

        return [[NodeExecutionData(json_data=update, binary_data=binary)]]

    # ------------- Helpers -------------

    def _get_api_url(self) -> str:
        creds = self.get_credentials("telegramApi")
        if not creds:
            raise ValueError("Telegram credentials not found")
        access_token = creds.get("accessToken")
        api_url = creds.get("apiUrl", "https://api.telegram.org")
        if not access_token:
            raise ValueError("Access token is required for Telegram API")
        return f"{api_url.rstrip('/')}/bot{access_token}"

    def _get_file_base(self) -> str:
        # For file download base: https://api.telegram.org/file/bot<token>/<file_path>
        creds = self.get_credentials("telegramApi")
        if not creds:
            raise ValueError("Telegram credentials not found")
        access_token = creds.get("accessToken")
        api_url = creds.get("apiUrl", "https://api.telegram.org")
        if not access_token:
            raise ValueError("Access token is required for Telegram API")
        return f"{api_url.rstrip('/')}/file/bot{access_token}"

    def _get_file_path(self, file_id: str) -> Optional[str]:
        api = self._get_api_url()
        r = requests.post(f"{api}/getFile", json={"file_id": file_id}, timeout=30)
        if r.status_code != 200:
            return None
        data = r.json()
        if not data.get("ok"):
            return None
        return data["result"].get("file_path")

    def _download_bytes(self, file_path: str) -> Optional[bytes]:
        base = self._get_file_base()
        r = requests.get(f"{base}/{file_path}", timeout=60)
        if r.status_code != 200:
            return None
        return r.content

    def _pick_photo_size(self, photos: List[Dict[str, Any]], pref: str) -> Dict[str, Any]:
        # Telegram sends photos sizes sorted by size (smallest to largest)
        if not photos:
            return {}
        if pref == "small":
            return photos[0]
        if pref == "medium":
            return photos[min(1, len(photos) - 1)]
        # large / extraLarge -> use largest available
        return photos[-1]

    def _download_assets(self, update: Dict[str, Any], additional: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        binary: Dict[str, Any] = {}

        # Photos
        image_size = str(additional.get("imageSize", "large"))
        if "message" in update and update["message"].get("photo"):
            chosen = self._pick_photo_size(update["message"]["photo"], image_size)
            file_id = chosen.get("file_id")
            if file_id:
                file_path = self._get_file_path(file_id)
                if file_path:
                    content = self._download_bytes(file_path)
                    if content:
                        b64 = base64.b64encode(content).decode()
                        binary["photo"] = {
                            "data": self.compress_data(b64),
                            "mimeType": "image/jpeg",
                            "fileName": file_path.split("/")[-1],
                            "size": len(content),
                        }

        # Document
        if "message" in update and update["message"].get("document"):
            doc = update["message"]["document"]
            file_id = doc.get("file_id")
            if file_id:
                file_path = self._get_file_path(file_id)
                if file_path:
                    content = self._download_bytes(file_path)
                    if content:
                        b64 = base64.b64encode(content).decode()
                        filename = doc.get("file_name") or file_path.split("/")[-1]
                        mime = doc.get("mime_type") or "application/octet-stream"
                        binary["document"] = {
                            "data": self.compress_data(b64),
                            "mimeType": mime,
                            "fileName": filename,
                            "size": len(content),
                        }

        return binary or None