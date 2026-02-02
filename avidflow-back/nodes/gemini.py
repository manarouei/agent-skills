import requests
from typing import Dict, List, Optional, Any, Union
import logging
import json
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)

class GeminiNode(BaseNode):
    """
    Gemini node for accessing Google's Gemini AI models
    """
    
    type = "gemini"
    version = 1.0
    
    description = {
        "displayName": "Gemini",
        "name": "gemini",
        "icon": "file:gemini.svg",
        "group": ["input"],
        "description": "Access Google's Gemini AI models",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
        "credentials": [
            {
                "name": "geminiApi",
                "required": True
            }
        ]
    }
    
    properties = {
        "parameters": [
            {
                "name": "resource",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Resource",
                "options": [
                    {"name": "Text", "value": "text"},
                    {"name": "Chat", "value": "chat"}
                ],
                "default": "text",
                "description": "The resource to operate on"
            },
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Generate", "value": "generate", "description": "Generate content"}
                ],
                "default": "generate"
            },
            {
                "name": "model",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model",
                "options": [
                    {"name": "Gemini 1.5 Flash", "value": "gemini-1.5-flash"},
                    {"name": "Gemini 1.5 Pro", "value": "gemini-1.5-pro"},
                    {"name": "Gemini Pro", "value": "gemini-pro"},
                    {"name": "Gemini Pro Vision", "value": "gemini-pro-vision"}
                ],
                "default": "gemini-1.5-flash",
                "description": "The Gemini model to use"
            },
            {
                "name": "prompt",
                "type": NodeParameterType.STRING,
                "display_name": "Prompt",
                "default": "",
                "required": True,
                "description": "The prompt to send to Gemini",
                "typeOptions": {
                    "rows": 3
                }
            },
            {
                "name": "temperature",
                "type": NodeParameterType.NUMBER,
                "display_name": "Temperature",
                "default": 0.7,
                "description": "Controls randomness in the output (0.0 to 1.0)",
                "typeOptions": {
                    "minValue": 0.0,
                    "maxValue": 1.0,
                    "numberPrecision": 1
                }
            },
            {
                "name": "maxTokens",
                "type": NodeParameterType.NUMBER,
                "display_name": "Max Output Tokens",
                "default": 1024,
                "description": "Maximum number of tokens to generate",
                "typeOptions": {
                    "minValue": 1,
                    "maxValue": 8192
                }
            },
            {
                "name": "topP",
                "type": NodeParameterType.NUMBER,
                "display_name": "Top P",
                "default": 0.9,
                "description": "Nucleus sampling parameter (0.0 to 1.0)",
                "typeOptions": {
                    "minValue": 0.0,
                    "maxValue": 1.0,
                    "numberPrecision": 1
                }
            },
            {
                "name": "topK",
                "type": NodeParameterType.NUMBER,
                "display_name": "Top K",
                "default": 40,
                "description": "Top-k sampling parameter",
                "typeOptions": {
                    "minValue": 1,
                    "maxValue": 100
                }
            }
        ],
        "credentials": [
            {
                "name": "geminiApi",
                "required": True
            }
        ]
    }
    
    icon = "gemini.svg"
    color = "#4285F4"

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Gemini operations"""
        try:
            input_data = self.get_input_data()
            result_items = []
            
            for i, item in enumerate(input_data):
                try:
                    resource = self.get_node_parameter("resource", i, "text")
                    operation = self.get_node_parameter("operation", i, "generate")
                    
                    if resource == 'text' and operation == 'generate':
                        result = self._generate_text(i)
                    elif resource == 'chat' and operation == 'generate':
                        result = self._generate_chat(i)
                    else:
                        raise ValueError(f"Unsupported operation '{operation}' for resource '{resource}'")
                    
                    result_items.append(NodeExecutionData(
                        json_data=result,
                        item_index=i,
                        binary_data=None
                    ))
                    
                except Exception as e:
                    logger.error(f"Gemini Node - Error processing item {i}: {str(e)}")
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": self.get_node_parameter("resource", i, "text"),
                            "operation": self.get_node_parameter("operation", i, "generate"),
                            "item_index": i
                        },
                        binary_data=None
                    )
                    result_items.append(error_item)
            
            return [result_items]
            
        except Exception as e:
            logger.error(f"Gemini Node - Execute error: {str(e)}")
            error_data = [NodeExecutionData(
                json_data={"error": f"Error in Gemini node: {str(e)}"},
                binary_data=None
            )]
            return [error_data]

    def _get_credentials(self) -> Dict[str, Any]:
        """Get Gemini API credentials"""
        credentials = self.get_credentials("geminiApi")
        if not credentials:
            raise ValueError("Gemini API credentials not found")
        return credentials

    def _generate_text(self, item_index: int) -> Dict[str, Any]:
        """Generate text using Gemini API"""
        try:
            credentials = self._get_credentials()
            
            # Extract credential data
            if isinstance(credentials, dict) and 'data' in credentials:
                cred_data = credentials['data']
            else:
                cred_data = credentials
            
            api_key = cred_data.get('apiKey', '')
            base_url = cred_data.get('baseUrl', 'https://generativelanguage.googleapis.com/v1beta')
            
            if not api_key:
                raise ValueError("API key not found in credentials")
            
            # Get parameters
            model = self.get_node_parameter("model", item_index, "gemini-1.5-flash")
            prompt = self.get_node_parameter("prompt", item_index, "")
            temperature = self.get_node_parameter("temperature", item_index, 0.7)
            max_tokens = self.get_node_parameter("maxTokens", item_index, 1024)
            top_p = self.get_node_parameter("topP", item_index, 0.9)
            top_k = self.get_node_parameter("topK", item_index, 40)
            
            if not prompt:
                raise ValueError("Prompt is required")
            
            # Prepare the request
            url = f"{base_url}/models/{model}:generateContent"
            
            headers = {
                "Content-Type": "application/json"
            }
            
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                    "topP": top_p,
                    "topK": top_k
                }
            }
            
            # Add API key as query parameter
            params = {"key": api_key}
            
            # Make the request
            response = requests.post(url, json=payload, headers=headers, params=params, timeout=60)
            response.raise_for_status()
            
            response_data = response.json()
            
            # Extract the generated text
            candidates = response_data.get('candidates', [])
            if not candidates:
                raise ValueError("No candidates returned from Gemini API")
            
            content = candidates[0].get('content', {})
            parts = content.get('parts', [])
            if not parts:
                raise ValueError("No content parts returned from Gemini API")
            
            generated_text = parts[0].get('text', '')
            
            return {
                "text": generated_text,
                "model": model,
                "prompt": prompt,
                "usage": response_data.get('usageMetadata', {}),
                "candidates": candidates,
                "raw_response": response_data
            }
            
        except requests.RequestException as e:
            error_msg = str(e)
            try:
                if hasattr(e, 'response') and e.response:
                    error_data = e.response.json()
                    error_msg = f"Gemini API Error: {error_data.get('error', {}).get('message', 'Unknown error')}"
            except:
                pass
            logger.error(f"Gemini API request failed: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"Error generating text with Gemini: {str(e)}")
            raise

    def _generate_chat(self, item_index: int) -> Dict[str, Any]:
        """Generate chat response using Gemini API (similar to text generation)"""
        # For now, we'll use the same implementation as text generation
        # This can be extended later for multi-turn conversations
        return self._generate_text(item_index)