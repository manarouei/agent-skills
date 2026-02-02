"""
MCP (Model Context Protocol) Client Tool Node

This node connects to MCP servers via SSE transport to execute tools and retrieve resources,
making them available to AI agents. It follows the MCP specification for
client-server communication over SSE (Server-Sent Events).

🔒 SECURITY & PERFORMANCE:
==================================

✅ Security:
   - Authentication headers redacted in logs (prevents token leakage to APM/logs)
   - Credential isolation in cache keys (prevents cross-user cache poisoning)

✅ Transport:
   - SSE-only transport for standard MCP servers
   - Shopify-specific transport with password authentication auto-detection
   - Shopify storePassword handling delegated to mcp_transport.py layer

✅ Cache Consistency:
   - Unified 3-tuple format: (timestamp, value, ttl) for all cache entries
   - LRU eviction with per-entry TTL support
   - Metrics tracking: cache hits/misses, connection reuse, tool call success/failure

✅ Blocking Behavior:
   - Following n8n's design: long-running tools block execution synchronously
   - No async/await or gevent - straightforward synchronous HTTP calls
"""

import json
import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from collections import OrderedDict
from threading import Lock

from models import NodeExecutionData
from .base import BaseNode, NodeParameterType

logger = logging.getLogger(__name__)


class McpClientToolNode(BaseNode):
    """
    MCP Client Tool node for connecting to Model Context Protocol servers
    via SSE transport and executing tools/resources as part of AI agent workflows
    """
    
    type = "mcpClientTool"
    version = 1.0
    
    description = {
        "displayName": "MCP Client Tool",
        "name": "mcpClientTool",
        "icon": "file:mcp.svg",
        "group": ["ai"],
        "description": "Connect to MCP servers via SSE to use tools and resources with AI agents",
        "inputs": [{"name": "main", "type": "main", "required": True}],
        "outputs": [
            {"name": "main", "type": "main", "required": True},
            {"name": "ai_tool", "type": "ai_tool", "required": False}
        ],
        "usableAsTool": True
    }
    
    properties = {
        "parameters": [
            {
                "name": "operation",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Operation",
                "options": [
                    {"name": "Execute Tool", "value": "executeTool"},
                    {"name": "List Tools", "value": "listTools"},
                    {"name": "Get Resource", "value": "getResource"},
                    {"name": "List Resources", "value": "listResources"}
                ],
                "default": "executeTool",
                "description": "Operation to perform on the MCP server"
            },
            
            # SSE Configuration
            {
                "name": "url",
                "type": NodeParameterType.STRING,
                "display_name": "SSE Endpoint",
                "default": "",
                "required": True,
                "placeholder": "e.g. https://my-mcp-server.ai/sse",
                "description": "URL of the MCP SSE server endpoint"
            },
            {
                "name": "authentication",
                "type": NodeParameterType.OPTIONS,
                "display_name": "Authentication",
                "options": [
                    {"name": "None", "value": "none"},
                    {"name": "Bearer Auth", "value": "bearerAuth"},
                    {"name": "Header Auth", "value": "headerAuth"}
                ],
                "default": "none",
                "description": "The way to authenticate"
            },
            
            # Tool Execution Parameters
            {
                "name": "toolName",
                "type": NodeParameterType.STRING,
                "display_name": "Tool Name",
                "default": "",
                "required": True,
                "description": "Name of the MCP tool to execute",
                "displayOptions": {"show": {"operation": ["executeTool"]}}
            },
            {
                "name": "toolArguments",
                "type": NodeParameterType.JSON,
                "display_name": "Tool Arguments",
                "default": "{}",
                "description": "JSON object of arguments to pass to the tool",
                "displayOptions": {"show": {"operation": ["executeTool"]}}
            },
            
            # Resource Parameters
            {
                "name": "resourceUri",
                "type": NodeParameterType.STRING,
                "display_name": "Resource URI",
                "default": "",
                "required": True,
                "description": "URI of the resource to retrieve",
                "displayOptions": {"show": {"operation": ["getResource"]}}
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "placeholder": "Add Option",
                "options": [
                    {
                        "name": "timeout",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Timeout (seconds)",
                        "default": 30,
                        "description": "Maximum time to wait for server response"
                    },
                    {
                        "name": "retries",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Max Retries",
                        "default": 3,
                        "description": "Maximum number of retry attempts on failure"
                    },
                    {
                        "name": "cacheResults",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Cache Results",
                        "default": True,
                        "description": "Cache tool/resource results to improve performance"
                    },
                    {
                        "name": "cacheTTL",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Cache TTL (seconds)",
                        "default": 300,
                        "description": "How long to cache results (0 = no caching)",
                        "displayOptions": {
                            "show": {
                                "cacheResults": [True]
                            }
                        }
                    },
                    {
                        "name": "storePassword",
                        "type": NodeParameterType.STRING,
                        "display_name": "Store Password",
                        "default": "",
                        "description": "Password for password-protected Shopify dev stores"
                    }
                ]
            }
        ],
        "credentials": [
            {
                "name": "httpBearerAuth",
                "required": True,
                "displayOptions": {
                    "show": {
                        "authentication": ["bearerAuth"]
                    }
                }
            },
            {
                "name": "httpHeaderAuth",
                "required": True,
                "displayOptions": {
                    "show": {
                        "authentication": ["headerAuth"]
                    }
                }
            }
        ]
    }
    
    icon = "mcp.svg"
    color = "#FF6B6B"
    
    # Class-level cache for server connections and results
    _cache_lock = Lock()
    _server_cache: Dict[str, Tuple[Dict[str, Any], float]] = {}  # (server, created_at)
    _result_cache: OrderedDict[str, Tuple[float, Any, int]] = OrderedDict()

    _cache_ttl_seconds = 300  # 5 minutes
    _max_cache_entries = 1000
    
    _metrics = {
        "cache_hits": 0,
        "cache_misses": 0,
        "connections_created": 0,
        "connections_reused": 0,
        "tool_calls_total": 0,
        "tool_calls_failed": 0,
    }

    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        """Get cache and connection metrics for monitoring"""
        with cls._cache_lock:
            return {
                "active_connections": len(cls._server_cache),
                "cached_results": len(cls._result_cache),
                "cache_max_size": cls._max_cache_entries,
                "cache_utilization_percent": round((len(cls._result_cache) / cls._max_cache_entries) * 100, 2),
                "cache_hits": cls._metrics["cache_hits"],
                "cache_misses": cls._metrics["cache_misses"],
                "cache_hit_rate_percent": round(
                    (cls._metrics["cache_hits"] / (cls._metrics["cache_hits"] + cls._metrics["cache_misses"]) * 100)
                    if (cls._metrics["cache_hits"] + cls._metrics["cache_misses"]) > 0
                    else 0,
                    2
                ),
                "connections_created": cls._metrics["connections_created"],
                "connections_reused": cls._metrics["connections_reused"],
                "tool_calls_total": cls._metrics["tool_calls_total"],
                "tool_calls_failed": cls._metrics["tool_calls_failed"],
                "ttl_seconds": cls._cache_ttl_seconds,
            }

    @classmethod
    def reset_metrics(cls) -> None:
        """Reset metrics (for testing)"""
        cls._metrics = {
            "cache_hits": 0,
            "cache_misses": 0,
            "connections_created": 0,
            "connections_reused": 0,
            "tool_calls_total": 0,
            "tool_calls_failed": 0,
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._current_server = None

    def _get_auth_headers(self, item_index: int = 0) -> Dict[str, str]:
        """
        Get authentication headers based on credentials (mirroring HTTP Request pattern).
        Returns headers dict for SSE transport authentication.
        
        ⚠️ SECURITY: Headers are logged in redacted form to prevent token leakage.
        """
        auth_type = self.get_node_parameter("authentication", item_index, "none")
        headers = {}
        logger.debug(f"MCP Client Tool - Using {auth_type} authentication")
        
        # Setup authentication (exactly like HTTP Request node)
        if auth_type == "bearerAuth":
            creds = self.get_credentials("httpBearerAuth")
            if creds:
                token = creds.get("token", "")
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                    logger.debug("MCP Client Tool - Added Bearer token authentication")
    
        elif auth_type == "headerAuth":
            creds = self.get_credentials("httpHeaderAuth")
            if creds:
                header_name = creds.get("name", "Authorization")
                header_value = creds.get("value", "")
                if header_name and header_value:
                    headers[header_name] = header_value
                    logger.debug(f"MCP Client Tool - Added custom header authentication: {header_name}")
    
        # Always include Content-Type for MCP JSON-RPC
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        
        # ✅ SECURITY FIX: Redact sensitive headers in logs
        safe_headers = {
            k: (v if k.lower() not in {"authorization", "x-api-key", "api-key"} else "***REDACTED***")
            for k, v in headers.items()
        }
        logger.debug(f"MCP Client Tool - Headers (redacted): {safe_headers}")
        return headers

    def execute(self) -> List[List[NodeExecutionData]]:
        """Execute MCP client operations"""
        try:
            items = self.get_input_data()
            if not items:
                return [[]]

            results: List[NodeExecutionData] = []
            
            for i, item in enumerate(items):
                try:
                    operation = self.get_node_parameter("operation", i, "executeTool")
                    
                    # Execute appropriate operation
                    if operation == "executeTool":
                        result = self._execute_tool_operation(i, item)
                    elif operation == "listTools":
                        result = self._list_tools_operation(i)
                    elif operation == "getResource":
                        result = self._get_resource_operation(i)
                    elif operation == "listResources":
                        result = self._list_resources_operation(i)
                    else:
                        raise ValueError(f"Unsupported operation: {operation}")
                    
                    results.append(NodeExecutionData(
                        json_data=result,
                        binary_data=item.binary_data
                    ))
                    
                except Exception as e:
                    logger.error(f"MCP Client Tool - Error processing item {i}: {e}", exc_info=True)
                    results.append(NodeExecutionData(
                        json_data={
                            "error": str(e),
                            "operation": self.get_node_parameter("operation", i, "executeTool"),
                            "item_index": i
                        },
                        binary_data=None
                    ))
            
            return [results]
            
        except Exception as e:
            logger.error(f"MCP Client Tool - Execute error: {e}", exc_info=True)
            return [[NodeExecutionData(
                json_data={"error": f"Error in MCP Client Tool: {str(e)}"},
                binary_data=None
            )]]

    def _execute_tool_operation(self, item_index: int, item: NodeExecutionData) -> Dict[str, Any]:
        """Execute a tool on the MCP server"""
        try:
            self.__class__._metrics["tool_calls_total"] += 1
            
            tool_name = self.get_node_parameter("toolName", item_index, "")
            if not tool_name:
                raise ValueError("Tool name is required")
            
            tool_args_param = self.get_node_parameter("toolArguments", item_index, "{}")
            
            if isinstance(tool_args_param, str):
                try:
                    tool_args = json.loads(tool_args_param)
                except json.JSONDecodeError:
                    tool_args = {}
            else:
                tool_args = tool_args_param or {}
            
            if hasattr(item, 'json_data') and item.json_data:
                for key, value in item.json_data.items():
                    if key not in tool_args and key != "error":
                        tool_args[key] = value
            
            cache_key = self._get_cache_key("tool", tool_name, json.dumps(tool_args, sort_keys=True))
            cached_result = self._get_from_cache(cache_key, item_index)
            if cached_result is not None:
                logger.debug(f"MCP Client Tool - Using cached result for tool: {tool_name}")
                return cached_result
            
            server = self._get_server_connection(item_index)
            result = self._call_mcp_tool(server, tool_name, tool_args, item_index)
            
            response = {
                "tool": tool_name,
                "arguments": tool_args,
                "result": result,
                "status": "success",
                "cached": False
            }
            
            self._store_in_cache(cache_key, response, item_index)
            return response
            
        except Exception as e:
            self.__class__._metrics["tool_calls_failed"] += 1
            logger.error(f"MCP Client Tool - Error executing tool: {e}", exc_info=True)
            return {
                "tool": self.get_node_parameter("toolName", item_index, ""),
                "error": str(e),
                "status": "failed"
            }

    def _list_tools_operation(self, item_index: int) -> Dict[str, Any]:
        """List all available tools from the MCP server"""
        try:
            cache_key = self._get_cache_key("list_tools")
            cached_result = self._get_from_cache(cache_key, item_index)
            if cached_result is not None:
                logger.debug("MCP Client Tool - Using cached tools list")
                return cached_result
            
            server = self._get_server_connection(item_index)
            tools = self._list_mcp_tools(server, item_index)
            
            result = {
                "tools": tools,
                "count": len(tools),
                "status": "success",
                "cached": False
            }
            
            self._store_in_cache(cache_key, result, item_index)
            return result
            
        except Exception as e:
            logger.error(f"MCP Client Tool - Error listing tools: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": "failed"
            }

    def _get_resource_operation(self, item_index: int) -> Dict[str, Any]:
        """Get a resource from the MCP server"""
        try:
            resource_uri = self.get_node_parameter("resourceUri", item_index, "")
            if not resource_uri:
                raise ValueError("Resource URI is required")
            
            cache_key = self._get_cache_key("resource", resource_uri)
            cached_result = self._get_from_cache(cache_key, item_index)
            if cached_result is not None:
                logger.debug(f"MCP Client Tool - Using cached resource: {resource_uri}")
                return cached_result
            
            server = self._get_server_connection(item_index)
            resource = self._get_mcp_resource(server, resource_uri, item_index)
            
            result = {
                "uri": resource_uri,
                "resource": resource,
                "status": "success",
                "cached": False
            }
            
            self._store_in_cache(cache_key, result, item_index)
            return result
            
        except Exception as e:
            logger.error(f"MCP Client Tool - Error getting resource: {e}", exc_info=True)
            return {
                "uri": self.get_node_parameter("resourceUri", item_index, ""),
                "error": str(e),
                "status": "failed"
            }

    def _list_resources_operation(self, item_index: int) -> Dict[str, Any]:
        """List all available resources from the MCP server"""
        try:
            cache_key = self._get_cache_key("list_resources")
            cached_result = self._get_from_cache(cache_key, item_index)
            if cached_result is not None:
                logger.debug("MCP Client Tool - Using cached resources list")
                return cached_result
            
            server = self._get_server_connection(item_index)
            resources = self._list_mcp_resources(server, item_index)
            
            result = {
                "resources": resources,
                "count": len(resources),
                "status": "success",
                "cached": False
            }
            
            self._store_in_cache(cache_key, result, item_index)
            return result
            
        except Exception as e:
            logger.error(f"MCP Client Tool - Error listing resources: {e}", exc_info=True)
            return {
                "error": str(e),
                "status": "failed"
            }

    def _get_server_connection(self, item_index: int) -> Dict[str, Any]:
        """Get or create MCP server connection"""
        url = self.get_node_parameter("url", item_index, "")
        auth_type = self.get_node_parameter("authentication", item_index, "none")
        
        # Include auth type in cache key to handle credential changes
        cache_key = f"server_sse_{url}_{auth_type}"
        
        # Check if connection already exists
        with self._cache_lock:
            if cache_key in self._server_cache:
                server, created_at = self._server_cache[cache_key]
                
                # Check if connection is too old (e.g., 1 hour)
                age = time.time() - created_at
                if age < 3600 and self._is_server_alive(server):
                    logger.debug(f"Reusing connection (age: {age:.1f}s)")
                    self.__class__._metrics["connections_reused"] += 1
                    return server
                else:
                    logger.debug(f"Connection expired or dead (age: {age:.1f}s)")
                    self._cleanup_server(cache_key)
        
        # Create new connection
        logger.debug(f"MCP Client Tool - Creating new server connection: {cache_key}")
        self.__class__._metrics["connections_created"] += 1
        
        server = self._create_sse_server(item_index)
        
        with self._cache_lock:
            self._server_cache[cache_key] = (server, time.time())
            self._current_server = cache_key
        
        return server

    def _create_sse_server(self, item_index: int) -> Dict[str, Any]:
        """
        Create SSE-based MCP server connection with authentication.
        
        Note: Shopify password handling is delegated to mcp_transport.py layer.
        """
        try:
            from utils.mcp_transport import create_sse_transport
            
            url = self.get_node_parameter("url", item_index, "")
            if not url:
                raise ValueError("SSE Endpoint is required")
            
            headers = self._get_auth_headers(item_index)
            options = self.get_node_parameter("options", item_index, {})
            store_password = options.get("storePassword")
            timeout = options.get("timeout", 30)

            logger.debug(f"MCP Client Tool - Connecting to SSE server: {url}")

            # Use transport factory (auto-detects Shopify vs generic)
            transport = create_sse_transport(
                url=url,
                headers=headers,
                store_password=store_password,
                timeout=timeout
            )
            
            return {
                "type": "sse",
                "url": url,
                "transport": transport
            }
            
        except Exception as e:
            logger.error(f"MCP Client Tool - Error creating SSE server: {e}", exc_info=True)
            raise ValueError(f"Failed to create SSE server: {str(e)}")

    def _call_mcp_tool(self, server: Dict[str, Any], tool_name: str, arguments: Dict[str, Any], item_index: int) -> Any:
        """Call tool via SSE transport"""
        try:
            transport = server["transport"]
            result = transport.send_request("tools/call", {
                "name": tool_name,
                "arguments": arguments
            })
            return result.get("result", {})
        except Exception as e:
            logger.error(f"MCP Client Tool - Error calling tool: {e}", exc_info=True)
            raise

    def _list_mcp_tools(self, server: Dict[str, Any], item_index: int) -> List[Dict[str, Any]]:
        """List tools via SSE transport"""
        try:
            transport = server["transport"]
            result = transport.send_request("tools/list", {})
            return result.get("result", {}).get("tools", [])
        except Exception as e:
            logger.error(f"MCP Client Tool - Error listing tools: {e}", exc_info=True)
            raise

    def _get_mcp_resource(self, server: Dict[str, Any], uri: str, item_index: int) -> Any:
        """Get resource via SSE transport"""
        try:
            transport = server["transport"]
            result = transport.send_request("resources/read", {"uri": uri})
            return result.get("result", {})
        except Exception as e:
            logger.error(f"MCP Client Tool - Error getting resource: {e}", exc_info=True)
            raise

    def _list_mcp_resources(self, server: Dict[str, Any], item_index: int) -> List[Dict[str, Any]]:
        """List resources via SSE transport"""
        try:
            transport = server["transport"]
            result = transport.send_request("resources/list", {})
            return result.get("result", {}).get("resources", [])
        except Exception as e:
            logger.error(f"MCP Client Tool - Error listing resources: {e}", exc_info=True)
            raise

    def _cleanup_server(self, cache_key: str) -> None:
        """Clean up a specific server connection"""
        try:
            if cache_key not in self._server_cache:
                return
            
            server = self._server_cache[cache_key]
            
            # Close SSE transport
            transport = server.get("transport")
            if transport and hasattr(transport, "close"):
                transport.close()
            
            del self._server_cache[cache_key]
            logger.debug(f"MCP Client Tool - Cleaned up server: {cache_key}")
            
        except Exception as e:
            logger.error(f"MCP Client Tool - Error cleaning up server {cache_key}: {e}")

    def _is_server_alive(self, server: Dict[str, Any]) -> bool:
        """Check if server connection is still alive"""
        try:
            transport = server.get("transport")
            return transport is not None and transport.is_alive()
        except Exception:
            return False

    def _get_cache_key(self, operation: str, *parts) -> str:
        """Generate cache key including credentials hash for isolation"""
        item_index = 0  # Default to first item for cache key generation
        auth_type = self.get_node_parameter("authentication", item_index, "none")
        
        key_parts = [operation] + list(parts)
        
        # Add credential hash for isolation between users
        if auth_type == "bearerAuth":
            creds = self.get_credentials("httpBearerAuth")
            if creds:
                token = creds.get("token", "")
                key_parts.append(f"auth_{hash(token)}")
        elif auth_type == "headerAuth":
            creds = self.get_credentials("httpHeaderAuth")
            if creds:
                header_val = creds.get("value", "")
                key_parts.append(f"auth_{hash(header_val)}")
        
        return "_".join(str(p) for p in key_parts)

    def _get_from_cache(self, key: str, item_index: int) -> Optional[Any]:
        """Get value from cache if not expired"""
        options = self.get_node_parameter("options", item_index, {})
        if not options.get("cacheResults", True):
            return None

        with self._cache_lock:
            if key not in self._result_cache:
                self.__class__._metrics["cache_misses"] += 1
                return None
            
            timestamp, value, stored_ttl = self._result_cache[key]
            age = time.time() - timestamp
            
            if age > stored_ttl:
                del self._result_cache[key]
                logger.debug(f"Cache expired for key: {key[:50]}... (age: {age:.1f}s, ttl: {stored_ttl}s)")
                self.__class__._metrics["cache_misses"] += 1
                return None
            
            # Move to end (LRU ordering)
            self._result_cache.move_to_end(key)
            
            self.__class__._metrics["cache_hits"] += 1
            logger.debug(f"Cache hit for key: {key[:50]}... (age: {age:.1f}s)")
            
            if isinstance(value, dict):
                result = value.copy()
                result["cached"] = True
                result["cache_age_seconds"] = int(age)
                return result
            return value
    
    def _store_in_cache(self, key: str, value: Any, item_index: int) -> None:
        """Store value in cache with timestamp and TTL"""
        options = self.get_node_parameter("options", item_index, {})
        if not options.get("cacheResults", True):
            return
        
        cache_ttl = options.get("cacheTTL", self._cache_ttl_seconds)
        if cache_ttl <= 0:
            return
        
        with self._cache_lock:
            if len(self._result_cache) >= self._max_cache_entries:
                if key not in self._result_cache:
                    oldest_key = next(iter(self._result_cache))
                    del self._result_cache[oldest_key]
        
            # Store with TTL (3-tuple)
            self._result_cache[key] = (time.time(), value, cache_ttl)
            logger.debug(f"Cached: {key[:50]}... (ttl={cache_ttl}s)")

