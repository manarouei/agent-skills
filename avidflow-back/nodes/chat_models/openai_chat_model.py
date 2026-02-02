from typing import Dict, List, Any, Optional
from models import NodeExecutionData
from nodes.base import BaseNode, NodeParameterType
from utils.model_registry import ModelRegistry, ModelAdapterProtocol
from utils.langchain_chat_models import ChatModelRunnable
from utils.langchain_base import RunnableRegistry
import requests, json, logging

logger = logging.getLogger(__name__)

class _OpenAIChatAdapter(ModelAdapterProtocol):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        options: Optional[Dict[str, Any]] = None,
    ):
        self.base_url = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"
        self.api_key = api_key
        self.model = model
        self.temperature = float(temperature)
        self.options = options or {}
        self.timeout = int(self.options.get("timeout", 120))
        self.org = self.options.get("organization")

    def invoke(self, messages: list[dict], tools: list[dict] | None = None) -> dict:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        if self.org:
            headers["OpenAI-Organization"] = self.org

        payload: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }

        # Optional OpenAI params (parity with LMOpenAi basics)
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
        if "response_format" in self.options:
            rf = self.options["response_format"]
            # text or json_object (simple parity)
            payload["response_format"] = {"type": rf}

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
            # logger.info(f"[OpenAI Adapter DEBUG] Tool calling enabled with {len(tools)} tools")
            # logger.info(f"[OpenAI Adapter DEBUG] Tool names: {[t.get('function', {}).get('name', 'unknown') for t in tools]}")
        else:
            logger.info(f"[OpenAI Adapter DEBUG] No tools provided")

        # Log the full request for debugging
        # logger.info(f"[OpenAI Adapter DEBUG] ===== FULL REQUEST TO OPENAI =====")
        # logger.info(f"[OpenAI Adapter DEBUG] URL: {url}")
        # logger.info(f"[OpenAI Adapter DEBUG] Payload:")
        # logger.info(f"{json.dumps(payload, indent=2)}")
        # logger.info(f"[OpenAI Adapter DEBUG] ====================================")

        # Basic single attempt; (optional) add simple retry if needed
        r = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        if r.status_code >= 400:
            error_data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            error_msg = error_data.get("error", {}).get("message", r.text[:500])
            logger.error(f"[OpenAI Adapter] ✗ API Error ({r.status_code}): {error_msg}")
            return {"error": f"{r.status_code}: {error_msg}"}

        data = r.json()
        
        # Log the FULL raw response from OpenAI
        # logger.info(f"[OpenAI Adapter DEBUG] ===== FULL RAW RESPONSE FROM OPENAI =====")
        # logger.info(f"[OpenAI Adapter DEBUG] {json.dumps(data, indent=2)}")
        # logger.info(f"[OpenAI Adapter DEBUG] ============================================")
        
        # # Log response details
        # logger.info(f"[OpenAI Adapter DEBUG] Response received:")
        # logger.info(f"[OpenAI Adapter DEBUG]   - choices count: {len(data.get('choices', []))}")
        # if data.get('choices'):
        #     first_choice = data['choices'][0]
        #     logger.info(f"[OpenAI Adapter DEBUG]   - finish_reason: {first_choice.get('finish_reason')}")
        #     msg_debug = first_choice.get('message', {})
        #     logger.info(f"[OpenAI Adapter DEBUG]   - message role: {msg_debug.get('role')}")
        #     logger.info(f"[OpenAI Adapter DEBUG]   - has content: {bool(msg_debug.get('content'))}")
        #     logger.info(f"[OpenAI Adapter DEBUG]   - has tool_calls: {bool(msg_debug.get('tool_calls'))}")
        #     if msg_debug.get('tool_calls'):
        #         logger.info(f"[OpenAI Adapter DEBUG]   - tool_calls count: {len(msg_debug['tool_calls'])}")
        #         for tc in msg_debug.get('tool_calls', []):
        #             logger.info(f"[OpenAI Adapter DEBUG]     - tool: {tc.get('function', {}).get('name')}")
        
        choices = data.get("choices") or []
        if not choices:
            return {"error": "No choices in response"}

        msg = choices[0].get("message") or {}
        tool_calls = []
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
        
        # Extract token usage from response
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

class OpenAIChatModelNode(BaseNode):
    """OpenAI Chat Model node"""
    
    type = "ai_languageModel"
    version = 1
    
    description = {
        "displayName": "OpenAI Chat Model",
        "name": "ai_languageModel",
        "icon": "file:openai.svg",
        "group": ["ai"],
        "description": "OpenAI chat model for AI agents",
        "defaults": {"name": "OpenAI Chat Model"},
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
                    {"name": "GPT-4", "value": "gpt-4"},
                    {"name": "GPT-4 Turbo", "value": "gpt-4-turbo"},
                    {"name": "GPT-3.5 Turbo", "value": "gpt-3.5-turbo"},
                    {"name": "GPT-4o", "value": "gpt-4o"},
                    {"name": "GPT-4o Mini", "value": "gpt-4o-mini"}
                ],
                "default": "gpt-4",
                "description": "The model to use"
            },
            {
                "name": "temperature",
                "type": NodeParameterType.NUMBER,
                "display_name": "Temperature",
                "default": 0.7,
                "typeOptions": {"minValue": 0, "maxValue": 2, "numberStepSize": 0.1},
                "description": "Controls randomness in responses"
            },
            # Options parity like in the UI screenshots
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "options": [
                    {"name": "max_tokens", "type": NodeParameterType.NUMBER, "display_name": "Maximum Number of Tokens", "default": 1000},
                    {"name": "top_p", "type": NodeParameterType.NUMBER, "display_name": "Top P", "default": 1.0},
                    {"name": "presence_penalty", "type": NodeParameterType.NUMBER, "display_name": "Presence Penalty", "default": 0.0},
                    {"name": "frequency_penalty", "type": NodeParameterType.NUMBER, "display_name": "Frequency Penalty", "default": 0.0},
                    {"name": "stop", "type": NodeParameterType.JSON, "display_name": "Stop Sequences", "default": []},
                    {"name": "response_format", "type": NodeParameterType.OPTIONS, "display_name": "Response Format", "options": [
                        {"name": "Text", "value": "text"},
                        {"name": "JSON Object", "value": "json_object"},
                    ], "default": "text"},
                    {"name": "timeout", "type": NodeParameterType.NUMBER, "display_name": "Timeout (s)", "default": 120},
                    {"name": "organization", "type": NodeParameterType.STRING, "display_name": "Organization (optional)", "default": ""},
                    {"name": "base_url", "type": NodeParameterType.STRING, "display_name": "Base URL (optional)", "default": ""},
                ]
            }
        ],
        "credentials": [{"name": "openAiApi", "required": True}]
    }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._runnable: Optional[ChatModelRunnable] = None

    
    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute the chat model node - returns model config"""
        try:
            input_data = self.get_input_data()
            if not input_data:
                logger.warning("[OpenAI Chat Model] No inbound items. This node will produce no output. Either connect Start -> OpenAI Chat Model or change this node to emit a default item when unconnected.")
                return [[]]
            
            results: List[NodeExecutionData] = []
            
            for item_index, item in enumerate(input_data):
                model = self.get_node_parameter("model", item_index, "gpt-4")
                temperature = self.get_node_parameter("temperature", item_index, 0.7)
                opts = self.get_node_parameter("options", item_index, {}) or {}

                # Normalize a few fields
                options = {}
                for k in ("max_tokens","top_p","presence_penalty","frequency_penalty","stop","response_format","timeout","organization"):
                    if k in opts and opts[k] not in (None, "", []):
                        options[k] = opts[k]
                base_url_override = ""
                if "base_url" in opts and opts["base_url"]:
                    base_url_override = str(opts["base_url"])

                credentials = self.get_credentials("openAiApi")
                if not credentials:
                    results.append(NodeExecutionData(json_data={"error": "No OpenAI credentials found"}, binary_data=None))
                    continue

                base_url = base_url_override or "https://api.openai.com/v1"
                api_key = credentials.get("apiKey", "")

                adapter = _OpenAIChatAdapter(
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    temperature=temperature,
                    options=options,
                )
                registry_id = ModelRegistry.register(adapter)
                # Verify registration immediately
                verify_adapter = ModelRegistry.get(registry_id)
                logger.info(f"[OpenAI Chat Model] Registered adapter id={registry_id} model={model}, verify={verify_adapter is not None}")

                model_config = {
                    "provider": "openai",
                    "model": model,
                    "temperature": temperature,
                    "registry_id": registry_id,
                }
                
                results.append(NodeExecutionData(
                    json_data={**item.json_data, "ai_model": model_config},
                    binary_data=item.binary_data
                ))
            
            logger.debug(f"[OpenAI Chat Model] Emitted {len(results)} item(s)")
            return [results]
        except Exception as e:
            logger.error(f"OpenAI Chat Model error: {e}")
            return [[NodeExecutionData(json_data={"error": str(e)}, binary_data=None)]]
    
    def get_runnable(self, item_index: int = 0) -> ChatModelRunnable:
        """
        Get LangChain-compatible ChatModelRunnable for LCEL composition.
        
        This enables:
        - Use in LCEL chains
        - Composability with other Runnables
        - Testing without workflow context
        - Future streaming support
        
        Args:
            item_index: Index of item to use for parameter resolution
        
        Returns:
            ChatModelRunnable instance (never None)
        
        Raises:
            ValueError: If configuration is invalid or credentials missing
        
        Example:
            chat_model = openai_node.get_runnable()
            result = chat_model.invoke({
                "messages": [{"role": "user", "content": "Hello!"}]
            })
        """
        
        if self._runnable is not None:
            return self._runnable
        
        try:
            # Get parameters (same as execute())
            model = self.get_node_parameter("model", item_index, "gpt-4")
            temperature = self.get_node_parameter("temperature", item_index, 0.7)
            opts = self.get_node_parameter("options", item_index, {}) or {}
            
            # Normalize options
            options = {}
            for k in ("max_tokens","top_p","presence_penalty","frequency_penalty","stop","response_format","timeout","organization"):
                if k in opts and opts[k] not in (None, "", []):
                    options[k] = opts[k]
            
            base_url_override = opts.get("base_url", "")
            
            # Get credentials
            credentials = self.get_credentials("openAiApi")
            if not credentials:
                logger.error("[OpenAI Chat Model] No credentials for Runnable")
                return None
            
            base_url = base_url_override or "https://api.openai.com/v1"
            api_key = credentials.get("apiKey", "")
            
            # Create adapter
            adapter = _OpenAIChatAdapter(
                base_url=base_url,
                api_key=api_key,
                model=model,
                temperature=temperature,
                options=options,
            )
            
            # Wrap as Runnable
            self._runnable = ChatModelRunnable(
                adapter=adapter,
                provider="openai",
                model=model,
                temperature=temperature,
                name=f"OpenAI-{model}",
                **options
            )
            
            # NOTE: Registry cleanup removed - use managed_runnable() context manager instead
            # For manual registration, call RunnableRegistry.register(runnable) explicitly
            # See utils.runnable_helpers.managed_runnable for automatic lifecycle management
            logger.debug(f"[OpenAI Chat Model] Created Runnable: {model}")
            
            return self._runnable
            
        except Exception as e:
            logger.error(f"[OpenAI Chat Model] Error creating Runnable: {e}")
            raise ValueError(f"Failed to create ChatModelRunnable: {e}") from e
