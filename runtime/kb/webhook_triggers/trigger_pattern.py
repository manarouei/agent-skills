"""
Webhook Trigger Node Pattern for AvidFlow

Pattern extracted from: webhook.py, telegram_trigger.py
Use case: Nodes that receive HTTP webhooks and start workflows

SYNC-CELERY SAFE: No HTTP calls, just data transformation
"""

from typing import Dict, List, Optional, Any
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType
import logging

logger = logging.getLogger(__name__)


# ==============================================================================
# PATTERN 1: Simple Webhook (Generic HTTP endpoint)
# ==============================================================================

class WebhookNodeExample(BaseNode):
    """
    Generic webhook that accepts GET/POST and passes all data to workflow.
    
    Based on: /home/toni/n8n/back/nodes/webhook.py
    """
    
    type = "webhook"
    version = 1
    is_trigger = True  # CRITICAL: Marks this as a trigger node
    
    description = {
        "displayName": "Webhook",
        "name": "webhook",
        "group": ["trigger"],  # CRITICAL: Must be in trigger group
        "inputs": [],  # Trigger nodes have NO inputs
        "outputs": [{"name": "main", "type": "main", "required": True}],
    }
    
    properties = {
        "parameters": [
            {
                "name": "test_path",
                "type": "string",
                "display_name": "Test Path",
                # PATTERN: Uses {api_base_address} and ${webhook_id} variables
                # These are replaced by router at runtime
                "default": "{api_base_address}/webhook/test/execute/webhook/${webhook_id}",
                "readonly": True,
            },
            {
                "name": "path",
                "type": "string",
                "display_name": "Production Path",
                "default": "{api_base_address}/webhook/${webhook_id}/webhook",
                "readonly": True,
            },
            {
                "name": "httpMethod",
                "type": NodeParameterType.OPTIONS,
                "display_name": "HTTP Method",
                "options": [
                    {"name": "GET", "value": "GET"},
                    {"name": "POST", "value": "POST"},
                ],
                "default": "POST",
            }
        ],
        "credentials": []  # Webhooks typically don't need credentials
    }
    
    def trigger(self) -> List[List[NodeExecutionData]]:
        """
        CRITICAL: Trigger nodes implement trigger(), NOT execute()!
        
        The webhook router (routers/webhook.py) does the following:
        1. Receives HTTP request at /webhook/{webhook_id}/{node_type}
        2. Validates webhook exists and workflow is active
        3. Packages request data into execution_data
        4. Calls execute_workflow Celery task
        5. Celery task sets self.execution_data before calling trigger()
        
        This method just unpacks execution_data and returns it as NodeExecutionData.
        """
        try:
            # PATTERN: execution_data is set by workflow engine
            if hasattr(self, "execution_data") and self.execution_data:
                # execution_data structure from router:
                # {
                #     "body": {...},  # POST payload
                #     "headers": {...},  # HTTP headers
                #     "query": {...},  # Query parameters
                #     "method": "POST",  # HTTP method
                #     "url": "https://...",  # Full URL
                #     "webhookData": {...},  # Alias for body
                #     "timestamp": "2026-01-07T..."
                # }
                input_data = NodeExecutionData(
                    json_data=self.execution_data,
                    binary_data=None
                )
                return [[input_data]]
            
            # Fallback for testing: Try to get from connected nodes
            # (though trigger nodes shouldn't have inputs in production)
            try:
                input_items = self.get_input_data()
                if input_items and len(input_items) > 0:
                    return [input_items]
            except:
                pass
            
            # Empty data if nothing available
            empty_data = NodeExecutionData(
                json_data={},
                binary_data=None
            )
            return [[empty_data]]
            
        except Exception as e:
            import traceback
            logger.error(f"Webhook trigger error: {e}")
            error_data = NodeExecutionData(
                json_data={
                    "error": str(e),
                    "details": traceback.format_exc()
                },
                binary_data=None
            )
            return [[error_data]]


# ==============================================================================
# PATTERN 2: Service-Specific Webhook (Telegram, GitHub, etc.)
# ==============================================================================

class TelegramTriggerNodeExample(BaseNode):
    """
    Service-specific webhook with validation, filtering, and binary downloads.
    
    Based on: /home/toni/n8n/back/nodes/telegram_trigger.py
    """
    
    type = "telegramTrigger"
    version = 2
    is_trigger = True
    
    description = {
        "displayName": "Telegram Trigger",
        "name": "telegramTrigger",
        "group": ["trigger"],
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
            },
            {
                "name": "path",
                "type": "string",
                "display_name": "Production Path",
                "default": "{api_base_address}/webhook/${webhook_id}/telegram_trigger",
                "readonly": True,
            },
            {
                "name": "httpMethod",
                "type": NodeParameterType.OPTIONS,
                "display_name": "HTTP Method",
                "default": "POST",
                "options": [{"name": "POST", "value": "POST"}],
            },
            {
                "name": "updates",
                "type": NodeParameterType.MULTI_OPTIONS,
                "display_name": "Trigger On",
                "options": [
                    {"name": "*", "value": "*", "description": "All updates"},
                    {"name": "Message", "value": "message"},
                    {"name": "Callback Query", "value": "callback_query"},
                    {"name": "Inline Query", "value": "inline_query"},
                ],
                "required": True,
                "default": ["*"],
            },
            {
                "name": "additionalFields",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Additional Fields",
                "default": {},
                "options": [
                    {
                        "name": "download",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Download Images/Files",
                        "default": False,
                    },
                    {
                        "name": "chatIds",
                        "type": NodeParameterType.STRING,
                        "display_name": "Restrict to Chat IDs",
                        "default": "",
                        "description": "Comma-separated chat IDs",
                    },
                    {
                        "name": "secretToken",
                        "type": NodeParameterType.STRING,
                        "display_name": "Secret Token",
                        "default": "",
                        "description": "Telegram secret token header validation",
                    },
                ],
            },
        ],
        "credentials": [{"name": "telegramApi", "required": True}],
    }
    
    def trigger(self) -> List[List[NodeExecutionData]]:
        """
        Advanced trigger with:
        1. Header validation (secret token)
        2. Payload filtering (chat IDs, user IDs, update types)
        3. Binary downloads (images, files)
        
        SYNC-CELERY SAFE: Uses requests with timeout for downloads.
        """
        envelope = self.execution_data if hasattr(self, "execution_data") else {}
        if not envelope:
            return [[]]
        
        # Extract webhook payload
        body = envelope.get("webhookData") or envelope.get("body") or {}
        headers = envelope.get("headers") or {}
        update: Dict[str, Any] = body if isinstance(body, dict) else {}
        
        # Get node parameters
        updates_filter = self.get_node_parameter("updates", 0, []) or []
        additional = self.get_node_parameter("additionalFields", 0, {}) or {}
        
        # VALIDATION 1: Secret token header check
        secret_param = (additional.get("secretToken") or "").strip()
        if secret_param:
            header_token = headers.get("x-telegram-bot-api-secret-token", "")
            if header_token != secret_param:
                logger.warning("Telegram secret token mismatch")
                return [[]]  # Reject webhook
        
        # VALIDATION 2: Filter by chat IDs
        chat_ids_raw = (additional.get("chatIds") or "").strip()
        if chat_ids_raw:
            allowed_chats = [c.strip() for c in chat_ids_raw.split(",") if c.strip()]
            message = update.get("message") or update.get("channel_post") or {}
            chat_id = str(message.get("chat", {}).get("id", ""))
            if chat_id and chat_id not in allowed_chats:
                logger.info(f"Chat {chat_id} not in allowed list")
                return [[]]
        
        # VALIDATION 3: Filter by update type (if not wildcard)
        if updates_filter and "*" not in updates_filter:
            update_type = next((k for k in updates_filter if k in update), None)
            if not update_type:
                logger.info(f"Update type not in filter: {list(update.keys())}")
                return [[]]
        
        # BINARY DOWNLOAD: Optionally download files/images
        binary: Optional[Dict[str, Any]] = None
        if additional.get("download", False):
            try:
                binary = self._download_assets(update, additional)
            except Exception as e:
                logger.error(f"Error downloading assets: {e}")
        
        return [[NodeExecutionData(
            json_data=update,
            binary_data=binary
        )]]
    
    def _download_assets(
        self,
        update: Dict[str, Any],
        additional: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Download images/files from Telegram update.
        
        PATTERN: Get file_id → getFile API → download URL → requests.get
        
        NOTE: This requires implementing file download helpers.
        For complex file handling, see runtime/kb/binary_handling/file_download_pattern.py
        """
        # LACK OF IMPLEMENTATION in AvidFlow platform:
        # Full Telegram file download requires:
        # 1. Extract file_id from update (message.photo, message.document, etc.)
        # 2. Call Telegram getFile API to get file_path
        # 3. Download file from https://api.telegram.org/file/bot{token}/{file_path}
        # 4. Convert to base64 binary data
        #
        # This functionality should be moved to utils/telegram_helpers.py
        # For now, mark as unimplemented:
        logger.warning(
            "File download not fully implemented in AvidFlow platform. "
            "See runtime/kb/binary_handling/ for implementation patterns."
        )
        return None


# ==============================================================================
# CRITICAL RULES for Webhook Triggers
# ==============================================================================

"""
1. ALWAYS set is_trigger = True
2. ALWAYS put in "trigger" group  
3. ALWAYS have empty inputs list []
4. ALWAYS implement trigger(), NOT execute()
5. execution_data is set by router before trigger() is called
6. Return List[List[NodeExecutionData]] - nested lists!
7. Use get_node_parameter() for user-configured parameters
8. Validation failures should return [[]] (empty), not raise exceptions
9. Binary downloads must use requests with timeout, not async
10. Log validation failures with logger.info/warning for debugging
"""
