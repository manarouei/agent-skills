"""
LangChain LCEL/Runnable base infrastructure for n8n-style nodes.

This module provides the foundation for integrating LangChain's Runnable interface
with our existing node system. It allows nodes to optionally expose LangChain-compatible
APIs while maintaining backward compatibility with the current execution model.

Key Components:
- BaseLangChainRunnable: Abstract base for all LangChain-aware components
- RunnableAdapter: Protocol for wrapping existing adapters
- RunnableRegistry: Central registry for Runnable instances
- Message conversion utilities for LangChain format
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Union, Iterator, AsyncIterator, Protocol, TypeVar, Generic
from abc import ABC, abstractmethod
import threading
import uuid
import logging

logger = logging.getLogger(__name__)

# Type variable for Runnable input/output
Input = TypeVar("Input")
Output = TypeVar("Output")


# ============================================================================
# Core Protocols and Base Classes
# ============================================================================

class RunnableProtocol(Protocol[Input, Output]):
    """
    Protocol matching LangChain's Runnable interface.
    
    This allows us to gradually adopt LangChain patterns without requiring
    full LangChain installation or breaking existing code.
    """
    
    def invoke(self, input: Input, config: Optional[Dict[str, Any]] = None) -> Output:
        """Synchronously invoke the runnable with given input"""
        ...
    
    def stream(self, input: Input, config: Optional[Dict[str, Any]] = None) -> Iterator[Output]:
        """Stream output chunks"""
        ...
    
    def batch(
        self, 
        inputs: List[Input], 
        config: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None
    ) -> List[Output]:
        """Process multiple inputs in batch"""
        ...


class BaseLangChainRunnable(ABC, Generic[Input, Output]):
    """
    Base class for LangChain-compatible Runnables in our system.
    
    This wraps our existing adapters/executors with LangChain's Runnable interface,
    enabling:
    - Composability with LCEL chains
    - Streaming support (where applicable)
    - Batch processing
    - Uniform error handling
    
    Design:
    - Synchronous by default (Celery compatibility)
    - Optional async methods for future WebSocket streaming
    - Delegates to existing infrastructure (adapters, registries)
    - STANDARDIZED OUTPUT: All invoke() methods SHOULD return wrapped output
    """
    
    def __init__(self, name: Optional[str] = None, **kwargs: Any):
        self.name = name or self.__class__.__name__
        self._config: Dict[str, Any] = kwargs
    
    def _wrap_output(
        self,
        data: Any,
        metadata: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Wrap output in standard format for LCEL composition.
        
        STANDARD OUTPUT CONTRACT:
        {
            "success": bool,  # True if no error
            "data": Any,  # The actual result data
            "metadata": Dict,  # Additional context (provider, latency, etc.)
            "error": str | None  # Error message if failed
        }
        
        This enables:
        - Consistent error handling in chains
        - Metadata propagation (token usage, latency, etc.)
        - Predictable composition (always check 'success' field)
        
        Args:
            data: The actual result data (can be any type)
            metadata: Optional metadata dict (provider, model, usage, etc.)
            error: Optional error message (if present, success=False)
        
        Returns:
            Standardized output dict
        
        Example:
            # Success case
            return self._wrap_output(
                data={"message": "Hello!"},
                metadata={"model": "gpt-4", "tokens": 50}
            )
            # Returns: {"success": True, "data": {...}, "metadata": {...}, "error": None}
            
            # Error case
            return self._wrap_output(
                data=None,
                metadata={"model": "gpt-4"},
                error="Rate limit exceeded"
            )
            # Returns: {"success": False, "data": None, "metadata": {...}, "error": "..."}
        """
        return {
            "success": error is None,
            "data": data,
            "metadata": metadata or {},
            "error": error
        }
    
    def _get_metadata(self) -> Dict[str, Any]:
        """
        Extract metadata about this Runnable for output wrapping.
        
        Override in subclasses to provide specific metadata.
        
        Returns:
            Metadata dict (provider, model, etc.)
        """
        return {
            "runnable_type": self.__class__.__name__,
            "runnable_name": self.name
        }
    
    @abstractmethod
    def invoke(self, input: Input, config: Optional[Dict[str, Any]] = None) -> Output:
        """
        Synchronously invoke the runnable.
        
        IMPORTANT: Implementations SHOULD use _wrap_output() for consistency,
        though not strictly enforced for backward compatibility.
        
        Args:
            input: Input data (type depends on Runnable)
            config: Optional runtime configuration (callbacks, tags, etc.)
        
        Returns:
            Output data (type depends on Runnable)
        """
        pass
    
    def stream(self, input: Input, config: Optional[Dict[str, Any]] = None) -> Iterator[Output]:
        """
        Stream output chunks (default: fallback to buffered invoke).
        
        Override this in subclasses that support true streaming.
        Yields structured event dictionaries with "type" field.
        """
        # Default: Yield full result as single chunk
        result = self.invoke(input, config)
        yield {"type": "result", "data": result}
    
    def batch(
        self,
        inputs: List[Input],
        config: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None
    ) -> List[Output]:
        """
        Process multiple inputs (default: sequential invoke).
        
        Override for parallel/optimized batch processing.
        """
        configs = self._get_config_list(config, len(inputs))
        return [self.invoke(inp, cfg) for inp, cfg in zip(inputs, configs)]
    
    def _get_config_list(
        self,
        config: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]],
        length: int
    ) -> List[Optional[Dict[str, Any]]]:
        """Helper to normalize config to list of configs"""
        if config is None:
            return [None] * length
        if isinstance(config, list):
            return config + [None] * (length - len(config))
        return [config] * length
    
    def with_config(self, **kwargs: Any) -> "BaseLangChainRunnable[Input, Output]":
        """Create a new instance with updated configuration"""
        new_config = {**self._config, **kwargs}
        return self.__class__(name=self.name, **new_config)
    
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"


# ============================================================================
# Message Format Utilities
# ============================================================================

class MessageConverter:
    """
    Convert between our internal message format and LangChain's format.
    
    Our format: {"role": "user"|"assistant"|"system"|"tool", "content": str, ...}
    LangChain format: HumanMessage, AIMessage, SystemMessage, ToolMessage, etc.
    
    For now, we work with dicts to avoid LangChain dependencies.
    Later, can add proper LangChain message types.
    """
    
    @staticmethod
    def to_langchain_dict(message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert our message format to LangChain-compatible dict.
        
        Args:
            message: Our internal message format
        
        Returns:
            LangChain-compatible message dict
        """
        role = message.get("role", "user")
        content = message.get("content", "")
        
        # Map our roles to LangChain types
        role_map = {
            "user": "human",
            "assistant": "ai",
            "system": "system",
            "tool": "tool"
        }
        
        lc_msg = {
            "type": role_map.get(role, role),
            "content": content,
        }
        
        # Preserve additional fields (tool_calls, function_call, etc.)
        for key in ("tool_calls", "function_call", "name", "tool_call_id"):
            if key in message:
                lc_msg[key] = message[key]
        
        return lc_msg
    
    @staticmethod
    def from_langchain_dict(lc_message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert LangChain message dict to our format.
        
        Args:
            lc_message: LangChain message dict
        
        Returns:
            Our internal message format
        """
        msg_type = lc_message.get("type", "human")
        
        # Reverse mapping
        type_map = {
            "human": "user",
            "ai": "assistant",
            "system": "system",
            "tool": "tool"
        }
        
        msg = {
            "role": type_map.get(msg_type, msg_type),
            "content": lc_message.get("content", "")
        }
        
        # Preserve additional fields
        for key in ("tool_calls", "function_call", "name", "tool_call_id"):
            if key in lc_message:
                msg[key] = lc_message[key]
        
        return msg
    
    @staticmethod
    def messages_to_langchain(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert a list of messages to LangChain format"""
        return [MessageConverter.to_langchain_dict(m) for m in messages]
    
    @staticmethod
    def messages_from_langchain(lc_messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert a list of LangChain messages to our format"""
        return [MessageConverter.from_langchain_dict(m) for m in lc_messages]


# ============================================================================
# Runnable Registry
# ============================================================================

class _RunnableRegistry:
    """
    Central registry for Runnable instances.
    
    Similar to ModelRegistry but for LangChain Runnables.
    Allows nodes to:
    1. Register a Runnable and get an ID
    2. Retrieve Runnable by ID for composition
    3. Clean up when done
    
    Thread-safe for Celery workers.
    """
    
    def __init__(self):
        self._lock = threading.Lock()
        self._store: Dict[str, BaseLangChainRunnable] = {}
    
    def register(self, runnable: BaseLangChainRunnable) -> str:
        """
        Register a Runnable and return its ID.
        
        Args:
            runnable: The Runnable instance to register
        
        Returns:
            Unique ID for this Runnable
        """
        runnable_id = uuid.uuid4().hex
        with self._lock:
            self._store[runnable_id] = runnable
        logger.debug(f"Registered Runnable: {runnable.name} (id={runnable_id})")
        return runnable_id
    
    def get(self, runnable_id: str) -> Optional[BaseLangChainRunnable]:
        """
        Retrieve a Runnable by ID.
        
        Args:
            runnable_id: The Runnable's unique ID
        
        Returns:
            The Runnable instance or None if not found
        """
        with self._lock:
            return self._store.get(runnable_id)
    
    def unregister(self, runnable_id: str) -> None:
        """
        Remove a Runnable from the registry.
        
        Args:
            runnable_id: The Runnable's unique ID
        """
        with self._lock:
            runnable = self._store.pop(runnable_id, None)
            if runnable:
                logger.debug(f"Unregistered Runnable: {runnable.name} (id={runnable_id})")
    
    def clear(self) -> None:
        """Clear all registered Runnables (useful for testing)"""
        with self._lock:
            count = len(self._store)
            self._store.clear()
            logger.debug(f"Cleared {count} Runnables from registry")


# Global registry instance
RunnableRegistry = _RunnableRegistry()


# ============================================================================
# Adapter Wrapper
# ============================================================================

class RunnableAdapter(BaseLangChainRunnable[Dict[str, Any], Dict[str, Any]]):
    """
    Wraps our existing ModelAdapterProtocol as a LangChain Runnable.
    
    This allows existing adapters (OpenAIChatAdapter, etc.) to be used
    in LCEL chains without modification.
    
    Example:
        adapter = _OpenAIChatAdapter(...)
        runnable = RunnableAdapter(adapter, name="OpenAI GPT-4")
        
        # Now can use in LCEL chains
        result = runnable.invoke({
            "messages": [...],
            "tools": [...]
        })
    """
    
    def __init__(
        self,
        adapter: Any,  # ModelAdapterProtocol
        name: Optional[str] = None,
        **kwargs: Any
    ):
        super().__init__(name=name or "ModelAdapter", **kwargs)
        self.adapter = adapter
    
    def invoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Invoke the underlying adapter.
        
        Args:
            input: Dict with "messages" and optional "tools"
            config: Optional runtime config (ignored for now)
        
        Returns:
            Dict with "assistant_message" and "tool_calls"
        """
        messages = input.get("messages", [])
        tools = input.get("tools")
        
        try:
            result = self.adapter.invoke(messages=messages, tools=tools)
            return result
        except Exception as e:
            logger.error(f"RunnableAdapter invoke error: {e}")
            return {
                "error": str(e),
                "assistant_message": {"role": "assistant", "content": ""},
                "tool_calls": []
            }
    
    def stream(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Stream output (fallback to single invoke for now).
        
        Can be enhanced later if adapters support streaming.
        """
        yield self.invoke(input, config)


# ============================================================================
# Utility Functions
# ============================================================================

def wrap_adapter_as_runnable(adapter: Any, name: Optional[str] = None) -> RunnableAdapter:
    """
    Convenience function to wrap an adapter as a Runnable.
    
    Args:
        adapter: Any object with invoke(messages, tools) method
        name: Optional name for the Runnable
    
    Returns:
        RunnableAdapter instance
    """
    return RunnableAdapter(adapter, name=name)


def create_runnable_from_registry_id(
    registry_id: str,
    registry: Any,  # ModelRegistry or similar
    name: Optional[str] = None
) -> Optional[RunnableAdapter]:
    """
    Create a Runnable from a registry ID.
    
    Args:
        registry_id: ID of adapter in registry
        registry: Registry instance (ModelRegistry, etc.)
        name: Optional name for the Runnable
    
    Returns:
        RunnableAdapter or None if not found
    """
    adapter = registry.get(registry_id)
    if adapter:
        return RunnableAdapter(adapter, name=name)
    return None
