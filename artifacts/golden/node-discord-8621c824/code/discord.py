#!/usr/bin/env python3
"""
Discord Node

Converted from TypeScript by agent-skills/code-convert
Correlation ID: node-discord-8621c824
Generated: 2026-01-04T13:32:31.803325

SYNC-CELERY SAFE: All methods are synchronous with timeouts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from .base import BaseNode, NodeParameter, NodeParameterType, NodeExecutionData

logger = logging.getLogger(__name__)


class DiscordNode(BaseNode):
    """
    Node node.
    
    
    """

    node_type = "discord"
    node_version = 1
    display_name = "Node"
    description = ""
    icon = "file:discord.svg"
    group = ['output']
    
    credentials = [
        {
            "name": "oauth2",
            "required": True,
        }
    ]

    properties = [
            {"name": "operation", "type": NodeParameterType.OPTIONS, "display_name": "Operation", "options": [
                {"name": "Send a Message", "value": "sendLegacy", "description": "Send a message to a channel using the webhook"},
                {"name": "parseDiscordError", "value": "parseDiscordError", "description": "Operation: parseDiscordError"},
                {"name": "prepareErrorData", "value": "prepareErrorData", "description": "Operation: prepareErrorData"},
                {"name": "prepareOptions", "value": "prepareOptions", "description": "Operation: prepareOptions"},
                {"name": "prepareEmbeds", "value": "prepareEmbeds", "description": "Operation: prepareEmbeds"},
                {"name": "prepareMultiPartForm", "value": "prepareMultiPartForm", "description": "Operation: prepareMultiPartForm"},
                {"name": "checkAccessToGuild", "value": "checkAccessToGuild", "description": "Operation: checkAccessToGuild"},
                {"name": "checkAccessToChannel", "value": "checkAccessToChannel", "description": "Operation: checkAccessToChannel"},
                {"name": "setupChannelGetter", "value": "setupChannelGetter", "description": "Operation: setupChannelGetter"},
                {"name": "sendDiscordMessage", "value": "sendDiscordMessage", "description": "Operation: sendDiscordMessage"},
                {"name": "createSendAndWaitMessageBody", "value": "createSendAndWaitMessageBody", "description": "Operation: createSendAndWaitMessageBody"},
                {"name": "getGuildId", "value": "getGuildId", "description": "Operation: getGuildId"},
                {"name": "checkBotAccessToGuild", "value": "checkBotAccessToGuild", "description": "Operation: checkBotAccessToGuild"},
                {"name": "guildSearch", "value": "guildSearch", "description": "Operation: guildSearch"},
                {"name": "channelSearch", "value": "channelSearch", "description": "Operation: channelSearch"},
                {"name": "textChannelSearch", "value": "textChannelSearch", "description": "Operation: textChannelSearch"},
                {"name": "categorySearch", "value": "categorySearch", "description": "Operation: categorySearch"},
                {"name": "userSearch", "value": "userSearch", "description": "Operation: userSearch"},
                {"name": "getRoles", "value": "getRoles", "description": "Operation: getRoles"},
                {"name": "discordApiRequest", "value": "discordApiRequest", "description": "Operation: discordApiRequest"},
                {"name": "discordApiMultiPartRequest", "value": "discordApiMultiPartRequest", "description": "Operation: discordApiMultiPartRequest"},
                {"name": "requestApi", "value": "requestApi", "description": "Operation: requestApi"}
            ], "default": "sendLegacy", "description": "Operation to perform"},
            {"name": "webhookUri", "type": NodeParameterType.STRING, "display_name": "Webhook URL", "default": "", "required": True},
            {"name": "text", "type": NodeParameterType.STRING, "display_name": "Content", "default": ""},
            {"name": "options", "type": NodeParameterType.COLLECTION, "display_name": "Additional Fields", "default": "{", "description": "Whether this message be sent as a Text To Speech message"},
            {"name": "allowedMentions", "type": NodeParameterType.JSON, "display_name": "Allowed Mentions", "default": ""},
            {"name": "attachments", "type": NodeParameterType.JSON, "display_name": "Attachments", "default": ""},
            {"name": "avatarUrl", "type": NodeParameterType.STRING, "display_name": "Avatar URL", "default": ""},
            {"name": "components", "type": NodeParameterType.JSON, "display_name": "Components", "default": ""},
            {"name": "embeds", "type": NodeParameterType.JSON, "display_name": "Embeds", "default": ""},
            {"name": "flags", "type": NodeParameterType.NUMBER, "display_name": "Flags", "default": ""},
            {"name": "payloadJson", "type": NodeParameterType.JSON, "display_name": "JSON Payload", "default": ""},
            {"name": "username", "type": NodeParameterType.STRING, "display_name": "Username", "default": ""},
            {"name": "tts", "type": NodeParameterType.BOOLEAN, "display_name": "TTS", "default": False, "description": "Whether this message be sent as a Text To Speech message"},
            {"name": "authentication", "type": NodeParameterType.OPTIONS, "display_name": "Connection Type", "options": [
                {"name": "Bot Token", "value": "botToken"},
                {"name": "OAuth2", "value": "oAuth2"},
                {"name": "Webhook", "value": "webhook"}
            ], "default": "botToken", "description": "Manage messages, channels, and members on a server"},
            {"name": "OAuth2", "type": NodeParameterType.OPTIONS, "display_name": "Bot Token", "description": "Manage messages, channels, and members on a server"}
        ]

    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute the node operations.
        
        SYNC-CELERY SAFE: All HTTP calls use timeout parameter.
        
        Returns:
            List[List[NodeExecutionData]]: Nested list where outer list is output branches,
            inner list is items in that branch.
        """
        # Get input data from previous node
        input_data = self.get_input_data()
        
        # Handle empty input
        if not input_data:
            return [[]]
        
        return_items: List[NodeExecutionData] = []

        for i, item in enumerate(input_data):
            try:
                operation = self.get_node_parameter("operation", i)
                item_data = item.json_data if hasattr(item, 'json_data') else item.get('json', {})
                
                if operation == "sendLegacy":
                    result = self._sendLegacy(i, item_data)
                elif operation == "parseDiscordError":
                    result = self._parseDiscordError(i, item_data)
                elif operation == "prepareErrorData":
                    result = self._prepareErrorData(i, item_data)
                elif operation == "prepareOptions":
                    result = self._prepareOptions(i, item_data)
                elif operation == "prepareEmbeds":
                    result = self._prepareEmbeds(i, item_data)
                elif operation == "prepareMultiPartForm":
                    result = self._prepareMultiPartForm(i, item_data)
                elif operation == "checkAccessToGuild":
                    result = self._checkAccessToGuild(i, item_data)
                elif operation == "checkAccessToChannel":
                    result = self._checkAccessToChannel(i, item_data)
                elif operation == "setupChannelGetter":
                    result = self._setupChannelGetter(i, item_data)
                elif operation == "sendDiscordMessage":
                    result = self._sendDiscordMessage(i, item_data)
                elif operation == "createSendAndWaitMessageBody":
                    result = self._createSendAndWaitMessageBody(i, item_data)
                elif operation == "getGuildId":
                    result = self._getGuildId(i, item_data)
                elif operation == "checkBotAccessToGuild":
                    result = self._checkBotAccessToGuild(i, item_data)
                elif operation == "guildSearch":
                    result = self._guildSearch(i, item_data)
                elif operation == "channelSearch":
                    result = self._channelSearch(i, item_data)
                elif operation == "textChannelSearch":
                    result = self._textChannelSearch(i, item_data)
                elif operation == "categorySearch":
                    result = self._categorySearch(i, item_data)
                elif operation == "userSearch":
                    result = self._userSearch(i, item_data)
                elif operation == "getRoles":
                    result = self._getRoles(i, item_data)
                elif operation == "discordApiRequest":
                    result = self._discordApiRequest(i, item_data)
                elif operation == "discordApiMultiPartRequest":
                    result = self._discordApiMultiPartRequest(i, item_data)
                elif operation == "requestApi":
                    result = self._requestApi(i, item_data)
                else:
                    raise ValueError(f"Unknown operation: {operation}")
                
                # Handle array results
                if isinstance(result, list):
                    for r in result:
                        return_items.append(NodeExecutionData(json_data=r))
                else:
                    return_items.append(NodeExecutionData(json_data=result))
                    
            except Exception as e:
                logger.error(f"Error in operation {operation}: {e}")
                if self.continue_on_fail:
                    return_items.append(NodeExecutionData(json_data={"error": str(e)}))
                else:
                    raise
        
        return [return_items]

    def _api_request(
        self,
        method: str,
        endpoint: str,
        body: Dict[str, Any] | None = None,
        query: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """
        Make authenticated API request.
        
        SYNC-CELERY SAFE: Uses requests with timeout.
        """
        credentials = self.get_credentials("oauth2")
        
        # TODO: Configure authentication based on credential type
        query = query or {}
        # For API key auth: query["api_key"] = credentials.get("apiKey")
        # For Bearer auth: headers["Authorization"] = f"Bearer {credentials.get('accessToken')}"
        
        url = f"https://api-ssl.bitly.com/v4{endpoint}"
        
        response = requests.request(
            method,
            url,
            params=query,
            json=body,
            timeout=30,  # REQUIRED for Celery
        )
        response.raise_for_status()
        return response.json()

    def _sendLegacy(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        sendLegacy operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("sendLegacy operation not implemented")

    def _parseDiscordError(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        parseDiscordError operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("parseDiscordError operation not implemented")

    def _prepareErrorData(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        prepareErrorData operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("prepareErrorData operation not implemented")

    def _prepareOptions(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        prepareOptions operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("prepareOptions operation not implemented")

    def _prepareEmbeds(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        prepareEmbeds operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("prepareEmbeds operation not implemented")

    def _prepareMultiPartForm(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        prepareMultiPartForm operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("prepareMultiPartForm operation not implemented")

    def _checkAccessToGuild(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        checkAccessToGuild operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("checkAccessToGuild operation not implemented")

    def _checkAccessToChannel(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        checkAccessToChannel operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("checkAccessToChannel operation not implemented")

    def _setupChannelGetter(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        setupChannelGetter operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("setupChannelGetter operation not implemented")

    def _sendDiscordMessage(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        sendDiscordMessage operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("sendDiscordMessage operation not implemented")

    def _createSendAndWaitMessageBody(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        createSendAndWaitMessageBody operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("createSendAndWaitMessageBody operation not implemented")

    def _getGuildId(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        getGuildId operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("getGuildId operation not implemented")

    def _checkBotAccessToGuild(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        checkBotAccessToGuild operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("checkBotAccessToGuild operation not implemented")

    def _guildSearch(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        guildSearch operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("guildSearch operation not implemented")

    def _channelSearch(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        channelSearch operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("channelSearch operation not implemented")

    def _textChannelSearch(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        textChannelSearch operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("textChannelSearch operation not implemented")

    def _categorySearch(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        categorySearch operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("categorySearch operation not implemented")

    def _userSearch(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        userSearch operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("userSearch operation not implemented")

    def _getRoles(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        getRoles operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("getRoles operation not implemented")

    def _discordApiRequest(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        discordApiRequest operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("discordApiRequest operation not implemented")

    def _discordApiMultiPartRequest(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        discordApiMultiPartRequest operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("discordApiMultiPartRequest operation not implemented")

    def _requestApi(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        requestApi operation.
        
        Args:
            item_index: Index of the current item being processed
            item_data: JSON data from the input item
            
        Returns:
            Dict with operation result
            
        TODO: Implement operation logic.
        """
        # TODO: Extract parameters using item_index
        # param = self.get_node_parameter("paramName", item_index)
        
        # TODO: Make API call
        # response = self._api_request("GET", "/endpoint", query={"param": param})
        
        raise NotImplementedError("requestApi operation not implemented")

