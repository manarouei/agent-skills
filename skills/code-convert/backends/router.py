#!/usr/bin/env python3
"""
Backend Router

Routes node conversion to the appropriate backend based on semantic class.
This is the central dispatch mechanism that enables universal node conversion.
"""

from __future__ import annotations
import importlib.util
import os
from typing import Any, Dict

# Define semantic class values as strings to avoid circular import issues
SEMANTIC_CLASSES = {
    "http_rest": "http_rest",
    "tcp_client": "tcp_client",
    "sdk_client": "sdk_client",
    "pure_transform": "pure_transform",
    "stateful": "stateful",
}

# Get the backends directory path
BACKENDS_DIR = os.path.dirname(__file__)


def _load_backend_module(name: str):
    """Load a backend module by name using importlib."""
    module_path = os.path.join(BACKENDS_DIR, f"{name}.py")
    spec = importlib.util.spec_from_file_location(name, module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def route_to_backend(
    semantic_class: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Route conversion to the appropriate backend based on semantic class.
    
    Args:
        semantic_class: The node's semantic classification (string)
        context: Dict with node_name, node_schema, ts_code, properties, execution_contract
    
    Returns:
        Dict with:
        - python_code: Generated Python code
        - imports: Required imports
        - helpers: Helper methods
        - conversion_notes: Notes about the conversion
    """
    # Extract context params
    node_name = context.get("node_name", "")
    node_schema = context.get("node_schema", {})
    ts_code = context.get("ts_code", "")
    properties = context.get("properties", [])
    execution_contract = context.get("execution_contract", {})
    
    # Normalize semantic class to string
    if hasattr(semantic_class, "value"):
        semantic_class = semantic_class.value
    semantic_class = str(semantic_class).lower()
    
    # Route to appropriate backend
    if semantic_class == "http_rest":
        module = _load_backend_module("http_rest")
        return module.convert_http_rest_node(
            node_name=node_name,
            node_schema=node_schema,
            ts_code=ts_code,
            properties=properties,
            execution_contract=execution_contract,
        )
    
    elif semantic_class == "tcp_client":
        module = _load_backend_module("tcp_client")
        return module.convert_tcp_client_node(
            node_name=node_name,
            node_schema=node_schema,
            ts_code=ts_code,
            properties=properties,
            execution_contract=execution_contract,
        )
    
    elif semantic_class == "sdk_client":
        module = _load_backend_module("sdk_client")
        return module.convert_sdk_client_node(
            node_name=node_name,
            node_schema=node_schema,
            ts_code=ts_code,
            properties=properties,
            execution_contract=execution_contract,
        )
    
    elif semantic_class == "pure_transform":
        module = _load_backend_module("pure_transform")
        return module.convert_pure_transform_node(
            node_name=node_name,
            node_schema=node_schema,
            ts_code=ts_code,
            properties=properties,
            execution_contract=execution_contract,
        )
    
    elif semantic_class == "stateful":
        module = _load_backend_module("stateful")
        return module.convert_stateful_node(
            node_name=node_name,
            node_schema=node_schema,
            ts_code=ts_code,
            properties=properties,
            execution_contract=execution_contract,
        )
    
    else:
        # Unknown semantic class - use HTTP REST as fallback
        module = _load_backend_module("http_rest")
        return module.convert_http_rest_node(
            node_name=node_name,
            node_schema=node_schema,
            ts_code=ts_code,
            properties=properties,
            execution_contract=execution_contract,
        )
