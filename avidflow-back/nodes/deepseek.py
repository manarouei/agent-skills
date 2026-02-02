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

class DeepSeekNode(BaseNode):
    """
    DeepSeek node for integration with DeepSeek AI services.
    """
    
    type = "deepseek"
    version = 1.0
    
    description = {
        "displayName": "DeepSeek",
        "name": "deepseek",
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
                    {"name": "Chat", "value": "chat"},
                    {"name": "Completion", "value": "completion"}
                ],
                "default": "chat"
            },
            {
                "name": "model",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model",
                "required": True,
                "options": [
                    {"name": "DeepSeek Chat", "value": "deepseek-chat"},
                    {"name": "DeepSeek Coder", "value": "deepseek-coder"}
                ],
                "default": "deepseek-chat",
                "display_options": {
                    "show": {"resource": ["chat", "completion"]}
                }
            },
            {
                "name": "systemMessage",
                "type": NodeParameterType.STRING,
                "display_name": "System Message",
                "default": "",
                "display_options": {
                    "show": {"resource": ["chat"]}
                }
            },
            {
                "name": "message",
                "type": NodeParameterType.STRING,
                "display_name": "Message",
                "default": "",
                "display_options": {
                    "show": {"resource": ["chat"]}
                }
            },
            {
                "name": "prompt",
                "type": NodeParameterType.STRING,
                "display_name": "Prompt",
                "default": "",
                "display_options": {
                    "show": {"resource": ["completion"]}
                }
            },
            {
                "name": "temperature",
                "type": NodeParameterType.NUMBER,
                "display_name": "Temperature",
                "default": 0.7,
                "min": 0.0,
                "max": 2.0
            },
            {
                "name": "maxTokens",
                "type": NodeParameterType.NUMBER,
                "display_name": "Max Tokens",
                "default": 1024,
                "min": 1,
                "max": 4096
            },
            {
                "name": "topP",
                "type": NodeParameterType.NUMBER,
                "display_name": "Top P",
                "default": 0.9,
                "min": 0.0,
                "max": 1.0
            },
            {
                "name": "frequencyPenalty",
                "type": NodeParameterType.NUMBER,
                "display_name": "Frequency Penalty",
                "default": 0.0,
                "min": -2.0,
                "max": 2.0
            },
            {
                "name": "presencePenalty",
                "type": NodeParameterType.NUMBER,
                "display_name": "Presence Penalty",
                "default": 0.0,
                "min": -2.0,
                "max": 2.0
            }
        ],
        "credentials": [
            {
                "name": "deepseekApi",
                "required": True
            }
        ]
    }
    
    icon = "file:deepseek.svg"
    color = "#0b3954"

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute DeepSeek node operations"""
        try:
            resource = self.get_node_parameter("resource", 0, "chat")
            credentials = self.get_credentials("deepseekApi")
            
            if not credentials:
                return self.prepare_error_data("No credentials found. Please set up Grok API credentials.")
            
            headers = {
                "Authorization": f"Bearer {credentials['apiKey']}",
                "Content-Type": "application/json"
            }
            base_url = "https://api.deepseek.com/v1"
            
            if resource == "chat":
                return self._process_chat(headers, base_url)
            elif resource == "completion":
                return self._process_completion(headers, base_url)
            else:
                return self.prepare_error_data(f"Unsupported resource: {resource}")
                
        except Exception as e:
            return self.prepare_error_data(f"DeepSeek execution error: {str(e)}")

    def _process_chat(self, headers: Dict, base_url: str) -> List[List[NodeExecutionData]]:
        messages = self._prepare_chat_messages()
        model = self.get_node_parameter("model", 0, "deepseek-chat")
        
        payload = {
            "model": model,
            "messages": messages,
            "temperature": self.get_node_parameter("temperature", 0, 0.7),
            "max_tokens": self.get_node_parameter("maxTokens", 0, 1024),
            "top_p": self.get_node_parameter("topP", 0, 0.9),
            "frequency_penalty": self.get_node_parameter("frequencyPenalty", 0, 0.0),
            "presence_penalty": self.get_node_parameter("presencePenalty", 0, 0.0),
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            return [[NodeExecutionData(
                json_data={
                    "response": result["choices"][0]["message"]["content"],
                    "usage": result.get("usage", {}),
                    "model": result.get("model", model)
                }
            )]]
            
        except requests.HTTPError as http_err:
            return self.prepare_error_data(
                f"DeepSeek API error [{http_err.response.status_code}]: {http_err.response.text}"
            )
        except Exception as e:
            return self.prepare_error_data(f"Chat processing failed: {str(e)}")

    def _process_completion(self, headers: Dict, base_url: str) -> List[List[NodeExecutionData]]:
        prompt = self.get_node_parameter("prompt", 0, "")
        model = self.get_node_parameter("model", 0, "deepseek-coder")
        
        payload = {
            "model": model,
            "prompt": prompt,
            "temperature": self.get_node_parameter("temperature", 0, 0.7),
            "max_tokens": self.get_node_parameter("maxTokens", 0, 1024),
            "top_p": self.get_node_parameter("topP", 0, 0.9),
            "frequency_penalty": self.get_node_parameter("frequencyPenalty", 0, 0.0),
            "presence_penalty": self.get_node_parameter("presencePenalty", 0, 0.0),
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{base_url}/completions",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            return [[NodeExecutionData(
                json_data={
                    "text": result["choices"][0]["text"],
                    "usage": result.get("usage", {}),
                    "model": result.get("model", model)
                }
            )]]
            
        except requests.HTTPError as http_err:
            return self.prepare_error_data(
                f"DeepSeek API error [{http_err.response.status_code}]: {http_err.response.text}"
            )
        except Exception as e:
            return self.prepare_error_data(f"Completion processing failed: {str(e)}")

    def _prepare_chat_messages(self) -> List[Dict]:
        messages = []
        
        if system_msg := self.get_node_parameter("systemMessage", 0, ""):
            messages.append({"role": "system", "content": system_msg})
            
        if user_msg := self.get_node_parameter("message", 0, ""):
            messages.append({"role": "user", "content": user_msg})
        
        return messages
    
    def prepare_error_data(self, error_message: str) -> List[List[NodeExecutionData]]:
        return [[NodeExecutionData(json_data={"error": error_message})]]