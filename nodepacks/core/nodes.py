"""
Core Nodes - Essential utility node implementations.

These nodes provide basic workflow functionality.
All are SYNC-CELERY SAFE.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

import requests

from src.node_sdk.basenode import BaseNode, NodeExecutionData, NodeOperationError


logger = logging.getLogger(__name__)


class ManualTriggerNode(BaseNode):
    """
    Manual Trigger - Start a workflow manually.
    
    This node serves as a workflow entry point when triggered manually.
    It passes through empty data or can inject test data.
    """
    
    type = "n8n-nodes-base.manualTrigger"
    version = 1
    
    description = {
        "displayName": "Manual Trigger",
        "name": "manualTrigger",
        "icon": "fa:play",
        "group": ["trigger"],
        "description": "Starts the workflow when triggered manually",
        "version": 1,
        "inputs": [],  # No inputs - this is a trigger
        "outputs": ["main"],
    }
    
    properties = {
        "parameters": [],
        "credentials": [],
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Return single empty item to start workflow."""
        return [[{"json": {}}]]


class SetNode(BaseNode):
    """
    Set Node - Set or modify data fields.
    
    Allows setting new fields or modifying existing ones
    on workflow items.
    """
    
    type = "n8n-nodes-base.set"
    version = 1
    
    description = {
        "displayName": "Set",
        "name": "set",
        "icon": "fa:pen",
        "group": ["transform"],
        "description": "Sets values on items",
        "version": 1,
        "inputs": ["main"],
        "outputs": ["main"],
    }
    
    properties = {
        "parameters": [
            {
                "displayName": "Mode",
                "name": "mode",
                "type": "options",
                "default": "manual",
                "options": [
                    {"name": "Manual", "value": "manual"},
                    {"name": "Raw JSON", "value": "raw"},
                ],
            },
            {
                "displayName": "Values",
                "name": "values",
                "type": "collection",
                "default": {},
                "displayOptions": {"show": {"mode": ["manual"]}},
            },
            {
                "displayName": "JSON Data",
                "name": "jsonData",
                "type": "json",
                "default": "{}",
                "displayOptions": {"show": {"mode": ["raw"]}},
            },
            {
                "displayName": "Keep Only Set",
                "name": "keepOnlySet",
                "type": "boolean",
                "default": False,
                "description": "If true, only keep the set values, discard others",
            },
        ],
        "credentials": [],
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Set values on items."""
        items = self.get_input_data()
        mode = self.get_node_parameter("mode", 0, "manual")
        keep_only_set = self.get_node_parameter("keepOnlySet", 0, False)
        
        results = []
        for i, item in enumerate(items):
            item_json = item.get("json", {})
            
            if mode == "raw":
                # Parse raw JSON
                json_data = self.get_node_parameter("jsonData", i, "{}")
                if isinstance(json_data, str):
                    try:
                        new_data = json.loads(json_data)
                    except json.JSONDecodeError:
                        new_data = {}
                else:
                    new_data = json_data
            else:
                # Manual mode - get values
                new_data = self.get_node_parameter("values", i, {})
            
            if keep_only_set:
                output = new_data
            else:
                output = {**item_json, **new_data}
            
            results.append({
                "json": output,
                "pairedItem": {"item": i},
            })
        
        return [results]


class CodeNode(BaseNode):
    """
    Code Node - Execute custom Python code.
    
    Runs user-provided Python code on workflow items.
    Code has access to input items and can return transformed items.
    
    SECURITY: This executes arbitrary code - use with caution.
    SYNC-CELERY SAFE: Code must be synchronous.
    """
    
    type = "n8n-nodes-base.code"
    version = 1
    
    description = {
        "displayName": "Code",
        "name": "code",
        "icon": "fa:code",
        "group": ["transform"],
        "description": "Execute custom Python code",
        "version": 1,
        "inputs": ["main"],
        "outputs": ["main"],
    }
    
    properties = {
        "parameters": [
            {
                "displayName": "Mode",
                "name": "mode",
                "type": "options",
                "default": "runOnceForAllItems",
                "options": [
                    {"name": "Run Once for All Items", "value": "runOnceForAllItems"},
                    {"name": "Run Once for Each Item", "value": "runOnceForEachItem"},
                ],
            },
            {
                "displayName": "Python Code",
                "name": "code",
                "type": "code",
                "default": "# Available variables:\n# items - list of input items\n# Return: list of output items\n\nreturn items",
            },
        ],
        "credentials": [],
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute custom code."""
        items = self.get_input_data()
        mode = self.get_node_parameter("mode", 0, "runOnceForAllItems")
        code = self.get_node_parameter("code", 0, "return items")
        
        # Create execution namespace
        namespace = {
            "items": items,
            "__builtins__": __builtins__,
        }
        
        try:
            if mode == "runOnceForAllItems":
                # Run code once with all items
                exec(f"__result__ = ({code})", namespace)
                result_items = namespace.get("__result__", items)
            else:
                # Run code for each item
                result_items = []
                for i, item in enumerate(items):
                    namespace["item"] = item
                    namespace["index"] = i
                    exec(f"__result__ = ({code})", namespace)
                    result = namespace.get("__result__", item)
                    if isinstance(result, list):
                        result_items.extend(result)
                    else:
                        result_items.append(result)
            
            # Normalize to NodeExecutionData format
            output = []
            for i, item in enumerate(result_items):
                if isinstance(item, dict):
                    if "json" in item:
                        output.append(item)
                    else:
                        output.append({"json": item, "pairedItem": {"item": i}})
                else:
                    output.append({"json": {"data": item}, "pairedItem": {"item": i}})
            
            return [output]
            
        except Exception as e:
            raise NodeOperationError(f"Code execution failed: {e}")


class NoOpNode(BaseNode):
    """
    No Operation Node - Pass-through.
    
    Simply passes input items through unchanged.
    Useful for organizing workflows.
    """
    
    type = "n8n-nodes-base.noOp"
    version = 1
    
    description = {
        "displayName": "No Operation",
        "name": "noOp",
        "icon": "fa:arrow-right",
        "group": ["transform"],
        "description": "No operation - passes items through",
        "version": 1,
        "inputs": ["main"],
        "outputs": ["main"],
    }
    
    properties = {
        "parameters": [],
        "credentials": [],
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Pass through items unchanged."""
        items = self.get_input_data()
        return [[
            {"json": item.get("json", {}), "pairedItem": {"item": i}}
            for i, item in enumerate(items)
        ]]


class HttpRequestNode(BaseNode):
    """
    HTTP Request Node - Make HTTP requests.
    
    Supports GET, POST, PUT, DELETE, PATCH methods.
    SYNC-CELERY SAFE: Uses requests with timeout.
    """
    
    type = "n8n-nodes-base.httpRequest"
    version = 1
    
    description = {
        "displayName": "HTTP Request",
        "name": "httpRequest",
        "icon": "fa:globe",
        "group": ["input", "output"],
        "description": "Make HTTP requests",
        "version": 1,
        "inputs": ["main"],
        "outputs": ["main"],
    }
    
    properties = {
        "parameters": [
            {
                "displayName": "Method",
                "name": "method",
                "type": "options",
                "default": "GET",
                "options": [
                    {"name": "GET", "value": "GET"},
                    {"name": "POST", "value": "POST"},
                    {"name": "PUT", "value": "PUT"},
                    {"name": "DELETE", "value": "DELETE"},
                    {"name": "PATCH", "value": "PATCH"},
                ],
            },
            {
                "displayName": "URL",
                "name": "url",
                "type": "string",
                "default": "",
                "required": True,
            },
            {
                "displayName": "Headers",
                "name": "headers",
                "type": "json",
                "default": "{}",
            },
            {
                "displayName": "Body",
                "name": "body",
                "type": "json",
                "default": "{}",
                "displayOptions": {"show": {"method": ["POST", "PUT", "PATCH"]}},
            },
            {
                "displayName": "Timeout",
                "name": "timeout",
                "type": "number",
                "default": 30,
                "description": "Timeout in seconds",
            },
        ],
        "credentials": [],
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Make HTTP request."""
        items = self.get_input_data()
        results = []
        
        for i, item in enumerate(items):
            method = self.get_node_parameter("method", i, "GET")
            url = self.get_node_parameter("url", i, "")
            headers_json = self.get_node_parameter("headers", i, "{}")
            body_json = self.get_node_parameter("body", i, "{}")
            timeout = self.get_node_parameter("timeout", i, 30)
            
            if not url:
                raise NodeOperationError("URL is required")
            
            # Parse headers
            if isinstance(headers_json, str):
                try:
                    headers = json.loads(headers_json)
                except json.JSONDecodeError:
                    headers = {}
            else:
                headers = headers_json
            
            # Parse body
            if isinstance(body_json, str):
                try:
                    body = json.loads(body_json)
                except json.JSONDecodeError:
                    body = None
            else:
                body = body_json
            
            # Make request (SYNC-CELERY SAFE: timeout required)
            try:
                response = requests.request(
                    method=method,
                    url=url,
                    headers=headers,
                    json=body if method in ("POST", "PUT", "PATCH") else None,
                    timeout=timeout,
                )
                
                # Parse response
                try:
                    response_data = response.json()
                except json.JSONDecodeError:
                    response_data = {"text": response.text}
                
                results.append({
                    "json": {
                        "statusCode": response.status_code,
                        "headers": dict(response.headers),
                        "body": response_data,
                    },
                    "pairedItem": {"item": i},
                })
                
            except requests.Timeout:
                raise NodeOperationError(f"Request timed out after {timeout}s")
            except requests.RequestException as e:
                if self.continue_on_fail:
                    results.append({
                        "json": {"error": str(e)},
                        "pairedItem": {"item": i},
                    })
                else:
                    raise NodeOperationError(f"Request failed: {e}")
        
        return [results]


# Export all nodes
__all__ = [
    "ManualTriggerNode",
    "SetNode",
    "CodeNode",
    "NoOpNode",
    "HttpRequestNode",
]
