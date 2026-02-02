from typing import Dict, List, Optional, Any, Union
from models import NodeExecutionData, Node, WorkflowModel
from .base import BaseNode, NodeParameter, NodeParameterType, NodeRunMode
from credentials.grokApi import GrokApiCredential
import requests
import json
import base64
import os
import copy
import logging

logger = logging.getLogger(__name__)

class GrokNode(BaseNode):
    """
    Grok node for integration with xAI's Grok services.
    """
    
    type = "grok"
    version = 1.0
    
    description = {
        "displayName": "Grok",
        "name": "grok",
        "group": ["transform"],
        "inputs": [
            {"name": "main", "type": "main", "required": True}
        ],
        "outputs": [
            {"name": "main", "type": "main", "required": True}
        ],
    }
    
    properties = {
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "required": True,
                "options": [
                    {
                        "name": "Chat",
                        "value": "chat"
                    },
                    {
                        "name": "Text",
                        "value": "text"
                    }
                ],
                "default": "chat"
            },
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["chat", "text"]
                    }
                },
                "options": [
                    {
                        "name": "Completion",
                        "value": "completion"
                    }
                ],
                "default": "completion"
            },
            {
                "name": "model",
                "type": NodeParameterType.STRING,
                "display_name": "Model",
                "default": "grok-3",
                "display_options": {
                    "show": {
                        "resource": ["chat", "text"]
                    }
                }
            },
            {
                "name": "systemMessage",
                "type": NodeParameterType.STRING,
                "display_name": "System Message",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["chat"]
                    }
                }
            },
            {
                "name": "message",
                "type": NodeParameterType.STRING,
                "display_name": "Message",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["chat"]
                    }
                }
            },
            {
                "name": "temperature",
                "type": NodeParameterType.NUMBER,
                "display_name": "Temperature",
                "default": 0.7,
                "display_options": {
                    "show": {
                        "resource": ["chat", "text"]
                    }
                }
            },
            {
                "name": "maxTokens",
                "type": NodeParameterType.NUMBER,
                "display_name": "Max Tokens",
                "default": 100,
                "display_options": {
                    "show": {
                        "resource": ["chat", "text"]
                    }
                }
            },
            {
                "name": "prompt",
                "type": NodeParameterType.STRING,
                "display_name": "Prompt",
                "default": "",
                "display_options": {
                    "show": {
                        "resource": ["text"],
                        "operation": ["completion"]
                    }
                }
            },
            {
                "name": "contextItems",
                "type": NodeParameterType.NUMBER,
                "display_name": "Context Items",
                "default": 10,
                "description": "Number of previous messages to include as context",
                "display_options": {
                    "show": {
                        "resource": ["chat"]
                    }
                }
            },
            {
                "name": "topP",
                "type": NodeParameterType.NUMBER,
                "display_name": "Top P",
                "default": 0.9,
                "display_options": {
                    "show": {
                        "resource": ["chat", "text"]
                    }
                }
            }
        ],
        "credentials": [
            {
                "name": "grokApi",
                "required": True
            }
        ]
    }
    
    icon = "file:grok.svg"
    color = "#0b3954"

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Grok node operations"""
        
        try:
            # Get parameters
            resource = self.get_node_parameter("resource", 0, "chat")
            operation = self.get_node_parameter("operation", 0, "completion")
            
            # Get credentials
            credentials = self.get_credentials("grokApi")
            
            if not credentials:
                return self.prepare_error_data("No credentials found. Please set up Grok API credentials.")
            
            
            # Use direct access to credential properties rather than converting to GrokApiCredential
            headers = {
                "Authorization": f"Bearer {credentials['apiKey']}",
                "Content-Type": "application/json"
            }
            base_url = "https://api.x.ai/v1"  # Fixed endpoint for X.AI
            
            result_items: List[NodeExecutionData] = []
            
            # Execute based on resource type
            if resource == "chat":
                result_items = self._process_chat(headers, base_url, operation)
            elif resource == "text":
                result_items = self._process_text(headers, base_url, operation)
            else:
                return self.prepare_error_data(f"Resource {resource} is not supported")

            return [result_items]

        except Exception as e:
            return self.prepare_error_data(f"Error executing Grok node: {str(e)}")

    def _process_chat(self, headers: Dict, base_url: str, operation: str) -> List[NodeExecutionData]:
        """Handle chat operations"""
        if operation == "completion":
            messages = self._prepare_chat_messages()
            
            model = self.get_node_parameter("model", 0, "grok-3")
            temperature = self.get_node_parameter("temperature", 0, 0.7)
            max_tokens = self.get_node_parameter("maxTokens", 0, 100)
            top_p = self.get_node_parameter("topP", 0, 0.9)
            
            data = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p
            }
            
            # Use the correct endpoint for X.AI
            endpoint = f"{base_url}/chat/completions"
            
            # Create a session with SSL verification disabled
            session = requests.Session()
            
            try:
                # Make API request
                response = session.post(
                    endpoint,
                    headers=headers,
                    json=data,
                    timeout=60
                )
                
                if response.status_code < 400:
                    result = response.json()
                    return [NodeExecutionData(
                        json_data={
                            "response": result["choices"][0]["message"]["content"],
                            "usage": result.get("usage", {}),
                            "model": result.get("model", model)
                        },
                        binary_data=None
                    )]
                else:
                    # Handle specific error for no credits
                    if "doesn't have any credits yet" in response.text or "purchase credits" in response.text:
                        return [NodeExecutionData(
                            json_data={
                                "error": "Your X.AI account needs credits to use the Grok API. Please purchase credits at https://console.x.ai/team to use this service."
                            },
                            binary_data=None
                        )]
                    else:
                        return [NodeExecutionData(
                            json_data={"error": f"Grok API error: {response.text}"},
                            binary_data=None
                        )]
                        
            except Exception as e:
                return [NodeExecutionData(
                    json_data={"error": f"Error connecting to Grok API: {str(e)}"},
                    binary_data=None
                )]
    
        return [NodeExecutionData(
            json_data={"error": f"Operation {operation} is not supported"},
            binary_data=None
        )]

    def _process_text(self, headers: Dict, base_url: str, operation: str) -> List[NodeExecutionData]:
        """Handle text operations"""
        if operation == "completion":
            model = self.get_node_parameter("model", 0, "grok-3")
            prompt = self.get_node_parameter("prompt", 0, "")
            max_tokens = self.get_node_parameter("maxTokens", 0, 100)
            temperature = self.get_node_parameter("temperature", 0, 0.7)
            top_p = self.get_node_parameter("topP", 0, 0.9)
            
            data = {
                "model": model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p
            }
            
            try:
                response = requests.post(
                    f"{base_url}/completions",
                    headers=headers,
                    json=data,
                    timeout=60
                )
            except requests.exceptions.RequestException as req_err:
                return [NodeExecutionData(
                    json_data={"error": f"Error connecting to Grok API: {str(req_err)}"},
                    binary_data=None
                )]
        
            if response.status_code >= 400:
                return [NodeExecutionData(
                    json_data={"error": f"Grok API error {response.status_code}: {response.text}"},
                    binary_data=None
                )]

            try:
                result = response.json()

                return [NodeExecutionData(
                    json_data={
                        "text": result["choices"][0]["text"],
                        "usage": result.get("usage", {}),
                        "model": result.get("model", model)
                    },
                    binary_data=None
                )]
            except (KeyError, ValueError, json.JSONDecodeError) as parse_err:
                return [NodeExecutionData(
                    json_data={"error": f"Error parsing API response: {str(parse_err)}"},
                    binary_data=None
                )]

        return [NodeExecutionData(
            json_data={"error": f"Operation {operation} is not supported"},
            binary_data=None
        )]

    def _prepare_chat_messages(self) -> List[Dict]:
        """Prepare chat messages from parameters"""
        messages = []
        
        system_message = self.get_node_parameter("systemMessage", 0, "")
        if system_message:
            messages.append({
                "role": "system",
                "content": system_message
            })
            
        message_content = self.get_node_parameter("message", 0, "")
        if message_content:
            messages.append({
                "role": "user",
                "content": message_content
            })
        
        # Process previous conversation context if needed
        context_items = self.get_node_parameter("contextItems", 0, 10)
        if context_items > 0:
            # This would be used to retrieve previous conversation context
            # The implementation would depend on how conversation history is stored
            pass
        
        return messages
    
    def prepare_error_data(self, error_message: str) -> List[List[NodeExecutionData]]:
        """Create error data structure for failed Grok executions"""
        return [[NodeExecutionData(
            json_data={"error": str(error_message)},
            binary_data=None
        )]]