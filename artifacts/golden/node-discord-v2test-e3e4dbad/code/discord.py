#!/usr/bin/env python3
"""
Discord Node

Converted from TypeScript by agent-skills/code-convert
Correlation ID: node-discord-v2test-e3e4dbad
Generated: 2026-01-06T04:47:27.221655

SYNC-CELERY SAFE: All methods are synchronous with timeouts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from .base import BaseNode, NodeParameterType, NodeExecutionData

logger = logging.getLogger(__name__)


class DiscordNode(BaseNode):
    """
    Discord node.
    
    
    """

    type = "discord"
    version = 1
    
    description = {
        "displayName": "Discord",
        "name": "discord",
        "icon": "file:discord.svg",
        "group": ['output'],
        "description": "",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
    }
    
    properties = {
        "parameters": [
            {"name": "resource", "type": NodeParameterType.OPTIONS, "display_name": "Resource", "options": [
                {"name": "Channel", "value": "channel"},
                {"name": "Message", "value": "message"},
                {"name": "Member", "value": "member"}
            ], "default": "channel", "description": "The resource to operate on"},
            {"name": "authentication", "type": NodeParameterType.OPTIONS, "display_name": "Connection Type", "options": [
                {"name": "Bot Token", "value": "botToken"},
                {"name": "OAuth2", "value": "oAuth2"},
                {"name": "Webhook", "value": "webhook"}
            ], "default": "botToken"}
        ],
        "credentials": [
            {"name": "discordBotApi", "required": True}
        ]
    }
    
    icon = "discord.svg"

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
                
                if operation == "execute":
                    result = self._execute(i, item_data)
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
        credentials = self.get_credentials("discordBotApi")
        
        # Build headers based on credential type
        headers = {}
        if credentials.get("accessToken"):
            headers["Authorization"] = f"Bot {credentials.get('accessToken')}"
        elif credentials.get("apiKey"):
            query = query or {}
            query["api_key"] = credentials.get("apiKey")
        
        url = f"https://api.example.com{endpoint}"
        
        response = requests.request(
            method,
            url,
            params=query,
            json=body,
            headers=headers,
            timeout=30,  # REQUIRED for Celery
        )
        response.raise_for_status()
        return response.json()

    def _execute(self, item_index: int, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        execute operation.
        
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
        
        raise NotImplementedError("execute operation not implemented")

