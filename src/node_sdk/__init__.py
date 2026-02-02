"""
Node SDK - Minimal Python node execution semantics.

This package provides the runtime for executing Python nodes:
- NodeItem: Data item flowing through workflows
- NodeExecutionContext: Runtime context for a node
- BaseNode: Abstract base class for node implementations

Mirrors the contract at /home/toni/n8n/back/nodes/base.py
See contracts/BASENODE_CONTRACT.md for full specification.

All nodes execute synchronously (sync-Celery safe).
"""

from .items import NodeItem, BinaryData
from .basenode import (
    BaseNode,
    NodeExecutionContext,
    NodeExecutionData,
    NodeParameter,
    NodeCredential,
    NodeParameterType,
    NodeParameterTypeEnum,
    NodeOperationError,
    NodeApiError,
)
from .http import HttpClient, HttpResponse

__all__ = [
    # Items
    "NodeItem",
    "BinaryData",
    "NodeExecutionData",
    # Context
    "NodeExecutionContext",
    # Base class
    "BaseNode",
    "NodeParameter",
    "NodeCredential",
    "NodeParameterType",
    "NodeParameterTypeEnum",
    # Errors
    "NodeOperationError", 
    "NodeApiError",
    # HTTP
    "HttpClient",
    "HttpResponse",
]

