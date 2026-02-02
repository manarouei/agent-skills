"""
MCP Tool Response Handler

Generic handler for processing and integrating MCP server responses with AI Agent workflow.
Works with ANY MCP server (Shopify, Filesystem, GitHub, Brave Search, etc.)
"""

import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


class MCPToolHandler:
    """
    Generic MCP tool response handler that works with any MCP server.
    
    Responsibilities:
    - Parse MCP tool responses (generic format)
    - Track tool call state
    - Format responses for AI Agent consumption
    - Handle MCP-specific error cases
    - NO server-specific logic (Shopify, etc.)
    """
    
    def __init__(self, agent_node):
        """
        Initialize MCP handler with reference to AI Agent node.
        
        Args:
            agent_node: Reference to AIAgentNode instance
        """
        self.agent = agent_node
        self._tool_call_history: List[Dict[str, Any]] = []
    
    def process_mcp_tool_response(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        raw_response: Dict[str, Any],
        item_index: int
    ) -> Dict[str, Any]:
        """
        Process raw MCP tool response and format for AI Agent.
        
        This is GENERIC - works with any MCP server response format.
        
        Args:
            tool_name: Name of the MCP tool that was called
            tool_args: Arguments passed to the tool
            raw_response: Raw response from MCP tool node
            item_index: Current item index in workflow
            
        Returns:
            Processed response dict ready for AI Agent consumption
        """
        try:
            # Track this tool call
            self._track_tool_call(tool_name, tool_args, raw_response)
            
            # Handle different MCP standard response types
            if self._is_error_response(raw_response):
                return self._format_error_response(tool_name, raw_response)
            
            if self._is_list_tools_response(raw_response):
                return self._format_list_tools_response(raw_response)
            
            if self._is_tool_execution_response(raw_response):
                return self._format_tool_execution_response(tool_name, raw_response)
            
            # Default: pass through as-is (let AI model interpret)
            logger.debug(f"[MCP Handler] Generic response for {tool_name}, passing through")
            return self._format_generic_response(tool_name, raw_response)
            
        except Exception as e:
            logger.error(f"[MCP Handler] Error processing tool response: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return {
                "error": f"Failed to process MCP response: {str(e)}",
                "tool": tool_name,
                "status": "processing_error"
            }
    
    def prepare_tool_call_for_mcp(
        self,
        tool_name: str,
        agent_args: Dict[str, Any]
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Prepare AI Agent's tool call for MCP server.
        
        Generic preparation that works with any MCP server.
        
        Args:
            tool_name: Tool name from AI Agent
            agent_args: Arguments from AI Agent
            
        Returns:
            Tuple of (mcp_tool_name, mcp_args)
        """
        # Extract actual MCP tool name if wrapped
        mcp_tool_name = self._extract_mcp_tool_name(tool_name, agent_args)
        
        # Convert agent args to MCP format (generic)
        mcp_args = self._convert_agent_args_to_mcp(agent_args)
        
        logger.debug(f"[MCP Handler] Prepared tool call: {mcp_tool_name} with args: {list(mcp_args.keys())}")
        
        return mcp_tool_name, mcp_args
    
    def format_tool_list_for_agent(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Format MCP tools list for AI Agent consumption.
        
        Converts MCP tool schema format to AI Agent's expected format.
        This follows MCP standard tool schema format.
        """
        formatted_tools = []
        
        for tool in tools:
            try:
                formatted = {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": self._convert_mcp_schema_to_agent_schema(
                        tool.get("inputSchema", {})
                    )
                }
                formatted_tools.append(formatted)
            except Exception as e:
                logger.warning(f"[MCP Handler] Failed to format tool {tool.get('name')}: {e}")
                continue
        
        return formatted_tools
    
    def get_tool_call_history(self) -> List[Dict[str, Any]]:
        """Get history of all tool calls in this session."""
        return self._tool_call_history.copy()
    
    def clear_tool_call_history(self) -> None:
        """Clear tool call history."""
        self._tool_call_history.clear()
    
    # Private helper methods
    
    def _track_tool_call(
        self,
        tool_name: str,
        args: Dict[str, Any],
        response: Dict[str, Any]
    ) -> None:
        """Track a tool call for debugging and state management."""
        self._tool_call_history.append({
            "tool": tool_name,
            "args": args,
            "response": response,
            "success": not self._is_error_response(response)
        })
    
    def _is_error_response(self, response: Dict[str, Any]) -> bool:
        """
        Check if response indicates an error.
        
        MCP standard: errors have "error" field or status "failed"
        """
        return (
            "error" in response or
            response.get("status") == "failed" or
            "MCP error" in str(response.get("error", ""))
        )
    
    def _is_list_tools_response(self, response: Dict[str, Any]) -> bool:
        """
        Check if response is a tools list.
        
        MCP standard: listTools returns {"tools": [...]}
        """
        return "tools" in response and isinstance(response["tools"], list)
    
    def _is_tool_execution_response(self, response: Dict[str, Any]) -> bool:
        """
        Check if response is from tool execution.
        
        MCP standard: tool responses have "result" or "content" field
        """
        return "result" in response or "content" in response
    
    def _format_error_response(
        self,
        tool_name: str,
        response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format error response for AI Agent."""
        return {
            "tool": tool_name,
            "error": response.get("error", "Unknown error"),
            "status": "failed",
            "details": response
        }
    
    def _format_list_tools_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """Format tools list response."""
        tools = response.get("tools", [])
        return {
            "tools": self.format_tool_list_for_agent(tools),
            "count": len(tools),
            "status": "success"
        }
    
    def _format_tool_execution_response(
        self,
        tool_name: str,
        response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format tool execution response.
        
        MCP standard: extract from "result" or "content" field
        """
        # Extract result from various possible locations
        result = (
            response.get("result") or
            response.get("content") or
            response.get("output") or
            response
        )
        
        return {
            "tool": tool_name,
            "result": result,
            "status": "success",
            "cached": response.get("cached", False)
        }
    
    def _format_generic_response(
        self,
        tool_name: str,
        response: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Format generic response when format is unknown.
        
        Pass through as-is, let the AI model interpret it.
        """
        return {
            "tool": tool_name,
            "result": response,
            "status": "success"
        }
    
    def _convert_mcp_schema_to_agent_schema(
        self,
        mcp_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert MCP input schema to AI Agent's parameter format.
        
        MCP uses JSON Schema format (standard), which is also what OpenAI uses.
        So this is mostly pass-through with validation.
        """
        # If already in correct format, return as-is
        if "type" in mcp_schema and "properties" in mcp_schema:
            return mcp_schema
        
        # If missing type, assume object
        if "properties" in mcp_schema:
            return {
                "type": "object",
                "properties": mcp_schema.get("properties", {}),
                "required": mcp_schema.get("required", [])
            }
        
        # Fallback: empty object schema
        return {
            "type": "object",
            "properties": {},
            "required": []
        }
    
    def _extract_mcp_tool_name(
        self,
        tool_name: str,
        args: Dict[str, Any]
    ) -> str:
        """
        Extract actual MCP tool name from agent's tool call.
        
        Generic extraction that works with any MCP server.
        """
        # Priority 1: explicit toolName in args (from MCP node config)
        if "toolName" in args and args["toolName"]:
            return args["toolName"]
        
        # Priority 2: use the tool_name as-is
        return tool_name
    
    def _convert_agent_args_to_mcp(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert AI Agent arguments to MCP format.
        
        Generic conversion: removes MCP node metadata, extracts actual tool args.
        """
        # Parameters that are for MCP node infrastructure, not the tool itself
        mcp_node_params = {
            "nodeType", "operation", "transport", "command",
            "args", "env", "url", "headers", "toolName",
            "toolArguments", "resourceUri", "options"
        }
        
        # Priority 1: Extract from toolArguments if present
        if "toolArguments" in args:
            tool_args = args["toolArguments"]
            
            # Parse if it's a JSON string
            if isinstance(tool_args, str):
                import json
                try:
                    tool_args = json.loads(tool_args)
                except json.JSONDecodeError:
                    logger.warning("[MCP Handler] Failed to parse toolArguments JSON")
                    tool_args = {}
            
            # Ensure it's a dict
            if not isinstance(tool_args, dict):
                tool_args = {}
            
            return tool_args
        
        # Priority 2: Filter out MCP node parameters, use the rest
        filtered = {
            k: v for k, v in args.items()
            if k not in mcp_node_params
        }
        
        return filtered


def create_mcp_handler(agent_node) -> MCPToolHandler:
    """
    Factory function to create MCP handler.
    
    Args:
        agent_node: AIAgentNode instance
        
    Returns:
        MCPToolHandler instance (generic, works with any MCP server)
    """
    return MCPToolHandler(agent_node)