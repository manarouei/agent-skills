from typing import Dict, List, Any, Optional
from models import NodeExecutionData
from nodes.base import BaseNode, NodeParameterType
from utils.model_registry import ModelRegistry, ModelAdapterProtocol
from utils.langchain_chat_models import ChatModelRunnable
import requests, json, logging

logger = logging.getLogger(__name__)

class _SakuyMeliChatAdapter(ModelAdapterProtocol):
    """Adapter for Iranian National Platform (سکوی ملی) LLM API - OpenAI-compatible format"""
    
    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        options: Optional[Dict[str, Any]] = None,
    ):
        self.base_url = "https://alphapi.aip.sharif.ir/v1"
        self.api_key = api_key
        self.model = model
        self.temperature = float(temperature)
        self.options = options or {}
        self.timeout = int(self.options.get("timeout", 120))

    def invoke(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        """Invoke Sakuy Meli API (OpenAI-compatible format)"""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        # Optional parameters (OpenAI-compatible)
        if "max_tokens" in self.options:
            payload["max_tokens"] = int(self.options["max_tokens"])
        if "top_p" in self.options:
            payload["top_p"] = float(self.options["top_p"])
        if "presence_penalty" in self.options:
            payload["presence_penalty"] = float(self.options["presence_penalty"])
        if "frequency_penalty" in self.options:
            payload["frequency_penalty"] = float(self.options["frequency_penalty"])
        if "stop" in self.options:
            payload["stop"] = self.options["stop"]

        # Tool calling support (if platform supports it)
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        # Make request
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            if r.status_code >= 400:
                logger.error(f"[Sakuy Meli Adapter] ✗ Error response: {r.status_code} - {r.text[:500]}")
                return {"error": f"{r.status_code}: {r.text}"}

            data = r.json()
        except requests.exceptions.Timeout:
            logger.error(f"[Sakuy Meli Adapter] ✗ Request timeout after {self.timeout}s")
            return {"error": f"Request timeout after {self.timeout}s"}
        except Exception as e:
            logger.error(f"[Sakuy Meli Adapter] ✗ Request failed: {e}")
            return {"error": str(e)}

        # Parse OpenAI-compatible response
        choices = data.get("choices") or []
        if not choices:
            return {"error": "No choices in response"}

        msg = choices[0].get("message") or {}
        tool_calls = []
        
        # Parse tool calls (if supported)
        for t in msg.get("tool_calls") or []:
            fn = t.get("function") or {}
            args_raw = fn.get("arguments") or "{}"
            try:
                args = json.loads(args_raw)
            except Exception:
                args = {"_raw": args_raw}
            tool_calls.append({
                "id": t.get("id") or "",
                "name": fn.get("name") or "",
                "arguments": args
            })
        
        # Extract token usage (if available)
        usage = data.get("usage") or {}
        token_usage = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
        
        return {
            "assistant_message": {"role": "assistant", "content": msg.get("content") or ""},
            "tool_calls": tool_calls,
            "usage": token_usage
        }


class SakuyMeliChatModelNode(BaseNode):
    """سکوی ملی (Iranian National Platform) Chat Model node"""
    
    type = "sakuy_meli_chat_model"
    version = 1
    
    description = {
        "displayName": "سکوی ملی Chat Model",
        "name": "sakuy_meli_chat_model",
        "icon": "file:iran.svg",
        "group": ["ai"],
        "description": "Iranian National Platform LLM models (DeepSeek, Qwen, GPT-OSS, etc.)",
        "defaults": {"name": "سکوی ملی Chat Model"},
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [{"name": "ai_model", "type": "ai_languageModel", "required": True}]
    }
    
    properties = {
        "parameters": [
            {
                "name": "model",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Model",
                "options": [
                    {"name": "DeepSeek V3.1", "value": "DeepSeek-V3.1"},
                    {"name": "Qwen 3-32B", "value": "Qwen3-32B"},
                    {"name": "Qwen 2.5-72B", "value": "Qwen2.5-72B"},
                    {"name": "GPT-OSS-120B", "value": "GPT-OSS-120B"},
                    {"name": "Llama4 Scout 17B-16E", "value": "Llama4-Scout-17B-16E"},
                    {"name": "Gemma 3-27B-IT", "value": "Gemma-3-27B-IT"}
                ],
                "default": "GPT-OSS-120B",
                "description": "Select Iranian National Platform LLM model"
            },
            {
                "name": "temperature",
                "type": NodeParameterType.NUMBER,
                "display_name": "Temperature",
                "default": 0.7,
                "typeOptions": {"minValue": 0, "maxValue": 2, "numberStepSize": 0.1},
                "description": "Controls randomness in responses"
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "options": [
                    {"name": "max_tokens", "type": NodeParameterType.NUMBER, "display_name": "Maximum Number of Tokens", "default": 5000},
                    {"name": "top_p", "type": NodeParameterType.NUMBER, "display_name": "Top P", "default": 1.0},
                    {"name": "presence_penalty", "type": NodeParameterType.NUMBER, "display_name": "Presence Penalty", "default": 0.0},
                    {"name": "frequency_penalty", "type": NodeParameterType.NUMBER, "display_name": "Frequency Penalty", "default": 0.0},
                    {"name": "stop", "type": NodeParameterType.JSON, "display_name": "Stop Sequences", "default": []},
                    {"name": "timeout", "type": NodeParameterType.NUMBER, "display_name": "Timeout (s)", "default": 120},
                ]
            }
        ],
        "credentials": [{"name": "sakuyMeliApi", "required": True}]
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._runnable: Optional[ChatModelRunnable] = None

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute the chat model node - returns model config"""
        try:
            input_data = self.get_input_data()
            if not input_data:
                logger.warning("[Sakuy Meli Chat Model] No inbound items. Connect a start node first.")
                return [[]]
            
            results: List[NodeExecutionData] = []
            
            for item_index, item in enumerate(input_data):
                model = self.get_node_parameter("model", item_index, "gpt-oss-120b")
                temperature = self.get_node_parameter("temperature", item_index, 0.7)
                opts = self.get_node_parameter("options", item_index, {}) or {}

                # Normalize options
                options = {}
                for k in ("max_tokens", "top_p", "presence_penalty", "frequency_penalty", "stop", "timeout"):
                    if k in opts and opts[k] not in (None, "", []):
                        options[k] = opts[k]

                # Get credentials
                credentials = self.get_credentials("sakuyMeliApi")
                if not credentials:
                    results.append(NodeExecutionData(
                        json_data={"error": "No سکوی ملی credentials found"}, 
                        binary_data=None
                    ))
                    continue

                api_key = credentials.get("apiKey", "")
                if not api_key:
                    results.append(NodeExecutionData(
                        json_data={"error": "API key is required"}, 
                        binary_data=None
                    ))
                    continue

                # Create adapter
                adapter = _SakuyMeliChatAdapter(
                    api_key=api_key,
                    model=model,
                    temperature=temperature,
                    options=options,
                )
                
                # Register in ModelRegistry
                registry_id = ModelRegistry.register(adapter)
                verify_adapter = ModelRegistry.get(registry_id)
                logger.info(
                    f"[Sakuy Meli Chat Model] Registered adapter id={registry_id} "
                    f"model={model}, verify={verify_adapter is not None}"
                )

                # Create model config (same format as OpenAI for compatibility)
                model_config = {
                    "provider": "sakuy_meli",
                    "model": model,
                    "temperature": temperature,
                    "registry_id": registry_id,
                }
                
                results.append(NodeExecutionData(
                    json_data={**item.json_data, "ai_model": model_config},
                    binary_data=item.binary_data
                ))
            
            logger.info(f"[Sakuy Meli Chat Model] ✓ Emitted {len(results)} item(s)")
            return [results]
            
        except Exception as e:
            import traceback
            error_msg = traceback.format_exc()
            logger.error(f"[Sakuy Meli Chat Model] ✗ EXCEPTION CAUGHT: {e}")
            logger.error(f"[Sakuy Meli Chat Model] ✗ Full traceback:\n{error_msg}")
            return [[NodeExecutionData(json_data={"error": str(e)}, binary_data=None)]]
    
    def get_runnable(self, item_index: int = 0) -> ChatModelRunnable:
        """Get LangChain-compatible ChatModelRunnable for LCEL composition"""
        
        if self._runnable is not None:
            return self._runnable
        
        try:
            # Get parameters
            model = self.get_node_parameter("model", item_index, "gpt-oss-120b")
            temperature = self.get_node_parameter("temperature", item_index, 0.7)
            opts = self.get_node_parameter("options", item_index, {}) or {}
            
            # Normalize options
            options = {}
            for k in ("max_tokens", "top_p", "presence_penalty", "frequency_penalty", "stop", "timeout"):
                if k in opts and opts[k] not in (None, "", []):
                    options[k] = opts[k]
            
            # Get credentials
            credentials = self.get_credentials("sakuyMeliApi")
            if not credentials:
                logger.error("[Sakuy Meli Chat Model] No credentials for Runnable")
                raise ValueError("No سکوی ملی credentials found")
            
            api_key = credentials.get("apiKey", "")
            if not api_key:
                raise ValueError("API key is required")
            
            # Create adapter
            adapter = _SakuyMeliChatAdapter(
                api_key=api_key,
                model=model,
                temperature=temperature,
                options=options,
            )
            
            # Wrap as Runnable
            self._runnable = ChatModelRunnable(
                adapter=adapter,
                provider="sakuy_meli",
                model=model,
                temperature=temperature,
                name=f"SakuyMeli-{model}",
                **options
            )
            
            logger.debug(f"[Sakuy Meli Chat Model] Created Runnable: {model}")
            return self._runnable
            
        except Exception as e:
            logger.error(f"[Sakuy Meli Chat Model] Error creating Runnable: {e}")
            raise ValueError(f"Failed to create ChatModelRunnable: {e}") from e
