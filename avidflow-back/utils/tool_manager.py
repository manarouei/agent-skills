from typing import Any, Dict, List, Callable, Tuple, Optional
from models import Node as NodeModel

from .ai_agent_tool_ops import (
    prepare_tools as _prepare_tools_util,
    handle_model_tool_calls as _handle_model_tool_calls_util,
    maybe_autocall_single_tool as _maybe_autocall_single_tool_util,
    deliver_via_text_tool as _deliver_via_text_tool_util,
)
from .tool_runner import execute_tool as _execute_tool_util

class ToolManager:
    """
    Thin manager around existing tool utils to centralize prepare/execute/persist logic.
    Now returns LangChain-compatible ToolRunnable instances.
    
    Supports both production and LCEL execution paths with unified signature.
    """

    def __init__(self, agent: Any):
        self.agent = agent

    def prepare(
        self, 
        tool_nodes=None,  # Legacy parameter (production path)
        node_definitions=None,  # Legacy parameter (production path)
        item_index: int = 0,  # NEW parameter (LCEL path)
        upstream_tool_nodes=None  # NEW parameter (LCEL path)
    ):
        """
        Prepare tools and return as LangChain-compatible ToolRunnable instances.
        
        UNIFIED SIGNATURE: Supports both production and LCEL paths.
        
        Args:
            tool_nodes: Tool node models (production path - positional)
            node_definitions: Node definitions registry (production path)
            item_index: Item index for parameter resolution (LCEL path)
            upstream_tool_nodes: Alternative to tool_nodes (LCEL path)
        
        Usage:
            # Production path (backward compatible)
            tools = tool_manager.prepare(tool_nodes)
            
            # LCEL path (new signature)
            tools = tool_manager.prepare(
                item_index=0,
                upstream_tool_nodes=tool_nodes
            )
        
        Returns:
            List[ToolRunnable]: Tools wrapped as Runnables for LCEL composition
        """
        # Use upstream_tool_nodes if provided, else tool_nodes
        nodes = upstream_tool_nodes if upstream_tool_nodes is not None else tool_nodes
        
        if not nodes:
            return []
        
        # Import here to avoid circular imports
        from .langchain_tools import ToolRunnable, create_tool_from_executor
        
        # Get raw tool data from existing util
        tool_schemas, executors, param_schemas = _prepare_tools_util(
            self.agent, nodes, node_definitions=node_definitions
        )
        
        # Convert to ToolRunnable instances
        import logging
        logger = logging.getLogger(__name__)
        
        runnables = []
        for tool_schema in tool_schemas:
            func_def = tool_schema.get("function", {})
            name = func_def.get("name", "")
            description = func_def.get("description", "")
            params = func_def.get("parameters", {"type": "object", "properties": {}})
            
            # Get the executor for this tool
            func_key = name.lower()
            raw_executor = executors.get(func_key)
            
            if raw_executor:
                # Wrap the raw executor to match ToolRunnable signature
                def create_wrapped_executor(node_cls_getter, schema):
                    def wrapped(args: Dict[str, Any]) -> Tuple[Any, Any]:
                        # node_cls_getter returns (node_class, node_model)
                        node_cls, node_model = node_cls_getter()
                        result = self.execute_tool(
                            node_cls, node_model, args, expr_json=schema
                        )
                        # execute_tool returns a single dict, not a tuple
                        return result, node_model
                    return wrapped
                
                executor_func = create_wrapped_executor(raw_executor, params)
                
                # Convert OpenAI schema to ToolRunnable internal format
                # OpenAI format has "required" as array at parameters level
                # ToolRunnable expects "required" flag per property
                properties = params.get("properties", {})
                required_fields = params.get("required", [])
                
                # Build schema with per-field required flags
                internal_schema = {}
                for prop_name, prop_def in properties.items():
                    internal_schema[prop_name] = {
                        **prop_def,
                        "required": prop_name in required_fields
                    }
                
                # Create ToolRunnable
                tool_runnable = create_tool_from_executor(
                    name=name,
                    description=description,
                    executor=executor_func,
                    schema=internal_schema
                )
                runnables.append(tool_runnable)
        
        return runnables

    def _is_mcp_tool(self, node_model) -> bool:
        """Check if a tool node is an MCP client."""
        return node_model.type == "mcpClientTool"

    def execute_tool(self, node_cls, node_model, args, expr_json: Optional[Dict[str, Any]] = None):
        return _execute_tool_util(self.agent, node_cls, node_model, args, expr_json=expr_json)


    def _handle_mcp_tool_response(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        raw_response: Dict[str, Any],
        item_index: int
    ) -> Dict[str, Any]:
        """Process MCP tool response using MCP handler."""
        return self.agent.mcp_handler.process_mcp_tool_response(
            tool_name, tool_args, raw_response, item_index
        )

    def handle_model_tool_calls(
        self,
        tool_calls: List[Dict[str, Any]],
        executors: Dict[str, Callable[[], Tuple[Any, NodeModel]]],
        tool_param_schemas: Dict[str, Dict[str, Any]],
        messages: List[Dict[str, Any]],
        intermediate: List[Dict[str, Any]],
        assistant_text: str,
        user_query: str,
    ) -> None:
        return _handle_model_tool_calls_util(
            self.agent, tool_calls, executors, tool_param_schemas,
            messages, intermediate, assistant_text, user_query
        )

    def maybe_autocall_single_tool(
        self,
        tools: List[Dict[str, Any]],
        tool_param_schemas: Dict[str, Dict[str, Any]],
        executors: Dict[str, Callable[[], Tuple[Any, NodeModel]]],
        user_input: str,
        messages: List[Dict[str, Any]],
        intermediate: List[Dict[str, Any]],
        assistant_text: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        return _maybe_autocall_single_tool_util(
            self.agent, tools, tool_param_schemas, executors,
            user_input, messages, intermediate, assistant_text
        )

    def deliver_via_text_tool(
        self,
        tools: List[Dict[str, Any]],
        executors: Dict[str, Callable[[], Tuple[Any, NodeModel]]],
        tool_param_schemas: Dict[str, Dict[str, Any]],
        messages: List[Dict[str, Any]],
        intermediate: List[Dict[str, Any]],
        final_text: str,
    ) -> Optional[Dict[str, Any]]:
        return _deliver_via_text_tool_util(
            self.agent, tools, executors, tool_param_schemas, messages, intermediate, final_text
        )

