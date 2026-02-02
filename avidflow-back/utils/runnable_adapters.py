"""
Schema adapters for LangChain Runnable composition.

Enables chaining Runnables with incompatible input/output schemas by providing
automatic key mapping and transformation layers.
"""
from __future__ import annotations
from typing import Any, Dict, Optional, Callable
import logging

from utils.langchain_base import BaseLangChainRunnable

logger = logging.getLogger(__name__)


class SchemaAdapter(BaseLangChainRunnable[Dict[str, Any], Dict[str, Any]]):
    """
    Adapter for mapping input/output schemas between incompatible Runnables.
    
    Problem:
    - Different Runnables expect different input key names
    - Example: Retriever expects "query", Agent expects "user_input"
    - Direct composition fails: retriever | agent ❌
    
    Solution:
    - SchemaAdapter maps keys transparently
    - Enables composition: retriever | adapter | agent ✅
    
    Input format:
        Any dict (depends on source Runnable)
    
    Output format:
        Transformed dict with mapped keys
    
    Example:
        # Agent expects "user_input", but retriever returns "query"
        adapter = SchemaAdapter(
            runnable=agent,
            input_map={"query": "user_input"}
        )
        
        # Now composable:
        chain = retriever | adapter
        result = chain.invoke({"query": "What is LangChain?"})
        # adapter transforms {"query": "..."} → {"user_input": "..."}
        # before passing to agent
    """
    
    def __init__(
        self,
        runnable: BaseLangChainRunnable,
        input_map: Optional[Dict[str, str]] = None,
        output_map: Optional[Dict[str, str]] = None,
        input_transform: Optional[Callable[[Dict], Dict]] = None,
        output_transform: Optional[Callable[[Dict], Dict]] = None,
        name: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Initialize Schema Adapter.
        
        Args:
            runnable: The underlying Runnable to wrap
            input_map: Map of input keys: {source_key: target_key}
            output_map: Map of output keys: {source_key: target_key}
            input_transform: Optional custom input transformation function
            output_transform: Optional custom output transformation function
            name: Optional adapter name
            **kwargs: Additional config
        
        Example:
            # Simple key mapping
            adapter = SchemaAdapter(
                runnable=agent,
                input_map={"query": "user_input", "docs": "context"}
            )
            
            # Custom transformation
            def transform(data):
                return {
                    "user_input": data["query"],
                    "context": "\n".join(d["content"] for d in data["documents"])
                }
            
            adapter = SchemaAdapter(
                runnable=agent,
                input_transform=transform
            )
        """
        super().__init__(name=name or f"Adapter({runnable.name})", **kwargs)
        self.runnable = runnable
        self.input_map = input_map or {}
        self.output_map = output_map or {}
        self.input_transform = input_transform
        self.output_transform = output_transform
    
    def invoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Invoke with schema adaptation.
        
        Args:
            input: Input dict with source schema
            config: Runtime config
        
        Returns:
            Output dict (possibly with adapted schema)
        """
        try:
            # Transform input
            if self.input_transform:
                # Custom transformation
                transformed_input = self.input_transform(input)
            elif self.input_map:
                # Key mapping
                transformed_input = self._map_keys(input, self.input_map)
            else:
                # Pass through
                transformed_input = input
            
            logger.debug(
                f"[SchemaAdapter] Input transformation: {list(input.keys())} → "
                f"{list(transformed_input.keys())}"
            )
            
            # Invoke wrapped Runnable
            result = self.runnable.invoke(transformed_input, config)
            
            # Transform output
            if self.output_transform:
                # Custom transformation
                transformed_output = self.output_transform(result)
            elif self.output_map:
                # Key mapping
                transformed_output = self._map_keys(result, self.output_map)
            else:
                # Pass through
                transformed_output = result
            
            return transformed_output
            
        except Exception as e:
            logger.error(f"[SchemaAdapter] Error in schema adaptation: {e}")
            return self._wrap_output(
                data=None,
                metadata=self._get_metadata(),
                error=str(e)
            )
    
    def _map_keys(
        self,
        data: Dict[str, Any],
        key_map: Dict[str, str]
    ) -> Dict[str, Any]:
        """
        Map keys according to mapping dict.
        
        Args:
            data: Source dict
            key_map: Mapping {source_key: target_key}
        
        Returns:
            Transformed dict with mapped keys
        """
        result = {}
        
        # Map specified keys
        for source_key, target_key in key_map.items():
            if source_key in data:
                result[target_key] = data[source_key]
        
        # Preserve unmapped keys
        for key, value in data.items():
            if key not in key_map:
                result[key] = value
        
        return result
    
    def _get_metadata(self) -> Dict[str, Any]:
        """
        Override: Provide adapter-specific metadata.
        
        Returns:
            Metadata about adapter configuration
        """
        return {
            "runnable_type": "SchemaAdapter",
            "runnable_name": self.name,
            "wrapped_runnable": self.runnable.name,
            "input_map": self.input_map,
            "output_map": self.output_map,
            "has_input_transform": self.input_transform is not None,
            "has_output_transform": self.output_transform is not None
        }
    
    def __repr__(self) -> str:
        return f"SchemaAdapter(wraps={self.runnable}, input_map={self.input_map})"


class PassthroughAdapter(BaseLangChainRunnable[Dict[str, Any], Dict[str, Any]]):
    """
    Simple passthrough adapter that extracts a single field from output.
    
    Useful for extracting specific fields from complex outputs.
    
    Example:
        # Agent returns {"success": True, "message": "...", ...}
        # But next step needs just the message
        
        adapter = PassthroughAdapter(
            runnable=agent,
            output_field="message"
        )
        
        result = adapter.invoke({"user_input": "Hello"})
        # Returns: "..." (just the message string)
    """
    
    def __init__(
        self,
        runnable: BaseLangChainRunnable,
        output_field: str,
        name: Optional[str] = None,
        **kwargs: Any
    ):
        """
        Initialize Passthrough Adapter.
        
        Args:
            runnable: The underlying Runnable
            output_field: Field to extract from output
            name: Optional adapter name
            **kwargs: Additional config
        """
        super().__init__(name=name or f"Extract({output_field})", **kwargs)
        self.runnable = runnable
        self.output_field = output_field
    
    def invoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Any:
        """
        Invoke and extract field.
        
        Args:
            input: Input dict
            config: Runtime config
        
        Returns:
            Extracted field value
        """
        try:
            result = self.runnable.invoke(input, config)
            
            if isinstance(result, dict) and self.output_field in result:
                return result[self.output_field]
            else:
                logger.warning(
                    f"[PassthroughAdapter] Field '{self.output_field}' not found in result"
                )
                return result
                
        except Exception as e:
            logger.error(f"[PassthroughAdapter] Error: {e}")
            return None
    
    def __repr__(self) -> str:
        return f"PassthroughAdapter(extract='{self.output_field}' from {self.runnable})"


# ============================================================================
# Factory Functions
# ============================================================================

def adapt_schema(
    runnable: BaseLangChainRunnable,
    input_map: Optional[Dict[str, str]] = None,
    output_map: Optional[Dict[str, str]] = None,
    **kwargs: Any
) -> SchemaAdapter:
    """
    Factory function to create a SchemaAdapter.
    
    Args:
        runnable: Runnable to wrap
        input_map: Input key mapping
        output_map: Output key mapping
        **kwargs: Additional config
    
    Returns:
        SchemaAdapter instance
    
    Example:
        adapted_agent = adapt_schema(
            agent,
            input_map={"query": "user_input"}
        )
    """
    return SchemaAdapter(
        runnable=runnable,
        input_map=input_map,
        output_map=output_map,
        **kwargs
    )


def extract_field(
    runnable: BaseLangChainRunnable,
    field: str
) -> PassthroughAdapter:
    """
    Factory function to create a PassthroughAdapter.
    
    Args:
        runnable: Runnable to wrap
        field: Field to extract
    
    Returns:
        PassthroughAdapter instance
    
    Example:
        message_only = extract_field(agent, "message")
    """
    return PassthroughAdapter(runnable=runnable, output_field=field)


# ============================================================================
# Common Adapters
# ============================================================================

def retriever_to_agent_adapter(
    agent: BaseLangChainRunnable
) -> SchemaAdapter:
    """
    Adapter for connecting retriever output to agent input.
    
    Transforms:
    - {"documents": [...], "query": str} → {"user_input": str, "context": [...]}
    
    Args:
        agent: Agent Runnable
    
    Returns:
        SchemaAdapter configured for retriever→agent composition
    
    Example:
        chain = retriever | retriever_to_agent_adapter(agent)
        result = chain.invoke({"query": "What is RAG?"})
    """
    def transform(data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform retriever output to agent input"""
        return {
            "user_input": data.get("query", ""),
            "context": data.get("documents", [])
        }
    
    return SchemaAdapter(
        runnable=agent,
        input_transform=transform,
        name="RetrieverToAgent"
    )


def query_to_user_input_adapter(
    runnable: BaseLangChainRunnable
) -> SchemaAdapter:
    """
    Simple adapter for query→user_input mapping.
    
    Args:
        runnable: Runnable expecting "user_input"
    
    Returns:
        SchemaAdapter for query key mapping
    
    Example:
        adapted = query_to_user_input_adapter(agent)
        result = adapted.invoke({"query": "Hello"})
    """
    return SchemaAdapter(
        runnable=runnable,
        input_map={"query": "user_input"},
        name="QueryToUserInput"
    )
