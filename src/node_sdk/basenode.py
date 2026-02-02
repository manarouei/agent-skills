"""
BaseNode - Abstract base class for Python node implementations.

Mirrors the contract at /home/toni/n8n/back/nodes/base.py
See contracts/BASENODE_CONTRACT.md for full specification.

All nodes inherit from BaseNode and implement the execute() method.

SYNC-CELERY SAFE: execute() is synchronous.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, TypedDict, Union

from pydantic import BaseModel, ConfigDict, Field


logger = logging.getLogger(__name__)


# ==============================================================================
# NodeParameterType - from /home/toni/n8n/back/nodes/base.py
# ==============================================================================

NodeParameterType = Literal[
    "string", "number", "boolean", "options", "multiOptions",
    "color", "json", "collection", "dateTime", "node",
    "resourceLocator", "notice", "array", "code",
]


class NodeParameterTypeEnum(str, Enum):
    """Enum version for convenience."""
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    OPTIONS = "options"
    MULTI_OPTIONS = "multiOptions"
    JSON = "json"
    COLLECTION = "collection"
    DATE_TIME = "dateTime"
    COLOR = "color"
    NODE = "node"
    RESOURCE_LOCATOR = "resourceLocator"
    NOTICE = "notice"
    ARRAY = "array"
    CODE = "code"


# ==============================================================================
# NodeParameter - Pydantic model for defining parameters
# ==============================================================================

class NodeParameter(BaseModel):
    """
    A single parameter in the node's properties.
    
    Can be used both as Pydantic model and as dict in properties.
    """
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    
    name: str = Field(..., description="Parameter key (internal name)")
    display_name: str = Field(..., alias="displayName", description="Human-readable label")
    type: NodeParameterType = Field(..., description="Parameter type")
    default: Any = Field(None, description="Default value")
    required: bool = Field(False, description="Is parameter required?")
    description: Optional[str] = Field(None, description="Help text")
    placeholder: Optional[str] = Field(None, description="Input placeholder")
    options: Optional[List[Dict[str, Any]]] = Field(
        None, 
        description="Options for options/multiOptions type"
    )
    display_options: Optional[Dict[str, Any]] = Field(
        None, 
        alias="displayOptions",
        description="Conditional visibility"
    )


class NodeCredential(BaseModel):
    """Credential requirement definition."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    
    name: str = Field(..., description="Credential type name")
    required: bool = Field(True, description="Is credential required?")
    display_name: Optional[str] = Field(None, alias="displayName")
    display_options: Optional[Dict[str, Any]] = Field(None, alias="displayOptions")


# ==============================================================================
# NodeExecutionData - Output data format
# ==============================================================================

class NodeExecutionData(TypedDict, total=False):
    """
    Single item of execution output data.
    
    Format: {"json": {...}, "binary": {...}, "pairedItem": {"item": 0}}
    """
    json: Dict[str, Any]
    binary: Optional[Dict[str, Any]]
    pairedItem: Optional[Dict[str, int]]


# ==============================================================================
# BaseNode - Abstract base class
# ==============================================================================

class BaseNode(ABC):
    """
    Abstract base class for all Python node implementations.
    
    Nodes define:
    - type: Unique identifier (e.g., "telegram")
    - version: Node version number
    - description: Node metadata dict
    - properties: Parameters and credentials
    
    And implement execute() which processes input items.
    
    SYNC-CELERY SAFE: All execution is synchronous.
    
    Example:
    
        class TelegramNode(BaseNode):
            type = "n8n-nodes-base.telegram"
            version = 1
            
            description = {
                "displayName": "Telegram",
                "name": "telegram",
                "description": "Send messages via Telegram",
                "group": ["output"],
                "version": 1,
                "inputs": ["main"],
                "outputs": ["main"],
                "credentials": [
                    {"name": "telegramApi", "required": True},
                ],
            }
            
            properties = {
                "parameters": [
                    {
                        "displayName": "Operation",
                        "name": "operation",
                        "type": "options",
                        "default": "sendMessage",
                        "options": [
                            {"name": "Send Message", "value": "sendMessage"},
                        ],
                    },
                ],
            }
            
            def execute(self) -> List[List[NodeExecutionData]]:
                items = self.get_input_data()
                operation = self.get_node_parameter("operation", 0)
                
                results = []
                for i, item in enumerate(items):
                    # Process item...
                    results.append({"json": {"result": "ok"}, "pairedItem": {"item": i}})
                
                return [results]  # Single output branch
    """
    
    # Required class attributes (override in subclasses)
    type: str = "base"
    version: int = 1
    
    # Node metadata - matches BASENODE_CONTRACT.md
    description: Dict[str, Any] = {
        "displayName": "Base Node",
        "name": "base",
        "description": "",
        "group": [],
        "version": 1,
        "inputs": ["main"],
        "outputs": ["main"],
    }
    
    # Node configuration - parameters and credentials
    properties: Dict[str, Any] = {
        "parameters": [],
        "credentials": [],
    }
    
    # Continue processing other items if one fails
    continue_on_fail: bool = False
    
    def __init__(self) -> None:
        """Initialize node instance."""
        self.logger = logging.getLogger(f"node.{self.type}")
        self._context: Optional[NodeExecutionContext] = None
    
    @abstractmethod
    def execute(self) -> List[List[NodeExecutionData]]:
        """
        Execute node operation.
        
        Returns:
            List[List[NodeExecutionData]]: Nested list of execution results.
            - Outer list represents output branches (usually 1)
            - Inner list represents items in that branch
            
        Raises:
            NodeOperationError: On operation failure
            NodeApiError: On API call failure
        """
        raise NotImplementedError
    
    # ==== Context Management ====
    
    def set_context(self, context: "NodeExecutionContext") -> None:
        """Set the execution context."""
        self._context = context
    
    # ==== Helper methods for subclasses ====
    
    def get_node_parameter(
        self, 
        name: str, 
        item_index: int = 0,
        default: Any = None,
    ) -> Any:
        """
        Get parameter value.
        
        Args:
            name: Parameter name
            item_index: Index of item (for expression resolution)
            default: Default if not set
        """
        if self._context is None:
            return default
        return self._context.get_node_parameter(name, item_index, default)
    
    def get_credentials(self, name: str) -> Dict[str, Any]:
        """
        Get credentials by type name.
        
        Args:
            name: Credential type name (e.g., "telegramApi")
            
        Returns:
            Credentials dict with decrypted values
        """
        if self._context is None:
            raise NodeOperationError("No context set")
        return self._context.get_credentials(name)
    
    def get_input_data(self) -> List[Dict[str, Any]]:
        """
        Get input items from previous node.
        
        Returns:
            List of input items, each with 'json' key.
        """
        if self._context is None:
            return []
        return self._context.get_input_data()
    
    def helpers_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Make HTTP request with timeout enforcement.
        
        This replaces n8n's this.helpers.request().
        SYNC-CELERY SAFE: Uses requests with timeout.
        
        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Passed to requests
            
        Returns:
            Response JSON
        """
        if self._context is None:
            raise NodeOperationError("No context set")
        return self._context.helpers_request(method, url, **kwargs)
    
    @classmethod
    def get_definition(cls) -> Dict[str, Any]:
        """Get full node definition for registration."""
        return {
            "type": cls.type,
            "version": cls.version,
            "description": cls.description,
            "properties": cls.properties,
        }


# ==============================================================================
# NodeExecutionContext - Runtime context for node execution
# ==============================================================================

class NodeExecutionContext:
    """
    Runtime context provided to nodes during execution.
    
    Provides access to:
    - Parameters
    - Credentials
    - Input data
    - HTTP helpers
    """
    
    def __init__(
        self,
        parameters: Dict[str, Any],
        credentials: Dict[str, Dict[str, Any]],
        input_data: List[Dict[str, Any]],
        workflow_id: Optional[str] = None,
        node_name: Optional[str] = None,
    ) -> None:
        self._parameters = parameters
        self._credentials = credentials
        self._input_data = input_data
        self.workflow_id = workflow_id
        self.node_name = node_name
    
    def get_node_parameter(
        self, 
        name: str, 
        item_index: int = 0,
        default: Any = None,
    ) -> Any:
        """Get parameter value."""
        value = self._parameters.get(name, default)
        # TODO: Expression resolution based on item_index
        return value
    
    def get_credentials(self, name: str) -> Dict[str, Any]:
        """Get credentials by type name."""
        if name not in self._credentials:
            raise NodeOperationError(f"Credentials '{name}' not found")
        return self._credentials[name]
    
    def get_input_data(self) -> List[Dict[str, Any]]:
        """Get input items."""
        return self._input_data
    
    def helpers_request(
        self,
        method: str,
        url: str,
        timeout: float = 30.0,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Make HTTP request.
        
        SYNC-CELERY SAFE: Timeout enforced.
        """
        import requests
        
        # Enforce timeout
        kwargs.setdefault("timeout", timeout)
        
        response = requests.request(method, url, **kwargs)
        response.raise_for_status()
        
        return response.json()


# ==============================================================================
# Errors
# ==============================================================================

class NodeOperationError(Exception):
    """Error during node operation."""
    
    def __init__(
        self,
        message: str,
        node: Optional[BaseNode] = None,
        item_index: Optional[int] = None,
    ) -> None:
        self.message = message
        self.node = node
        self.item_index = item_index
        super().__init__(message)


class NodeApiError(NodeOperationError):
    """Error from external API call."""
    
    def __init__(
        self,
        message: str,
        node: Optional[BaseNode] = None,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ) -> None:
        super().__init__(message, node)
        self.status_code = status_code
        self.response_body = response_body


# ==============================================================================
# Exports
# ==============================================================================

__all__ = [
    "BaseNode",
    "NodeExecutionContext",
    "NodeExecutionData",
    "NodeParameter",
    "NodeCredential",
    "NodeParameterType",
    "NodeParameterTypeEnum",
    "NodeOperationError",
    "NodeApiError",
]
