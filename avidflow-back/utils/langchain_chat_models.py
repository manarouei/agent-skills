"""
LangChain-compatible Chat Model implementations.

Wraps our existing chat model adapters (OpenAI, etc.) with LangChain's
Runnable interface, enabling LCEL composition while maintaining full
backward compatibility with current node implementations.

Langfuse Integration:
- Each LLM call is wrapped in a Langfuse generation observation
- Captures input messages, output, token usage, and latency
- Gracefully degrades when Langfuse is not configured
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Iterator
import logging
import time
import json

from utils.langchain_base import BaseLangChainRunnable, MessageConverter

# Langfuse observability (gracefully degrades if not configured)
from observability.langfuse_client import create_llm_generation, is_langfuse_enabled

logger = logging.getLogger(__name__)


class ChatModelRunnable(BaseLangChainRunnable[Dict[str, Any], Dict[str, Any]]):
    """
    LangChain-compatible wrapper for chat model adapters.
    
    This allows our existing adapters (_OpenAIChatAdapter, etc.) to be used
    as Runnables in LCEL chains while maintaining backward compatibility.
    
    Input format:
        {
            "messages": List[Dict[str, Any]],  # conversation history
            "tools": Optional[List[Dict[str, Any]]],  # available tools
            "temperature": Optional[float],  # override temperature
            "max_tokens": Optional[int],  # override max tokens
            ... other model-specific params
        }
    
    Output format:
        {
            "assistant_message": Dict[str, Any],  # assistant's response
            "tool_calls": List[Dict[str, Any]],  # requested tool calls
            "usage": Optional[Dict[str, Any]]  # token usage stats
        }
    
    Example:
        adapter = _OpenAIChatAdapter(...)
        chat_model = ChatModelRunnable(adapter, name="gpt-4")
        
        result = chat_model.invoke({
            "messages": [
                {"role": "user", "content": "Hello!"}
            ]
        })
    """
    
    def __init__(
        self,
        adapter: Any,  # ModelAdapterProtocol
        provider: str = "openai",
        model: str = "gpt-4",
        temperature: float = 0.7,
        name: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Initialize Chat Model Runnable.
        
        Args:
            adapter: The underlying model adapter (must have invoke method)
            provider: Provider name (openai, anthropic, etc.)
            model: Model identifier
            temperature: Default temperature
            name: Optional display name
            **kwargs: Additional config (max_tokens, top_p, etc.)
        """
        super().__init__(name=name or f"{provider}:{model}", **kwargs)
        self.adapter = adapter
        self.provider = provider
        self.model = model
        self.temperature = temperature
        self.default_params = kwargs
    
    def invoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Invoke the chat model with messages.
        
        Langfuse Integration:
        - Wraps the LLM call in a Langfuse generation observation
        - Captures input messages, output, token usage, and latency
        - Gracefully degrades when Langfuse is not configured
        
        ALWAYS returns normalized schema:
        {
            "assistant_message": {
                "role": "assistant",
                "content": [{"type": "text", "text": str}] | str,
                "tool_calls": [  # optional
                    {"id": str, "type": "function", "function": {"name": str, "arguments": str}}
                ]
            },
            "usage": {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int},
            "_metadata": {"provider": str, "model": str, "latency_ms": int, "finish_reason": str}
        }
        
        Args:
            input: Dict with "messages" (required) and optional overrides
            config: Runtime config (max_retries, timeout, etc.)
        
        Returns:
            Dict with normalized assistant_message, usage, and _metadata
        """
        messages = input.get("messages", [])
        tools = input.get("tools")
        
        # Runtime overrides
        runtime_params = {
            k: v for k, v in input.items()
            if k not in ("messages", "tools") and v is not None
        }
        
        # Retry configuration
        max_retries = (config or {}).get("max_retries", 3)
        backoff_factor = (config or {}).get("backoff_factor", 1.0)
        timeout = (config or {}).get("timeout", 60)
        
        start_time = time.time()
        last_error = None
        
        # Wrap LLM call in Langfuse generation for observability
        # This creates one generation per LLM call with input/output/usage tracking
        with create_llm_generation(
            name="llm-call",
            model=self.model,
            provider=self.provider,
            metadata={
                "temperature": self.temperature,
                "tools_count": len(tools) if tools else 0,
            },
            input_messages=self._truncate_messages_for_trace(messages),
        ) as gen_ctx:
            for attempt in range(max_retries):
                try:
                    # Invoke adapter with current messages and tools
                    result = self.adapter.invoke(messages=messages, tools=tools)
                    elapsed_ms = int((time.time() - start_time) * 1000)
                    
                    # Normalize result to standard schema
                    normalized = self._normalize_response(result, elapsed_ms, runtime_params)
                    
                    # Update Langfuse generation with output and usage
                    if gen_ctx:
                        gen_ctx.update(
                            output=self._extract_output_for_trace(normalized),
                            usage=normalized.get("usage"),
                            metadata={"latency_ms": elapsed_ms, "attempt": attempt + 1},
                        )
                    
                    return normalized
                    
                except Exception as e:
                    last_error = e
                    is_transient = self._is_transient_error(e)
                    
                    logger.warning(
                        f"[ChatModelRunnable] Attempt {attempt + 1}/{max_retries} failed: {e} "
                        f"(transient={is_transient})"
                    )
                    
                    if not is_transient or attempt == max_retries - 1:
                        break
                    
                    # Exponential backoff
                    sleep_time = backoff_factor * (2 ** attempt)
                    time.sleep(sleep_time)
            
            # All retries failed
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[ChatModelRunnable] All retries failed: {last_error}")
            
            # Update Langfuse generation with error
            if gen_ctx:
                gen_ctx.update(
                    level="ERROR",
                    output={"error": str(last_error)},
                    metadata={"latency_ms": elapsed_ms, "attempts": max_retries},
                )
            
            return self._error_response(str(last_error), elapsed_ms, is_transient)
    
    def _truncate_messages_for_trace(self, messages: List[Dict[str, Any]], max_chars: int = 5000) -> List[Dict[str, Any]]:
        """
        Truncate messages for Langfuse trace to avoid huge payloads.
        
        Args:
            messages: Original messages list
            max_chars: Max characters per message content
            
        Returns:
            Truncated messages safe for tracing
        """
        truncated = []
        for msg in messages:
            truncated_msg = dict(msg)
            content = truncated_msg.get("content", "")
            if isinstance(content, str) and len(content) > max_chars:
                truncated_msg["content"] = content[:max_chars] + f"... [truncated {len(content) - max_chars} chars]"
            elif isinstance(content, list):
                # Truncate content blocks
                truncated_msg["content"] = content[:10]  # Keep first 10 blocks
            truncated.append(truncated_msg)
        return truncated
    
    def _extract_output_for_trace(self, normalized: Dict[str, Any]) -> str:
        """
        Extract a string representation of the LLM output for tracing.
        
        Args:
            normalized: Normalized response
            
        Returns:
            String preview of the output
        """
        assistant_msg = normalized.get("assistant_message", {})
        content = assistant_msg.get("content", "")
        
        if isinstance(content, str):
            return content[:2000] if len(content) > 2000 else content
        elif isinstance(content, list):
            # Extract text from content blocks
            texts = []
            for block in content[:5]:  # First 5 blocks
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", "")[:500])
            return " ".join(texts)
        return str(content)[:2000]
    
    def _normalize_response(
        self,
        result: Dict[str, Any],
        elapsed_ms: int,
        runtime_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Normalize adapter response to standard schema.
        
        Args:
            result: Raw adapter response
            elapsed_ms: Request latency
            runtime_params: Runtime parameter overrides
        
        Returns:
            Normalized response with guaranteed structure
        """
        # Extract assistant message
        assistant_msg = result.get("assistant_message", {})
        if not isinstance(assistant_msg, dict):
            assistant_msg = {"role": "assistant", "content": ""}
        
        # Ensure role is set
        if not assistant_msg.get("role"):
            assistant_msg["role"] = "assistant"
        
        # Normalize content to array format (LC compatible)
        content = assistant_msg.get("content", "")
        if isinstance(content, str):
            if content:  # Only wrap non-empty strings
                assistant_msg["content"] = [{"type": "text", "text": content}]
            else:
                assistant_msg["content"] = []
        elif not isinstance(content, list):
            # Fallback for unexpected content types
            assistant_msg["content"] = [{"type": "text", "text": str(content)}]
        
        # Extract tool calls (check both top-level and inside assistant_message)
        tool_calls = result.get("tool_calls", []) or assistant_msg.get("tool_calls", []) or []
        if tool_calls and isinstance(tool_calls, list):
            # Ensure arguments is JSON string
            normalized_calls = []
            for tc in tool_calls:
                normalized_tc = dict(tc)  # Copy
                if "function" in normalized_tc:
                    func = dict(normalized_tc["function"])  # Copy nested dict too
                    if isinstance(func, dict):
                        args = func.get("arguments")
                        # Ensure arguments is a JSON string
                        if args is not None and not isinstance(args, str):
                            func["arguments"] = json.dumps(args, ensure_ascii=False)
                    normalized_tc["function"] = func  # Update with copied dict
                normalized_calls.append(normalized_tc)
            assistant_msg["tool_calls"] = normalized_calls
        else:
            # Ensure tool_calls is always present
            assistant_msg["tool_calls"] = []
        
        # Extract usage
        usage = result.get("usage", {})
        if not isinstance(usage, dict):
            usage = {}
        
        # Ensure all usage fields are present
        usage.setdefault("prompt_tokens", 0)
        usage.setdefault("completion_tokens", 0)
        usage.setdefault("total_tokens", 0)
        
        # Build metadata
        metadata = {
            "provider": self.provider,
            "model": self.model,
            "temperature": runtime_params.get("temperature", self.temperature),
            "latency_ms": elapsed_ms,
            "finish_reason": result.get("finish_reason", "stop")
        }
        
        return {
            "assistant_message": assistant_msg,
            "usage": usage,
            "_metadata": metadata
        }
    
    def _get_metadata(self) -> Dict[str, Any]:
        """
        Override: Provide chat model-specific metadata.
        
        Returns:
            Metadata about model configuration
        """
        return {
            "runnable_type": "ChatModelRunnable",
            "runnable_name": self.name,
            "provider": self.provider,
            "model": self.model,
            "temperature": self.temperature,
            "default_params": self.default_params
        }
    
    def _error_response(
        self,
        error_message: str,
        elapsed_ms: int,
        is_transient: bool
    ) -> Dict[str, Any]:
        """
        Build standardized error response.
        
        Args:
            error_message: Error description
            elapsed_ms: Request latency
            is_transient: Whether error is retryable
        
        Returns:
            Error response with normalized structure
        """
        return {
            "assistant_message": {
                "role": "assistant",
                "content": [],  # Empty content on error
                "tool_calls": []
            },
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            },
            "_metadata": {
                "provider": self.provider,
                "model": self.model,
                "latency_ms": elapsed_ms,
                "error": True,
                "error_message": error_message,
                "transient": is_transient
            }
        }
    
    def _is_transient_error(self, error: Exception) -> bool:
        """
        Determine if error is transient (retryable).
        
        Args:
            error: The exception
        
        Returns:
            True if error is transient
        """
        error_str = str(error).lower()
        transient_indicators = [
            "timeout",
            "connection",
            "429",  # Rate limit
            "500",  # Server error
            "502",  # Bad gateway
            "503",  # Service unavailable
            "504",  # Gateway timeout
            "network",
            "temporary",
        ]
        return any(indicator in error_str for indicator in transient_indicators)
    
    def stream(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Stream model output as structured events.
        
        Yields:
            {"type": "model_token", "text": str, "ts": int}  # token chunks (future)
            {"type": "model_result", "data": {...}}  # final result
        
        For now, buffers full result and yields as single chunk.
        Future: Can enhance adapters to support true token streaming.
        """
        # Check if adapter supports streaming
        has_streaming = hasattr(self.adapter, 'stream') and callable(self.adapter.stream)
        
        if has_streaming:
            # True streaming support (future enhancement)
            try:
                for chunk in self.adapter.stream(input.get("messages", []), input.get("tools")):
                    if isinstance(chunk, dict) and "text" in chunk:
                        yield {
                            "type": "model_token",
                            "text": chunk["text"],
                            "ts": int(time.time() * 1000)
                        }
                    elif isinstance(chunk, str):
                        yield {
                            "type": "model_token",
                            "text": chunk,
                            "ts": int(time.time() * 1000)
                        }
            except Exception as e:
                logger.warning(f"[ChatModelRunnable] Streaming failed, falling back: {e}")
                has_streaming = False
        
        if not has_streaming:
            # Buffered mode: invoke and yield full result
            result = self.invoke(input, config)
            
            # Emit usage/metadata event
            if "_metadata" in result:
                yield {
                    "type": "model_result",
                    "usage": result.get("usage", {}),
                    "_metadata": result["_metadata"],
                    "ts": int(time.time() * 1000)
                }
            
            # Emit final result
            yield {
                "type": "result",
                "data": result
            }
    
    def bind_tools(self, tools: List[Dict[str, Any]]) -> "ChatModelRunnable":
        """
        Create a new ChatModelRunnable with tools pre-bound.
        
        This is a LangChain pattern for creating specialized versions.
        
        Args:
            tools: List of tool definitions to bind
        
        Returns:
            New ChatModelRunnable instance with tools pre-configured
        """
        # Create new instance with same config but bound tools
        new_runnable = ChatModelRunnable(
            adapter=self.adapter,
            provider=self.provider,
            model=self.model,
            temperature=self.temperature,
            name=self.name,
            **self.default_params
        )
        new_runnable._bound_tools = tools
        return new_runnable
    
    def __repr__(self) -> str:
        return f"ChatModelRunnable(provider='{self.provider}', model='{self.model}')"


class ChainOfThoughtRunnable(BaseLangChainRunnable[Dict[str, Any], Dict[str, Any]]):
    """
    Wraps a chat model with chain-of-thought prompting.
    
    This is an example of how to compose Runnables. It takes a base
    chat model and adds CoT instructions automatically.
    
    Example:
        base_model = ChatModelRunnable(adapter, ...)
        cot_model = ChainOfThoughtRunnable(base_model)
        
        result = cot_model.invoke({
            "messages": [{"role": "user", "content": "Solve: 2+2"}]
        })
        # Automatically adds "Let's think step by step" instruction
    """
    
    def __init__(
        self,
        chat_model: ChatModelRunnable,
        cot_instruction: str = "Let's think through this step by step:",
        name: Optional[str] = None
    ):
        """
        Initialize Chain of Thought wrapper.
        
        Args:
            chat_model: Base chat model to wrap
            cot_instruction: CoT prompt to inject
            name: Optional display name
        """
        super().__init__(name=name or f"CoT({chat_model.name})")
        self.chat_model = chat_model
        self.cot_instruction = cot_instruction
    
    def invoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Invoke with CoT instruction injected.
        
        Args:
            input: Same as ChatModelRunnable
            config: Runtime config
        
        Returns:
            Same as ChatModelRunnable
        """
        messages = input.get("messages", [])
        
        # Inject CoT instruction before last user message
        if messages and messages[-1].get("role") == "user":
            enhanced_content = f"{messages[-1]['content']}\n\n{self.cot_instruction}"
            enhanced_messages = messages[:-1] + [
                {**messages[-1], "content": enhanced_content}
            ]
        else:
            enhanced_messages = messages
        
        # Invoke base model with enhanced messages
        enhanced_input = {**input, "messages": enhanced_messages}
        return self.chat_model.invoke(enhanced_input, config)
    
    def __repr__(self) -> str:
        return f"ChainOfThoughtRunnable(base={self.chat_model})"


# ============================================================================
# Factory Functions
# ============================================================================

def create_chat_model_runnable(
    adapter: Any,
    provider: str,
    model: str,
    temperature: float = 0.7,
    **kwargs: Any
) -> ChatModelRunnable:
    """
    Factory function to create a ChatModelRunnable.
    
    Args:
        adapter: Model adapter instance
        provider: Provider name (openai, anthropic, etc.)
        model: Model identifier
        temperature: Sampling temperature
        **kwargs: Additional parameters
    
    Returns:
        ChatModelRunnable instance
    """
    return ChatModelRunnable(
        adapter=adapter,
        provider=provider,
        model=model,
        temperature=temperature,
        **kwargs
    )


def wrap_adapter_as_chat_model(
    adapter: Any,
    provider: str = "openai",
    model: str = "gpt-4",
    **kwargs: Any
) -> ChatModelRunnable:
    """
    Convenience function to wrap any adapter as a chat model Runnable.
    
    Args:
        adapter: Adapter with invoke(messages, tools) method
        provider: Provider name
        model: Model name
        **kwargs: Additional config
    
    Returns:
        ChatModelRunnable instance
    """
    return ChatModelRunnable(
        adapter=adapter,
        provider=provider,
        model=model,
        **kwargs
    )
