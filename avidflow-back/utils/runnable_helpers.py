"""
Helper utilities for Runnable lifecycle management and provider resolution.

This module provides utilities for:
- Automatic Runnable registration/cleanup via context managers
- Lazy provider resolution from upstream nodes
- Runnable instantiation from workflow context
"""
from contextlib import contextmanager
from typing import Optional, Iterator, Any
import logging

from utils.langchain_base import BaseLangChainRunnable, RunnableRegistry

logger = logging.getLogger(__name__)


@contextmanager
def managed_runnable(node: Any, item_index: int = 0) -> Iterator[BaseLangChainRunnable]:
    """
    Context manager for automatic Runnable registration and cleanup.
    
    Ensures Runnables are properly unregistered even if exceptions occur.
    
    Args:
        node: Node instance with get_runnable() method
        item_index: Item index for parameter resolution
    
    Yields:
        Runnable instance
    
    Example:
        with managed_runnable(chat_model_node) as chat_model:
            result = chat_model.invoke({"messages": [...]})
        # Auto-cleanup after context exit
    """
    if not hasattr(node, 'get_runnable'):
        raise AttributeError(f"Node {node.__class__.__name__} does not have get_runnable() method")
    
    runnable = node.get_runnable(item_index)
    runnable_id = RunnableRegistry.register(runnable)
    
    try:
        yield runnable
    finally:
        try:
            RunnableRegistry.unregister(runnable_id)
        except Exception as e:
            logger.warning(f"[managed_runnable] Cleanup error: {e}")


def get_runnable_from_provider(
    workflow: Any,
    execution_data: dict,
    node_name: str,
    input_name: str,
    item_index: int = 0
) -> Optional[BaseLangChainRunnable]:
    """
    Resolve and get Runnable from an upstream provider node.
    
    Follows n8n lazy execution pattern:
    1. Find upstream nodes connected to specified input
    2. Instantiate provider node
    3. Call get_runnable() to get Runnable instance
    
    Args:
        workflow: WorkflowModel instance
        execution_data: Execution data dict
        node_name: Current node's name
        input_name: Input type (e.g., "ai_model", "ai_memory")
        item_index: Item index for parameter resolution
    
    Returns:
        Runnable instance or None if not found
    
    Example:
        chat_model = get_runnable_from_provider(
            workflow=self.workflow,
            execution_data=self.execution_data,
            node_name="AI Agent",
            input_name="ai_model"
        )
    """
    from utils.connection_resolver import ConnectionResolver
    from nodes import node_definitions
    
    try:
        # Get upstream nodes connected to this input
        upstream_nodes = ConnectionResolver.get_upstream_nodes(
            workflow, node_name, input_name
        )
        
        if not upstream_nodes:
            logger.warning(
                f"[get_runnable_from_provider] No upstream nodes for "
                f"{node_name}.{input_name}"
            )
            return None
        
        # Get first upstream provider
        provider_node_model = upstream_nodes[0]
        
        # Get node class from registry
        node_def = node_definitions.get(provider_node_model.type)
        if not node_def:
            logger.error(
                f"[get_runnable_from_provider] Node type {provider_node_model.type} "
                f"not found in node_definitions registry"
            )
            return None
        
        node_cls = node_def.get('node_class')
        if not node_cls:
            logger.error(
                f"[get_runnable_from_provider] No node_class found "
                f"for type: {provider_node_model.type}"
            )
            return None
        
        # Instantiate provider node
        provider_node = node_cls(
            node_data=provider_node_model,
            workflow=workflow,
            execution_data=execution_data
        )
        
        # Check if node exposes Runnable
        if not hasattr(provider_node, 'get_runnable'):
            logger.error(
                f"[get_runnable_from_provider] Node {provider_node_model.name} "
                f"(type: {provider_node_model.type}) does not have get_runnable() method"
            )
            return None
        
        # Get Runnable
        runnable = provider_node.get_runnable(item_index)
        
        logger.info(
            f"[get_runnable_from_provider] Got {runnable.__class__.__name__} "
            f"from {provider_node_model.name}"
        )
        
        return runnable
        
    except Exception as e:
        logger.error(
            f"[get_runnable_from_provider] Error getting Runnable from "
            f"{input_name}: {e}",
            exc_info=True
        )
        return None


def get_all_runnables_from_input(
    workflow: Any,
    execution_data: dict,
    node_name: str,
    input_name: str,
    item_index: int = 0
) -> list[BaseLangChainRunnable]:
    """
    Get all Runnables from upstream nodes connected to an input.
    
    Useful for inputs that accept multiple connections (e.g., ai_tool).
    
    Args:
        workflow: WorkflowModel instance
        execution_data: Execution data dict
        node_name: Current node's name
        input_name: Input type
        item_index: Item index for parameter resolution
    
    Returns:
        List of Runnable instances
    """
    from utils.connection_resolver import ConnectionResolver
    from nodes import node_definitions
    
    runnables = []
    
    try:
        # Get all upstream nodes
        upstream_nodes = ConnectionResolver.get_upstream_nodes(
            workflow, node_name, input_name
        )
        
        for provider_node_model in upstream_nodes:
            # Get node class from registry
            node_def = node_definitions.get(provider_node_model.type)
            if not node_def:
                logger.warning(
                    f"[get_all_runnables_from_input] Node type {provider_node_model.type} "
                    f"not found in registry"
                )
                continue
            
            node_cls = node_def.get('node_class')
            if not node_cls:
                logger.warning(
                    f"[get_all_runnables_from_input] No node_class for "
                    f"{provider_node_model.type}"
                )
                continue
            
            # Instantiate node
            provider_node = node_cls(
                node_data=provider_node_model,
                workflow=workflow,
                execution_data=execution_data
            )
            
            # Get Runnable if available
            if hasattr(provider_node, 'get_runnable'):
                runnable = provider_node.get_runnable(item_index)
                runnables.append(runnable)
            else:
                logger.warning(
                    f"[get_all_runnables_from_input] Node {provider_node_model.name} "
                    f"has no get_runnable() method"
                )
        
    except Exception as e:
        logger.error(
            f"[get_all_runnables_from_input] Error: {e}",
            exc_info=True
        )
    
    return runnables
