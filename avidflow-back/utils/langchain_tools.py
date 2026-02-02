"""
LangChain-compatible Tool abstractions.

Wraps our existing tool executors as LangChain Tools/StructuredTools,
enabling them to be used in LCEL chains and agent compositions.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Callable, Tuple
import logging
import json
import time
from pydantic import BaseModel, Field, create_model, ValidationError

from utils.langchain_base import BaseLangChainRunnable

logger = logging.getLogger(__name__)


class ToolRunnable(BaseLangChainRunnable[Dict[str, Any], Dict[str, Any]]):
    """
    LangChain-compatible wrapper for tool executors.
    
    Wraps our existing tool execution pattern (node_cls, node_model, executor)
    as a Runnable that can be composed in LCEL chains.
    
    Input format:
        {
            "arguments": Dict[str, Any],  # tool arguments
            "context": Optional[Dict[str, Any]]  # execution context
        }
    
    Output format:
        {
            "result": Any,  # tool execution result
            "success": bool,  # execution status
            "error": Optional[str]  # error message if failed
        }
    
    Example:
        tool = ToolRunnable(
            name="search_database",
            description="Search the knowledge base",
            executor=lambda args: search_fn(**args),
            schema={"query": {"type": "string", "required": True}}
        )
        
        result = tool.invoke({
            "arguments": {"query": "What is n8n?"}
        })
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        executor: Callable[[Dict[str, Any]], Tuple[Any, Any]],  # (result, node_model)
        schema: Dict[str, Any],
        node_model: Optional[Any] = None,
        **kwargs: Any
    ):
        """
        Initialize Tool Runnable.
        
        Args:
            name: Tool name (must be valid identifier)
            description: Human-readable description
            executor: Callable that executes the tool
            schema: Parameter schema (JSON Schema-like)
            node_model: Optional node model reference
            **kwargs: Additional config
        """
        super().__init__(name=name, **kwargs)
        self.description = description
        self.executor = executor
        self.schema = schema
        self.node_model = node_model
        
        # Build Pydantic model from schema for validation
        self._validator = self._build_pydantic_validator(schema)
    
    def invoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute the tool with given arguments.
        
        ALWAYS returns structured format:
        {
            "ok": True/False,
            "name": str,
            "tool_call_id": str | None,
            "data": Any,  # Only on success
            "error": {...},  # Only on failure
            "_metadata": {"elapsed_ms": int, ...}
        }
        
        Args:
            input: Dict with "arguments" and optional "context", "tool_call_id"
            config: Runtime config (timeout, etc.)
        
        Returns:
            Structured result with ok/error fields
        """
        arguments = input.get("arguments", {})
        context = input.get("context", {})
        tool_call_id = input.get("tool_call_id")
        
        start_time = time.time()
        
        try:
            # Strict Pydantic validation
            validation_result = self._validate_arguments_strict(arguments)
            if not validation_result["ok"]:
                elapsed_ms = int((time.time() - start_time) * 1000)
                return {
                    "ok": False,
                    "name": self.name,
                    "tool_call_id": tool_call_id,
                    "error": validation_result["error"],
                    "_metadata": {
                        "tool_name": self.name,
                        "elapsed_ms": elapsed_ms
                    }
                }
            
            # Execute tool with validated arguments
            result, _ = self.executor(validation_result["validated_args"])
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            return {
                "ok": True,
                "name": self.name,
                "tool_call_id": tool_call_id,
                "data": result,
                "_metadata": {
                    "tool_name": self.name,
                    "node_model": self.node_model.name if self.node_model else None,
                    "elapsed_ms": elapsed_ms
                }
            }
            
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[ToolRunnable] {self.name} execution error: {e}")
            return {
                "ok": False,
                "name": self.name,
                "tool_call_id": tool_call_id,
                "error": {
                    "type": "ExecutionError",
                    "message": str(e),
                    "details": []
                },
                "_metadata": {
                    "tool_name": self.name,
                    "elapsed_ms": elapsed_ms
                }
            }
    
    def _build_pydantic_validator(self, schema: Dict[str, Any]) -> Optional[type[BaseModel]]:
        """
        Build a Pydantic model from JSON Schema for validation.
        
        Args:
            schema: Tool parameter schema
        
        Returns:
            Pydantic model class or None if schema is empty
        """
        if not schema:
            return None
        
        try:
            fields = {}
            for param_name, param_def in schema.items():
                param_type = param_def.get("type", "string")
                is_required = param_def.get("required", False)
                description = param_def.get("description", "")
                default = param_def.get("default")
                
                # Map JSON Schema types to Python types
                py_type = {
                    "string": str,
                    "number": float,
                    "integer": int,
                    "boolean": bool,
                    "array": list,
                    "object": dict,
                }.get(param_type, str)
                
                # Build field with proper typing
                if is_required and default is None:
                    fields[param_name] = (py_type, Field(..., description=description))
                elif default is not None:
                    fields[param_name] = (py_type, Field(default=default, description=description))
                else:
                    # Optional field with no default
                    from typing import Optional as Opt
                    fields[param_name] = (Opt[py_type], Field(None, description=description))
            
            # Create dynamic Pydantic model
            validator_model = create_model(
                f"{self.name}_Args",
                **fields
            )
            return validator_model
            
        except Exception as e:
            logger.warning(f"[ToolRunnable] Failed to build Pydantic validator for {self.name}: {e}")
            return None
    
    def _validate_arguments_strict(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Strict argument validation using Pydantic.
        
        Args:
            arguments: Arguments to validate
        
        Returns:
            Dict with "ok" and either "validated_args" or "error"
        """
        if not self._validator:
            # No validator, pass through
            return {"ok": True, "validated_args": arguments}
        
        try:
            # Validate using Pydantic model
            validated = self._validator(**arguments)
            # Convert back to dict
            validated_dict = validated.model_dump(exclude_unset=False)
            
            return {
                "ok": True,
                "validated_args": validated_dict
            }
            
        except ValidationError as e:
            # Extract validation errors
            error_details = []
            for err in e.errors():
                error_details.append({
                    "field": ".".join(str(loc) for loc in err["loc"]),
                    "message": err["msg"],
                    "type": err["type"]
                })
            
            return {
                "ok": False,
                "error": {
                    "type": "ValidationError",
                    "message": f"Invalid arguments for {self.name}",
                    "details": error_details
                }
            }
    
    def to_openai_tool_schema(self) -> Dict[str, Any]:
        """
        Convert to OpenAI function calling schema.
        
        Returns:
            OpenAI-compatible tool schema
        """
        properties = {}
        required = []
        
        for param_name, param_schema in self.schema.items():
            properties[param_name] = {
                "type": param_schema.get("type", "string"),
                "description": param_schema.get("description", "")
            }
            if param_schema.get("required", False):
                required.append(param_name)
        
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
    
    def __repr__(self) -> str:
        return f"ToolRunnable(name='{self.name}')"


class ToolCollectionRunnable(BaseLangChainRunnable[Dict[str, Any], Dict[str, Any]]):
    """
    Manages a collection of tools and routes execution.
    
    This is useful for agent-like patterns where you want to:
    1. Present multiple tools to a model
    2. Route tool calls to the correct executor
    3. Handle tool execution errors uniformly
    
    Example:
        tools = ToolCollectionRunnable([
            search_tool,
            calculator_tool,
            database_tool
        ])
        
        # Get all tool schemas for model
        schemas = tools.get_tool_schemas()
        
        # Execute specific tool
        result = tools.invoke({
            "tool_name": "search_database",
            "arguments": {"query": "..."}
        })
    """
    
    def __init__(self, tools: List[ToolRunnable], name: Optional[str] = None):
        """
        Initialize Tool Collection.
        
        Args:
            tools: List of ToolRunnable instances
            name: Optional collection name
        """
        super().__init__(name=name or "ToolCollection")
        self.tools: Dict[str, ToolRunnable] = {t.name: t for t in tools}
    
    def invoke(
        self,
        input: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a specific tool by name.
        
        Args:
            input: Dict with "tool_name" and "arguments"
            config: Runtime config
        
        Returns:
            Structured tool execution result with ok/error fields
        """
        tool_name = input.get("tool_name")
        tool_call_id = input.get("tool_call_id")
        
        if not tool_name:
            return {
                "ok": False,
                "name": "unknown",
                "tool_call_id": tool_call_id,
                "error": {
                    "type": "MissingToolName",
                    "message": "No tool_name provided",
                    "details": []
                }
            }
        
        tool = self.tools.get(tool_name)
        if not tool:
            return {
                "ok": False,
                "name": tool_name,
                "tool_call_id": tool_call_id,
                "error": {
                    "type": "ToolNotFound",
                    "message": f"Tool not found: {tool_name}",
                    "details": [{"available_tools": list(self.tools.keys())}]
                }
            }
        
        return tool.invoke(input, config)
    
    def get_tool_schemas(self, format: str = "openai") -> List[Dict[str, Any]]:
        """
        Get schemas for all tools.
        
        Args:
            format: Schema format ("openai" for now, can add "anthropic", etc.)
        
        Returns:
            List of tool schemas
        """
        if format == "openai":
            return [tool.to_openai_tool_schema() for tool in self.tools.values()]
        else:
            raise ValueError(f"Unsupported schema format: {format}")
    
    def get_tool(self, name: str) -> Optional[ToolRunnable]:
        """Get a specific tool by name"""
        return self.tools.get(name)
    
    def add_tool(self, tool: ToolRunnable) -> None:
        """Add a tool to the collection"""
        self.tools[tool.name] = tool
    
    def remove_tool(self, name: str) -> None:
        """Remove a tool from the collection"""
        self.tools.pop(name, None)
    
    def __repr__(self) -> str:
        tool_names = ", ".join(self.tools.keys())
        return f"ToolCollectionRunnable(tools=[{tool_names}])"


# ============================================================================
# Factory Functions
# ============================================================================

def create_tool_from_executor(
    name: str,
    description: str,
    executor: Callable[[Dict[str, Any]], Tuple[Any, Any]],
    schema: Dict[str, Any],
    node_model: Optional[Any] = None
) -> ToolRunnable:
    """
    Factory function to create a ToolRunnable from an executor.
    
    Args:
        name: Tool name
        description: Tool description
        executor: Execution function
        schema: Parameter schema
        node_model: Optional node model
    
    Returns:
        ToolRunnable instance
    """
    return ToolRunnable(
        name=name,
        description=description,
        executor=executor,
        schema=schema,
        node_model=node_model
    )


def create_tool_collection(tools: List[ToolRunnable]) -> ToolCollectionRunnable:
    """
    Factory function to create a ToolCollectionRunnable.
    
    Args:
        tools: List of tools
    
    Returns:
        ToolCollectionRunnable instance
    """
    return ToolCollectionRunnable(tools)


def convert_n8n_tool_to_runnable(
    tool_schema: Dict[str, Any],
    executor: Callable[[Dict[str, Any]], Tuple[Any, Any]],
    node_model: Optional[Any] = None
) -> ToolRunnable:
    """
    Convert an n8n-style tool schema to a ToolRunnable.
    
    Args:
        tool_schema: n8n tool schema (from prepare_tools)
        executor: Execution callable
        node_model: Optional node model
    
    Returns:
        ToolRunnable instance
    """
    # Extract name and description from n8n schema
    if "function" in tool_schema:
        func = tool_schema["function"]
        name = func.get("name", "unknown")
        description = func.get("description", "")
        parameters = func.get("parameters", {})
        properties = parameters.get("properties", {})
        required = parameters.get("required", [])
        
        # Convert to our schema format
        schema = {}
        for prop_name, prop_def in properties.items():
            schema[prop_name] = {
                "type": prop_def.get("type", "string"),
                "description": prop_def.get("description", ""),
                "required": prop_name in required
            }
    else:
        # Fallback for unknown format
        name = tool_schema.get("name", "unknown")
        description = tool_schema.get("description", "")
        schema = {}
    
    return ToolRunnable(
        name=name,
        description=description,
        executor=executor,
        schema=schema,
        node_model=node_model
    )
