import requests
from typing import Dict, List, Optional, Any, Union
import logging
import json
import base64
from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)

class QwenNode(BaseNode):
    """
    Qwen node for accessing Alibaba's Qwen AI models
    """
    
    type = "qwen"
    version = 1.0
    
    description = {
        "displayName": "Qwen",
        "name": "qwen",
        "icon": "file:qwen.svg",
        "group": ["input"],
        "description": "Access Alibaba's Qwen AI models",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "main", "type": "main", "required": True}],
        "usableAsTool": True,
        "credentials": [
            {
                "name": "qwenApi",
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
                    {"name": "Chat", "value": "chat"},
                    {"name": "Embeddings", "value": "embeddings"},
                    {"name": "Image", "value": "image"},
                    {"name": "Function", "value": "function"}
                ],
                "default": "chat",
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
                    {"name": "Qwen Turbo", "value": "qwen-turbo"},
                    {"name": "Qwen Plus", "value": "qwen-plus"},
                    {"name": "Qwen Max", "value": "qwen-max"},
                    {"name": "Qwen VL", "value": "qwen-vl"},
                    {"name": "Qwen Embedding", "value": "text-embedding-v1"}
                ],
                "default": "qwen-turbo",
                "description": "The Qwen model to use"
            },
            {
                "name": "prompt",
                "type": NodeParameterType.STRING,
                "display_name": "Prompt",
                "default": "",
                "required": True,
                "description": "The prompt to send to Qwen",
                "typeOptions": {
                    "rows": 3
                },
                "displayOptions": {
                    "show": {
                        "resource": ["text", "chat", "image", "function"]
                    }
                }
            },
            {
                "name": "text",
                "type": NodeParameterType.STRING,
                "display_name": "Text",
                "default": "",
                "required": True,
                "description": "The text to generate embeddings for",
                "typeOptions": {
                    "rows": 3
                },
                "displayOptions": {
                    "show": {
                        "resource": ["embeddings"]
                    }
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
                },
                "displayOptions": {
                    "show": {
                        "resource": ["text", "chat", "function"]
                    }
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
                },
                "displayOptions": {
                    "show": {
                        "resource": ["text", "chat", "function"]
                    }
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
                },
                "displayOptions": {
                    "show": {
                        "resource": ["text", "chat", "function"]
                    }
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
                },
                "displayOptions": {
                    "show": {
                        "resource": ["text", "chat", "function"]
                    }
                }
            },
            {
                "name": "imagePrompt",
                "type": NodeParameterType.STRING,
                "display_name": "Image Prompt",
                "default": "",
                "required": True,
                "description": "The text prompt for image generation",
                "typeOptions": {
                    "rows": 3
                },
                "displayOptions": {
                    "show": {
                        "resource": ["image"]
                    }
                }
            },
            {
                "name": "imageSize",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Image Size",
                "options": [
                    {"name": "1024x1024", "value": "1024*1024"},
                    {"name": "720x1280", "value": "720*1280"},
                    {"name": "1280x720", "value": "1280*720"}
                ],
                "default": "1024*1024",
                "description": "The size of the generated image",
                "displayOptions": {
                    "show": {
                        "resource": ["image"]
                    }
                }
            },
            {
                "name": "functions",
                "type": NodeParameterType.JSON,
                "display_name": "Functions",
                "default": "[]",
                "description": "JSON array of function definitions the model may call",
                "displayOptions": {
                    "show": {
                        "resource": ["function"]
                    }
                }
            },
            {
                "name": "returnJson",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Return as JSON",
                "default": true,
                "description": "Whether to return embeddings as a parsed JSON object",
                "displayOptions": {
                    "show": {
                        "resource": ["embeddings"]
                    }
                }
            }
        ],
        "credentials": [
            {
                "name": "qwenApi",
                "required": True
            }
        ]
    }
    
    icon = "qwen.svg"
    color = "#FF6A00"  # Alibaba's orange color

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Qwen operations"""
        try:
            input_data = self.get_input_data()
            result_items = []
            
            for i, item in enumerate(input_data):
                try:
                    resource = self.get_node_parameter("resource", i, "chat")
                    operation = self.get_node_parameter("operation", i, "generate")
                    
                    if resource == 'text' and operation == 'generate':
                        result = self._generate_text(i)
                    elif resource == 'chat' and operation == 'generate':
                        result = self._generate_chat(i)
                    elif resource == 'embeddings' and operation == 'generate':
                        result = self._generate_embeddings(i)
                    elif resource == 'image' and operation == 'generate':
                        result = self._generate_image(i)
                    elif resource == 'function' and operation == 'generate':
                        result = self._generate_function_call(i)
                    else:
                        raise ValueError(f"Unsupported operation '{operation}' for resource '{resource}'")
                    
                    result_items.append(NodeExecutionData(
                        json_data=result,
                        item_index=i,
                        binary_data=None
                    ))
                    
                except Exception as e:
                    logger.error(f"Qwen Node - Error processing item {i}: {str(e)}")
                    error_item = NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "resource": self.get_node_parameter("resource", i, "chat"),
                            "operation": self.get_node_parameter("operation", i, "generate"),
                            "item_index": i
                        },
                        binary_data=None
                    )
                    result_items.append(error_item)
            
            return [result_items]
            
        except Exception as e:
            logger.error(f"Qwen Node - Execute error: {str(e)}")
            error_data = [NodeExecutionData(
                json_data={"error": f"Error in Qwen node: {str(e)}"},
                binary_data=None
            )]
            return [error_data]

    def _get_credentials(self) -> Dict[str, Any]:
        """Get Qwen API credentials"""
        credentials = self.get_credentials("qwenApi")
        if not credentials:
            raise ValueError("Qwen API credentials not found")
        return credentials

    def _generate_text(self, item_index: int) -> Dict[str, Any]:
        """Generate text using Qwen API"""
        try:
            credentials = self._get_credentials()
            
            # Extract credential data
            if isinstance(credentials, dict) and 'data' in credentials:
                cred_data = credentials['data']
            else:
                cred_data = credentials
            
            api_key = cred_data.get('apiKey', '')
            base_url = cred_data.get('baseUrl', 'https://dashscope.aliyuncs.com/api/v1')
            
            if not api_key:
                raise ValueError("API key not found in credentials")
            
            # Get parameters
            model = self.get_node_parameter("model", item_index, "qwen-turbo")
            prompt = self.get_node_parameter("prompt", item_index, "")
            temperature = self.get_node_parameter("temperature", item_index, 0.7)
            max_tokens = self.get_node_parameter("maxTokens", item_index, 1024)
            top_p = self.get_node_parameter("topP", item_index, 0.9)
            top_k = self.get_node_parameter("topK", item_index, 40)
            
            if not prompt:
                raise ValueError("Prompt is required")
            
            # Prepare the request
            url = f"{base_url}/services/aigc/text-generation/generation"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": model,
                "input": {
                    "prompt": prompt
                },
                "parameters": {
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                    "top_k": top_k
                }
            }
            
            # Make the request
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            
            response_data = response.json()
            
            # Extract the generated text based on Qwen API response structure
            output = response_data.get('output', {})
            generated_text = output.get('text', '')
            
            return {
                "text": generated_text,
                "model": model,
                "prompt": prompt,
                "usage": response_data.get('usage', {}),
                "raw_response": response_data
            }
            
        except requests.RequestException as e:
            error_msg = str(e)
            try:
                if hasattr(e, 'response') and e.response:
                    error_data = e.response.json()
                    error_msg = f"Qwen API Error: {error_data.get('error', {}).get('message', 'Unknown error')}"
            except:
                pass
            logger.error(f"Qwen API request failed: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"Error generating text with Qwen: {str(e)}")
            raise

    def _generate_chat(self, item_index: int) -> Dict[str, Any]:
        """Generate chat response using Qwen API"""
        try:
            credentials = self._get_credentials()
            
            # Extract credential data
            if isinstance(credentials, dict) and 'data' in credentials:
                cred_data = credentials['data']
            else:
                cred_data = credentials
            
            api_key = cred_data.get('apiKey', '')
            base_url = cred_data.get('baseUrl', 'https://dashscope.aliyuncs.com/api/v1')
            
            if not api_key:
                raise ValueError("API key not found in credentials")
            
            # Get parameters
            model = self.get_node_parameter("model", item_index, "qwen-turbo")
            prompt = self.get_node_parameter("prompt", item_index, "")
            temperature = self.get_node_parameter("temperature", item_index, 0.7)
            max_tokens = self.get_node_parameter("maxTokens", item_index, 1024)
            top_p = self.get_node_parameter("topP", item_index, 0.9)
            top_k = self.get_node_parameter("topK", item_index, 40)
            
            if not prompt:
                raise ValueError("Prompt is required")
            
            # Prepare the request for chat
            url = f"{base_url}/services/aigc/text-generation/generation"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            # Format as a chat message
            payload = {
                "model": model,
                "input": {
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                },
                "parameters": {
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                    "top_k": top_k
                }
            }
            
            # Make the request
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            
            response_data = response.json()
            
            # Extract the generated text from chat response
            output = response_data.get('output', {})
            choices = output.get('choices', [{}])
            if choices:
                message = choices[0].get('message', {})
                generated_text = message.get('content', '')
            else:
                generated_text = ""
            
            return {
                "text": generated_text,
                "model": model,
                "prompt": prompt,
                "usage": response_data.get('usage', {}),
                "raw_response": response_data
            }
            
        except requests.RequestException as e:
            error_msg = str(e)
            try:
                if hasattr(e, 'response') and e.response:
                    error_data = e.response.json()
                    error_msg = f"Qwen API Error: {error_data.get('error', {}).get('message', 'Unknown error')}"
            except:
                pass
            logger.error(f"Qwen API request failed: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"Error generating chat with Qwen: {str(e)}")
            raise

    def _generate_embeddings(self, item_index: int) -> Dict[str, Any]:
        """Generate embeddings using Qwen API"""
        try:
            credentials = self._get_credentials()
            
            # Extract credential data
            if isinstance(credentials, dict) and 'data' in credentials:
                cred_data = credentials['data']
            else:
                cred_data = credentials
            
            api_key = cred_data.get('apiKey', '')
            base_url = cred_data.get('baseUrl', 'https://dashscope.aliyuncs.com/api/v1')
            
            if not api_key:
                raise ValueError("API key not found in credentials")
            
            # Get parameters
            model = "text-embedding-v1"  # Use the embeddings-specific model
            text = self.get_node_parameter("text", item_index, "")
            return_json = self.get_node_parameter("returnJson", item_index, True)
            
            if not text:
                raise ValueError("Text is required for embedding generation")
            
            # Prepare the request
            url = f"{base_url}/services/embeddings/text-embedding/text-embedding"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": model,
                "input": {
                    "texts": [text]
                }
            }
            
            # Make the request
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            
            response_data = response.json()
            
            # Extract the embeddings
            embeddings = []
            if "output" in response_data and "embeddings" in response_data["output"]:
                embeddings = response_data["output"]["embeddings"]
            
            result = {
                "model": model,
                "text": text,
                "usage": response_data.get("usage", {}),
            }
            
            # Add embeddings based on return format preference
            if return_json:
                result["embeddings"] = embeddings
            else:
                result["embeddings"] = json.dumps(embeddings)
                
            result["raw_response"] = response_data
            
            return result
            
        except requests.RequestException as e:
            error_msg = str(e)
            try:
                if hasattr(e, 'response') and e.response:
                    error_data = e.response.json()
                    error_msg = f"Qwen API Error: {error_data.get('error', {}).get('message', 'Unknown error')}"
            except:
                pass
            logger.error(f"Qwen API request failed: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"Error generating embeddings with Qwen: {str(e)}")
            raise

    def _generate_image(self, item_index: int) -> Dict[str, Any]:
        """Generate image using Qwen VL API"""
        try:
            credentials = self._get_credentials()
            
            # Extract credential data
            if isinstance(credentials, dict) and 'data' in credentials:
                cred_data = credentials['data']
            else:
                cred_data = credentials
            
            api_key = cred_data.get('apiKey', '')
            base_url = cred_data.get('baseUrl', 'https://dashscope.aliyuncs.com/api/v1')
            
            if not api_key:
                raise ValueError("API key not found in credentials")
            
            # Get parameters
            prompt = self.get_node_parameter("imagePrompt", item_index, "")
            size = self.get_node_parameter("imageSize", item_index, "1024*1024")
            
            if not prompt:
                raise ValueError("Image prompt is required")
            
            # Prepare the request
            url = f"{base_url}/services/aigc/text2image/image-synthesis"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": "wanx-v1",
                "input": {
                    "prompt": prompt
                },
                "parameters": {
                    "size": size,
                    "n": 1  # Number of images to generate
                }
            }
            
            # Make the request
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            
            response_data = response.json()
            
            # Extract image data from response
            output = response_data.get('output', {})
            images = output.get('results', [])
            
            result = {
                "prompt": prompt,
                "size": size,
                "images": []
            }
            
            # Process the returned images
            binary_data = {}
            for i, img_data in enumerate(images):
                if "url" in img_data:
                    # For URLs, add them to the result
                    result["images"].append({
                        "url": img_data["url"]
                    })
                elif "b64_image" in img_data:
                    # For base64 images, decode and create binary data
                    img_base64 = img_data["b64_image"]
                    img_name = f"qwen_image_{i+1}.png"
                    
                    # Add to binary data
                    binary_data[img_name] = {
                        "data": img_base64,
                        "mimeType": "image/png"
                    }
                    
                    # Add reference to result
                    result["images"].append({
                        "fileName": img_name
                    })
            
            result["raw_response"] = response_data
            
            # Return with binary data if available
            return_data = NodeExecutionData(
                json_data=result,
                binary_data=binary_data if binary_data else None
            )
            
            return result
            
        except requests.RequestException as e:
            error_msg = str(e)
            try:
                if hasattr(e, 'response') and e.response:
                    error_data = e.response.json()
                    error_msg = f"Qwen API Error: {error_data.get('error', {}).get('message', 'Unknown error')}"
            except:
                pass
            logger.error(f"Qwen API request failed: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"Error generating image with Qwen: {str(e)}")
            raise

    def _generate_function_call(self, item_index: int) -> Dict[str, Any]:
        """Generate chat with function calling using Qwen API"""
        try:
            credentials = self._get_credentials()
            
            # Extract credential data
            if isinstance(credentials, dict) and 'data' in credentials:
                cred_data = credentials['data']
            else:
                cred_data = credentials
            
            api_key = cred_data.get('apiKey', '')
            base_url = cred_data.get('baseUrl', 'https://dashscope.aliyuncs.com/api/v1')
            
            if not api_key:
                raise ValueError("API key not found in credentials")
            
            # Get parameters
            model = self.get_node_parameter("model", item_index, "qwen-plus")  # Using Plus as default for function calling
            prompt = self.get_node_parameter("prompt", item_index, "")
            temperature = self.get_node_parameter("temperature", item_index, 0.7)
            max_tokens = self.get_node_parameter("maxTokens", item_index, 1024)
            top_p = self.get_node_parameter("topP", item_index, 0.9)
            top_k = self.get_node_parameter("topK", item_index, 40)
            functions_json = self.get_node_parameter("functions", item_index, "[]")
            
            if not prompt:
                raise ValueError("Prompt is required")
            
            # Parse functions JSON
            try:
                functions = json.loads(functions_json)
                if not isinstance(functions, list):
                    raise ValueError("Functions must be a JSON array")
            except json.JSONDecodeError:
                raise ValueError("Functions must be valid JSON")
            
            # Prepare the request for chat with function calling
            url = f"{base_url}/services/aigc/text-generation/generation"
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            # Format as a chat message with tools
            payload = {
                "model": model,
                "input": {
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                },
                "parameters": {
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                    "top_k": top_k,
                    "tools": functions,
                    "tool_choice": "auto"  # Let the model decide whether to call a function
                }
            }
            
            # Make the request
            response = requests.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            
            response_data = response.json()
            
            # Extract the result based on whether a function was called
            output = response_data.get('output', {})
            choices = output.get('choices', [{}])
            
            result = {
                "model": model,
                "prompt": prompt,
                "usage": response_data.get('usage', {}),
                "raw_response": response_data
            }
            
            if choices:
                message = choices[0].get('message', {})
                content = message.get('content', '')
                
                result["text"] = content
                
                # Check if there's a function call
                tool_calls = message.get('tool_calls', [])
                if tool_calls:
                    result["function_calls"] = tool_calls
                    
                    # Format function calls in a more accessible way
                    formatted_calls = []
                    for call in tool_calls:
                        function_name = call.get('function', {}).get('name', '')
                        arguments = call.get('function', {}).get('arguments', '{}')
                        
                        try:
                            args_dict = json.loads(arguments)
                        except:
                            args_dict = {"raw_arguments": arguments}
                            
                        formatted_calls.append({
                            "name": function_name,
                            "arguments": args_dict,
                            "id": call.get('id', '')
                        })
                    
                    result["formatted_function_calls"] = formatted_calls
            
            return result
            
        except requests.RequestException as e:
            error_msg = str(e)
            try:
                if hasattr(e, 'response') and e.response:
                    error_data = e.response.json()
                    error_msg = f"Qwen API Error: {error_data.get('error', {}).get('message', 'Unknown error')}"
            except:
                pass
            logger.error(f"Qwen API request failed: {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"Error with Qwen function calling: {str(e)}")
            raise