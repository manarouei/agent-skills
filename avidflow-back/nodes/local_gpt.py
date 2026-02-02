"""
Local GPT Node for integration with self-hosted GPT-compatible model servers.

This node provides chat completion functionality compatible with OpenAI's API format,
allowing you to use local or self-hosted models with the same interface.
"""
from typing import Dict, List, Any
from models import NodeExecutionData
import requests
import json
import base64
import traceback
import logging
from utils.serialization import deep_serialize
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class LocalGptNode(BaseNode):
    """
    Local GPT node for integration with self-hosted GPT-compatible model servers.
    
    This node supports:
    - OpenAI-compatible chat completions API
    - Configurable authentication (Basic Auth or Bearer Token)
    - Streaming responses (if supported by server)
    - Custom endpoint paths for different server implementations
    """
    
    type = "localGpt"
    version = 1
    
    description = {
        "displayName": "Local GPT",
        "name": "localGpt",
        "group": ["transform"],
        "subtitle": "={{$parameter['operation'] + ': ' + $parameter['resource']}}",
        "description": "Connect to self-hosted GPT-compatible model servers",
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
                    }
                ],
                "default": "chat",
                "description": "Type of operation to perform"
            },
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "required": True,
                "display_options": {
                    "show": {
                        "resource": ["chat"]
                    }
                },
                "options": [
                    {
                        "name": "Complete",
                        "value": "complete"
                    }
                ],
                "default": "complete",
                "description": "Chat operation to perform"
            },
            {
                "name": "endpointPath",
                "type": NodeParameterType.STRING,
                "display_name": "Endpoint Path",
                "default": "/api/chat/completions",
                "required": False,
                "description": "API endpoint path. Try: /api/chat/completions (OpenWebUI) or /v1/chat/completions (OpenAI)",
                "placeholder": "/api/chat/completions"
            },
            {
                "name": "baseUrl",
                "type": NodeParameterType.STRING,
                "display_name": "Base URL",
                "default": "http://178.131.134.191:11300",
                "required": False,
                "description": "Base URL of the local GPT server (without trailing slash)",
                "placeholder": "http://178.131.134.191:11300"
            },
            {
                "name": "authType",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Authentication Type",
                "default": "bearer",
                "required": False,
                "options": [
                    {
                        "name": "Bearer Token (OpenWebUI)",
                        "value": "bearer"
                    },
                    {
                        "name": "HTTP Basic Auth",
                        "value": "basic"
                    }
                ],
                "description": "Authentication method (OpenWebUI requires Bearer token)"
            },
            {
                "name": "loginEndpoint",
                "type": NodeParameterType.STRING,
                "display_name": "Login Endpoint",
                "default": "/api/v1/auths/signin",
                "required": False,
                "description": "Login endpoint path for Bearer token authentication (OpenWebUI default: /api/v1/auths/signin)",
                "placeholder": "/api/v1/auths/signin",
                "display_options": {
                    "show": {
                        "authType": ["bearer"]
                    }
                }
            },
            {
                "name": "timeout",
                "type": NodeParameterType.NUMBER,
                "display_name": "Timeout (seconds)",
                "default": 60,
                "required": False,
                "description": "Request timeout in seconds",
                "typeOptions": {
                    "minValue": 1,
                    "maxValue": 300
                }
            },
            {
                "name": "model",
                "type": NodeParameterType.STRING,
                "display_name": "Model",
                "default": "gpt-oss:120b",
                "required": False,
                "description": "Model name to use. Check your server's available models.",
                "placeholder": "gpt-oss:120b"
            },
            {
                "name": "systemMessage",
                "type": NodeParameterType.STRING,
                "display_name": "System Message",
                "default": "",
                "required": False,
                "description": "System message to set the behavior of the assistant",
                "placeholder": "You are a helpful assistant."
            },
            {
                "name": "messages",
                "type": NodeParameterType.JSON,
                "display_name": "Messages",
                "default": [],
                "required": False,
                "description": "Array of message objects with role and content. Example: [{\"role\": \"user\", \"content\": \"Hello\"}]",
                "placeholder": "[{\"role\": \"user\", \"content\": \"Hello\"}]"
            },
            {
                "name": "message",
                "type": NodeParameterType.STRING,
                "display_name": "Message",
                "default": "",
                "required": False,
                "description": "User message to send (will be added to messages array)",
                "placeholder": "What is AI?"
            },
            {
                "name": "temperature",
                "type": NodeParameterType.NUMBER,
                "display_name": "Temperature",
                "default": 0.7,
                "required": False,
                "description": "Controls randomness. Lower is more focused, higher is more creative (0-2)",
                "typeOptions": {
                    "minValue": 0,
                    "maxValue": 2,
                    "numberPrecision": 1
                }
            },
            {
                "name": "maxTokens",
                "type": NodeParameterType.NUMBER,
                "display_name": "Max Tokens",
                "default": 1000,
                "required": False,
                "description": "Maximum number of tokens to generate",
                "typeOptions": {
                    "minValue": 1,
                    "maxValue": 100000
                }
            },
            {
                "name": "topP",
                "type": NodeParameterType.NUMBER,
                "display_name": "Top P",
                "default": 1,
                "required": False,
                "description": "Nucleus sampling parameter (0-1)",
                "typeOptions": {
                    "minValue": 0,
                    "maxValue": 1,
                    "numberPrecision": 2
                }
            },
            {
                "name": "frequencyPenalty",
                "type": NodeParameterType.NUMBER,
                "display_name": "Frequency Penalty",
                "default": 0,
                "required": False,
                "description": "Penalize new tokens based on frequency (-2 to 2)",
                "typeOptions": {
                    "minValue": -2,
                    "maxValue": 2,
                    "numberPrecision": 1
                }
            },
            {
                "name": "presencePenalty",
                "type": NodeParameterType.NUMBER,
                "display_name": "Presence Penalty",
                "default": 0,
                "required": False,
                "description": "Penalize new tokens based on presence (-2 to 2)",
                "typeOptions": {
                    "minValue": -2,
                    "maxValue": 2,
                    "numberPrecision": 1
                }
            },
            {
                "name": "stream",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Stream",
                "default": False,
                "required": False,
                "description": "Stream the response as it's generated (if supported by server)"
            },
            {
                "name": "simplifyOutput",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Simplify Output",
                "default": True,
                "required": False,
                "description": "Return only the message content instead of full API response"
            },
            {
                "name": "additionalParams",
                "type": NodeParameterType.JSON,
                "display_name": "Additional Parameters",
                "default": {},
                "required": False,
                "description": "Additional parameters to send to the API (as JSON object)",
                "placeholder": "{\"stop\": [\"\\n\"], \"n\": 1}"
            }
        ],
        "credentials": [
            {
                "name": "localGptApi",
                "required": True,
                "displayOptions": {
                    "show": {}
                }
            }
        ]
    }
    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute Local GPT node operations"""
        
        try:
            # Get resource and operation
            resource = self.get_node_parameter("resource", 0, "chat")
            operation = self.get_node_parameter("operation", 0, "complete")
            
            input_data = self.get_input_data()
            
            # Process based on resource/operation
            if resource == "chat" and operation == "complete":
                result = self._process_chat_completion(input_data)
            else:
                result = {"error": f"Unsupported operation: {resource}.{operation}"}
            
            # Check for errors
            if isinstance(result, dict) and "error" in result:
                return [[NodeExecutionData(json_data=result)]]
            
            # Serialize and return
            serialized_result = deep_serialize(result)
            return [[NodeExecutionData(json_data=serialized_result)]]
            
        except Exception as e:
            traceback.print_exc()
            return [[NodeExecutionData(json_data={
                "error": f"Error executing Local GPT node: {str(e)}"
            })]]
    
    def _process_chat_completion(self, input_data: List[NodeExecutionData]) -> Dict[str, Any]:
        """
        Process chat completion request
        
        This method:
        1. Gets credentials and validates them
        2. Prepares authentication headers
        3. Builds the request payload
        4. Makes the HTTP request to the local server
        5. Processes and returns the response
        
        Args:
            input_data: Input data from previous node
            
        Returns:
            Dictionary with chat completion response or error
        """
        try:            
            # Get credentials
            credentials = self.get_credentials("localGptApi")
            if not credentials:
                logger.error("LOCAL GPT: No credentials found")
                return {"error": "No credentials found. Please configure Local GPT API credentials."}
            
            # Extract credential data
            username = credentials.get("username")
            password = credentials.get("password")
                       
            if not username or not password:
                logger.error("LOCAL GPT: Missing username or password")
                return {"error": "Username and password are required in credentials"}
            
            # Get configuration from node parameters
            base_url = self.get_node_parameter("baseUrl", 0, "http://178.131.134.191:11300").rstrip('/')
            auth_type = self.get_node_parameter("authType", 0, "bearer")
            timeout_seconds = float(self.get_node_parameter("timeout", 0, 60))
            
            # Get endpoint path
            endpoint_path = self.get_node_parameter("endpointPath", 0, "/api/chat/completions")
            if not endpoint_path.startswith("/"):
                endpoint_path = "/" + endpoint_path
            
            full_url = f"{base_url}{endpoint_path}"

            # Get parameters
            model = self.get_node_parameter("model", 0, "gpt-oss:120b")
            temperature = self.get_node_parameter("temperature", 0, 0.7)
            max_tokens = self.get_node_parameter("maxTokens", 0, 1000)
            top_p = self.get_node_parameter("topP", 0, 1)
            frequency_penalty = self.get_node_parameter("frequencyPenalty", 0, 0)
            presence_penalty = self.get_node_parameter("presencePenalty", 0, 0)
            stream = self.get_node_parameter("stream", 0, False)
            simplify_output = self.get_node_parameter("simplifyOutput", 0, True)
            additional_params = self.get_node_parameter("additionalParams", 0, {})

            # Build messages array
            messages = []
            
            # Add system message if provided
            system_message = self.get_node_parameter("systemMessage", 0, "")
            if system_message:
                messages.append({
                    "role": "system",
                    "content": system_message
                })
            
            # Add messages from collection parameter
            collection_messages = self.get_node_parameter("messages", 0, [])
            if isinstance(collection_messages, list):
                for msg in collection_messages:
                    if isinstance(msg, dict) and "role" in msg and "content" in msg:
                        messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })
            
            # Add user message if provided
            user_message = self.get_node_parameter("message", 0, "")
            if user_message:
                messages.append({
                    "role": "user",
                    "content": user_message
                })

            # Ensure at least one message
            if not messages:
                messages.append({
                    "role": "user",
                    "content": "Hello"
                })
            
            # Prepare request payload
            payload = {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "frequency_penalty": frequency_penalty,
                "presence_penalty": presence_penalty
            }
            
            # Add stream parameter if requested
            if stream:
                payload["stream"] = True
            
            # Merge additional parameters
            if isinstance(additional_params, dict):
                payload.update(additional_params)
        
            
            # Prepare authentication headers
            headers = {
                "Content-Type": "application/json"
            }
            
            # Handle authentication based on type
            if auth_type == "basic":
                # HTTP Basic Auth
                auth_string = f"{username}:{password}"
                auth_bytes = auth_string.encode('utf-8')
                auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
                headers["Authorization"] = f"Basic {auth_b64}"
                
            elif auth_type == "bearer":
                # Bearer Token: First login to get token
                login_endpoint = self.get_node_parameter("loginEndpoint", 0, "/api/v1/auths/signin")
                login_url = f"{base_url}{login_endpoint}"
                
                
                # OpenWebUI uses 'email' not 'username'
                login_payload = {
                    "email": username,
                    "password": password
                }
                
                try:
                    login_response = requests.post(
                        login_url,
                        json=login_payload,
                        timeout=timeout_seconds
                    )
                    login_response.raise_for_status()
                    
                    login_data = login_response.json()
                    # OpenWebUI returns 'token' field
                    token = login_data.get("token") or login_data.get("access_token") or login_data.get("accessToken")
                    
                    if not token:
                        logger.error(f"LOCAL GPT: No token in login response: {login_data}")
                        return {"error": "Login successful but no token found in response"}
                    
                    headers["Authorization"] = f"Bearer {token}"
                    
                except requests.exceptions.RequestException as e:
                    logger.error(f"LOCAL GPT: Authentication failed: {str(e)}")
                    return {"error": f"Authentication failed: {str(e)}"}
            else:
                logger.error(f"LOCAL GPT: Unsupported auth type: {auth_type}")
                return {"error": f"Unsupported authentication type: {auth_type}"}
                     
            # Make the API request
            try:
                
                if stream:
                    # Handle streaming response
                    response = requests.post(
                        full_url,
                        headers=headers,
                        json=payload,
                        stream=True,
                        timeout=timeout_seconds
                    )
                    response.raise_for_status()
                    
                    
                    # Collect streamed chunks
                    full_content = ""
                    for line in response.iter_lines():
                        if line:
                            line_text = line.decode('utf-8')
                            if line_text.startswith('data: '):
                                chunk_data = line_text[6:]
                                if chunk_data.strip() == '[DONE]':
                                    break
                                try:
                                    chunk_json = json.loads(chunk_data)
                                    if 'choices' in chunk_json and len(chunk_json['choices']) > 0:
                                        delta = chunk_json['choices'][0].get('delta', {})
                                        content = delta.get('content', '')
                                        if content:
                                            full_content += content
                                except json.JSONDecodeError:
                                    continue
                    
                    
                    if simplify_output:
                        return {"message": full_content}
                    else:
                        return {
                            "choices": [{
                                "message": {
                                    "role": "assistant",
                                    "content": full_content
                                },
                                "finish_reason": "stop"
                            }]
                        }
                else:
                    # Regular (non-streaming) request
                    
                    response = requests.post(
                        full_url,
                        headers=headers,
                        json=payload,
                        timeout=timeout_seconds
                    )
                    
                    response.raise_for_status()
                    
                    response_data = response.json()
                    
                    # Simplify output if requested
                    if simplify_output:
                        # Extract just the message content
                        if 'choices' in response_data and len(response_data['choices']) > 0:
                            message_content = response_data['choices'][0].get('message', {}).get('content', '')
                            #logger.info(f"LOCAL GPT: Extracted message content (length: {len(message_content)})")
                            return {"message": message_content}
                        else:
                            logger.warning(f"LOCAL GPT: Unexpected response format: {response_data}")
                            return {"error": "Unexpected response format", "raw": response_data}
                    else:
                        logger.info("LOCAL GPT: Returning full response")
                        return response_data
                        
            except requests.exceptions.Timeout:
                logger.error(f"LOCAL GPT: Request timeout after {timeout_seconds} seconds")
                return {"error": f"Request timeout after {timeout_seconds} seconds"}
            except requests.exceptions.ConnectionError as e:
                logger.error(f"LOCAL GPT: Connection error to {full_url}: {str(e)}")
                return {"error": f"Connection error: Unable to connect to {full_url}"}
            except requests.exceptions.HTTPError as e:
                error_message = f"HTTP {e.response.status_code}"
                logger.error(f"LOCAL GPT: HTTP error: {error_message}")
                logger.error(f"LOCAL GPT: Response text: {e.response.text}")
                try:
                    error_data = e.response.json()
                    error_message += f": {json.dumps(error_data)}"
                    logger.error(f"LOCAL GPT: Error data: {json.dumps(error_data, indent=2)}")
                except:
                    error_message += f": {e.response.text[:200]}"
                return {"error": error_message}
            except json.JSONDecodeError as e:
                logger.error(f"LOCAL GPT: Invalid JSON response: {str(e)}")
                logger.error(f"LOCAL GPT: Response text: {response.text}")
                return {"error": "Invalid JSON response from server"}
                
        except Exception as e:
            logger.error(f"LOCAL GPT: Unexpected error in chat completion: {str(e)}")
            traceback.print_exc()
            return {"error": f"Error in chat completion: {str(e)}"}
