from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, Callable
import logging, json, time
from datetime import datetime
from config import settings

from database.config import get_sync_session_manual
from models import NodeExecutionData, Node as NodeModel
from nodes.base import BaseNode, NodeParameterType
from nodes.memory.buffer_memory import MemoryManager
from utils.model_registry import ModelRegistry
from services.queue import QueueService

from utils.connection_resolver import ConnectionResolver

# LangChain Runnable integration
from utils.langchain_agents import AgentRunnable
from utils.langchain_base import RunnableRegistry

from utils.ai_agent_args import (
    coerce_primitive as _coerce_primitive_utils,
    validate_and_coerce_args as _validate_and_coerce_args_utils,
    clean_tool_args as _clean_tool_args,  # NEW
)
from utils.ai_agent_text import (
    smart_truncate as _smart_truncate_utils,
    stringify_item as _stringify_item_utils,
    select_relevant_items as _select_relevant_items_utils,
)
from utils.ai_agent_tool_ops import process_tool_response as _process_tool_response
from utils.ai_agent_tooling import (
    classify_tools as _classify_tools_utils,
    tool_instruction as _tool_instruction_utils,
)

from utils.common_params import normalize_parameters as _normalize_parameters
from utils.retry import retry_call as _retry_call, is_transient_exc as _is_transient_exc
from utils.node_loader import (
    coerce_node_definitions_mapping as _coerce_node_defs_map,
    dyn_import_node_class_from_type as _dyn_import_node_cls,
    resolve_node_definitions as _resolve_node_defs,
)
from utils.execution_data import get_execution_data_ref as _get_exec_ref, persist_provider_snapshot as _persist_provider_snap
from utils.inline_exec import run_node_inline as _run_node_inline
from utils.tool_runner import execute_tool as _execute_tool_util
from utils.llm_messages import (
    messages_for_memory as _messages_for_memory_util,
    build_initial_messages as _build_initial_messages_util,
    assistant_with_tool_calls_message as _assistant_with_tool_calls_message_util,
)


from utils.provider_meta import build_providers_meta as _build_providers_meta_util
from utils.tool_manager import ToolManager
from utils.mcp_handler import create_mcp_handler, MCPToolHandler


logger = logging.getLogger(__name__)


class _AgentEventPublisher:
    """
    Publisher mixin for standardized agent events to workflow_updates queue.
    
    ╔══════════════════════════════════════════════════════════════════════════════╗
    ║ RABBITMQ USAGE: ZERO CUSTOM EVENTS (Matches All Other Nodes)                ║
    ║                                                                              ║
    ║ The AI Agent now behaves EXACTLY like Bale, HTTP Request, Qdrant, etc.:     ║
    ║   ✓ Executes silently (no custom event publishing)                          ║
    ║   ✓ Returns results via standard return statement                           ║
    ║   ✓ Execution engine publishes standard "node_completed" event              ║
    ║   ✓ Execution engine publishes standard "node_error" on exceptions          ║
    ║                                                                              ║
    ║ ALL CUSTOM AGENT EVENTS REMOVED (100+ messages eliminated):                 ║
    ║   ✗ agent_started - REMOVED                                                 ║
    ║   ✗ agent_completed - REMOVED (executor publishes node_completed)           ║
    ║   ✗ agent_error - REMOVED (executor publishes node_error)                   ║
    ║   ✗ agent_step - REMOVED (2-5× per execution)                               ║
    ║   ✗ tool_called - REMOVED (30× in production workflow)                      ║
    ║   ✗ tool_result - REMOVED (30× in production workflow)                      ║
    ║   ✗ model_result - REMOVED (5-10× per execution)                            ║
    ║   ✗ memory_result - REMOVED (2× per execution)                              ║
    ║   ✗ Shadow nodes - REMOVED (30+ messages per execution)                     ║
    ║                                                                              ║
    ║ PRODUCTION IMPACT:                                                           ║
    ║   Before: ~100 custom AI Agent events per execution                         ║
    ║   After:  0 custom events (executor publishes 1 node_completed)             ║
    ║                                                                              ║
    ║ NOTE: _AgentEventPublisher class kept for backward compatibility but        ║
    ║       all methods are unused. AI Agent is now a standard node.              ║
    ╚══════════════════════════════════════════════════════════════════════════════╝
    
    All events follow the standard envelope:
    {
        "event": "<event_name>",
        "workflow_id": "<workflow_id>",
        "execution_id": "<execution_id>",
        "ts": "<ISO-8601 timestamp>",
        ...additional fields...
    }
    """
    
    workflow_id: str
    execution_id: str
    pub_sub: bool
    queue: Optional[QueueService]
    _seq: int
    
    def _init_publisher(self, workflow_id: str, execution_id: str, pub_sub: bool) -> None:
        """Initialize the event publisher"""
        self.workflow_id = workflow_id
        self.execution_id = execution_id
        self.pub_sub = pub_sub
        self.queue = QueueService() if self.pub_sub else None
        self._seq = 0
    
    def _publish(self, payload: Dict[str, Any]) -> None:
        """
        Publish event to workflow_updates queue with standard envelope.
        
        Args:
            payload: Event payload (must include 'event' key)
        """
        if not self.pub_sub or not self.queue:
            return
        
        # Ensure standard envelope fields
        payload.setdefault("workflow_id", self.workflow_id)
        payload.setdefault("execution_id", self.execution_id)
        payload.setdefault("ts", datetime.utcnow().isoformat())
        
        # Add sequence number for agent_step events
        if payload.get("event") == "agent_step":
            self._seq = getattr(self, "_seq", 0) + 1
            payload.setdefault("seq", self._seq)
        
        # Sanitize and truncate payload
        payload = self._sanitize_payload(payload)
        
        try:
            self.queue.publish_sync(queue_name="workflow_updates", message=payload)
            logger.debug(f"[AgentPublisher] Published {payload.get('event')} event")
        except Exception as e:
            logger.warning(f"[AgentPublisher] Failed to publish event: {e}")
    
    def _sanitize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize payload: truncate large fields, redact secrets.
        
        Enforces 10-50KB safety limit on result fields.
        
        Args:
            payload: Raw event payload
            
        Returns:
            Sanitized payload
        """
        MAX_FIELD_SIZE = 50 * 1024  # 50KB
        REDACT_KEYS = {"password", "token", "secret", "api_key", "apikey", "authorization", "credential"}
        
        def truncate_value(v: Any, key: str = "") -> Any:
            """Recursively truncate/redact values"""
            # Redact secrets
            if key.lower() in REDACT_KEYS:
                return "***REDACTED***"
            
            # Truncate strings
            if isinstance(v, str):
                if len(v) > MAX_FIELD_SIZE:
                    return v[:MAX_FIELD_SIZE] + f"... [truncated {len(v) - MAX_FIELD_SIZE} chars]"
                return v
            
            # Recursively handle dicts
            if isinstance(v, dict):
                return {k: truncate_value(val, k) for k, val in v.items()}
            
            # Recursively handle lists (limit length too)
            if isinstance(v, list):
                if len(v) > 100:
                    return [truncate_value(item) for item in v[:100]] + [f"... [truncated {len(v) - 100} items]"]
                return [truncate_value(item) for item in v]
            
            return v
        
        return truncate_value(payload)
    
    def _agent_started(self, model: str, tools_count: int = 0) -> None:
        """Publish agent_started event"""
        self._publish({
            "event": "agent_started",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "data": {
                "model": model,
                "tools_count": tools_count,
            }
        })
    
    def _agent_step(self, delta: str, iteration: int = 0) -> None:
        """Publish agent_step event (for streaming/progress updates)"""
        self._publish({
            "event": "agent_step",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "data": {
                "delta": delta,
                "iteration": iteration,
            }
        })
    
    def _tool_called(self, tool_name: str, args: Dict[str, Any]) -> None:
        """Publish tool_called event"""
        self._publish({
            "event": "tool_called",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "tool_name": tool_name,
            "tool_args": args,
        })
    
    def _tool_result(self, tool_name: str, result: Any, success: bool = True, error: Optional[str] = None) -> None:
        """Publish tool_result event"""
        self._publish({
            "event": "tool_result",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "tool_name": tool_name,
            "result": result,
            "success": success,
            "error": error,
        })
    
    def _model_result(self, usage: Optional[Dict[str, Any]] = None, preview: Optional[str] = None) -> None:
        """Publish model_result event"""
        self._publish({
            "event": "model_result",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "data": {
                "usage": usage,
                "preview": preview,
            }
        })
    
    def _memory_result(self, operation: str, status: str, meta: Optional[Dict[str, Any]] = None) -> None:
        """Publish memory_result event"""
        self._publish({
            "event": "memory_result",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "data": {
                "operation": operation,
                "status": status,
                "meta": meta,
            }
        })
    
    def _agent_completed(self, final_preview: Optional[str] = None, summary: Optional[Dict[str, Any]] = None) -> None:
        """
        Publish agent_completed event.
        
        ╔══════════════════════════════════════════════════════════════════════════════╗
        ║ RABBITMQ USAGE: agent_completed event (PRIMARY & REQUIRED)                  ║
        ║                                                                              ║
        ║ THIS IS THE ONLY REGULAR EVENT PUBLISHED BY AI AGENT                        ║
        ║                                                                              ║
        ║ PURPOSE: Delivers final agent output to WebSocket clients                   ║
        ║ FREQUENCY: Exactly 1 message per execution                                  ║
        ║ PAYLOAD: Final text response + execution summary (iterations, tokens, etc.) ║
        ║                                                                              ║
        ║ This is REQUIRED because:                                                    ║
        ║   1. WebSocket clients wait for this to display results to users            ║
        ║   2. Contains the actual AI response that users asked for                   ║
        ║   3. Without this, the entire workflow execution appears to "hang"          ║
        ║                                                                              ║
        ║ OPTIMIZATION: All intermediate events (tool_called, agent_step, etc.)       ║
        ║               have been disabled to reduce load from 100+ to 1 message      ║
        ╚══════════════════════════════════════════════════════════════════════════════╝
        """
        self._publish({
            "event": "agent_completed",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "data": {
                "final_preview": final_preview,
                "summary": summary,
            }
        })
    
    def _agent_error(self, message: str, details: Optional[Dict[str, Any]] = None, fatal: bool = False) -> None:
        """
        Publish agent_error event (non-terminal by default).
        
        ╔══════════════════════════════════════════════════════════════════════════════╗
        ║ RABBITMQ USAGE: agent_error event (KEPT ENABLED)                            ║
        ║                                                                              ║
        ║ REASON: Critical failures need to be communicated to UI immediately          ║
        ║ FREQUENCY: Rare (only on exceptions, timeouts, or fatal errors)             ║
        ║ IMPACT: ~0-2 messages per execution (only when errors occur)                ║
        ║                                                                              ║
        ║ This is JUSTIFIED because:                                                   ║
        ║   1. Users need to know when agent execution fails                          ║
        ║   2. Errors are infrequent (not every execution)                            ║
        ║   3. Without this, users would wait indefinitely for failed executions      ║
        ╚══════════════════════════════════════════════════════════════════════════════╝
        
        Agent errors don't close the WebSocket - only workflow-level terminal events do.
        
        Args:
            message: Error message
            details: Additional error context
            fatal: If True, marks error as workflow-fatal (rare)
        """
        self._publish({
            "event": "agent_error",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "data": {
                "error": message,
                "details": details,
                "fatal": fatal,
            }
        })
    
    def _agent_step(self, delta: str, iteration: int = 0) -> None:
        """
        Publish agent_step event (streamed deltas).
        
        Args:
            delta: Step content (text delta, reasoning update, etc.)
            iteration: Current iteration number
        """
        self._publish({
            "event": "agent_step",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "delta": delta,
            "iteration": iteration,
        })
    
    def _tool_called(self, tool_name: str, args: Dict[str, Any]) -> None:
        """Publish tool_called event"""
        self._publish({
            "event": "tool_called",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "tool_name": tool_name,
            "tool_args": args,
        })
    
    def _tool_result(self, tool_name: str, result: Any, success: bool = True, error: Optional[str] = None) -> None:
        """Publish tool_result event"""
        self._publish({
            "event": "tool_result",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "tool_name": tool_name,
            "result": result,
            "success": success,
            "error": error,
        })
    
    def _model_result(self, usage: Optional[Dict[str, Any]] = None, preview: Optional[str] = None) -> None:
        """Publish model_result event"""
        self._publish({
            "event": "model_result",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "usage": usage,
            "preview": preview,
        })
    
    def _memory_result(self, operation: str, status: str, meta: Optional[Dict[str, Any]] = None) -> None:
        """Publish memory_result event"""
        self._publish({
            "event": "memory_result",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "operation": operation,
            "status": status,
            "meta": meta,
        })
    
    def _agent_completed(self, final_preview: Optional[str] = None, summary: Optional[Dict[str, Any]] = None) -> None:
        """Publish agent_completed event"""
        self._publish({
            "event": "agent_completed",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "final_preview": final_preview,
            "summary": summary,
        })
    
    def _agent_error(self, message: str, details: Optional[Dict[str, Any]] = None, fatal: bool = False) -> None:
        """
        Publish agent_error event (non-terminal by default).
        
        Agent errors don't close the WebSocket - only workflow-level terminal events do.
        
        Args:
            message: Error message
            details: Additional error context
            fatal: If True, marks error as workflow-fatal (rare)
        """
        self._publish({
            "event": "agent_error",
            "node_name": getattr(self, "node_data", None) and self.node_data.name or "AI Agent",
            "error": message,
            "details": details,
            "fatal": fatal,
        })


class AIAgentNode(BaseNode, _AgentEventPublisher):
    """AI Agent node that orchestrates chat models, tools, and memory (n8n-style lazy provider execution)"""

    type = "ai_agent"
    version = 1

    # --- KEEP EXACT (description / properties) ---
    description = {
        "displayName": "AI Agent",
        "name": "ai_agent",
        "icon": "file:robot.svg",
        "group": ["ai"],
        "description": "AI agent that can use tools and maintain conversation context",
        "defaults": {"name": "AI Agent"},
        "inputs": [
            {"name": "main", "type": "main", "required": True},
            {"name": "ai_model", "type": "ai_languageModel", "required": True},
            {"name": "ai_tool", "type": "ai_tool", "required": False, "maxConnections": 10},
            {"name": "ai_memory", "type": "ai_memory", "required": False},
        ],
        "outputs": [{"name": "main", "type": "main", "required": True}],
    }
    properties = {
        "parameters": [
            {
                "name": "promptType",
                "type": NodeParameterType.OPTIONS,
                "display_name": "User Message Source",
                "options": [
                    {"name": "Connected Chat Trigger Node", "value": "userInput"},
                    {"name": "Define below", "value": "define"}
                    
                ],
                "default": "userInput"
            },
            {
                "name": "userInputExpression",
                "type": NodeParameterType.STRING,
                "display_name": "Prompt (User Message)",
                "default": "{{$json.chatInput}}",
                "displayOptions": {"show": {"promptType": ["userInput"]}},
                "description": "Expression to read the chat input from the connected Chat Trigger"
            },
            {
                "name": "text",
                "type": NodeParameterType.STRING,
                "display_name": "Prompt (User Message)",
                "default": "",
                "displayOptions": {"show": {"promptType": ["define"]}}
            },
            {
                "name": "requireSpecificOutputFormat",
                "type": NodeParameterType.BOOLEAN,
                "display_name": "Require Specific Output Format",
                "default": False
            },
            {
                "name": "outputFormat",
                "type": NodeParameterType.STRING,
                "display_name": "Output Format",
                "default": "json",
                "displayOptions": {"show": {"requireSpecificOutputFormat": [True]}},
                "description": "Required output format (e.g., 'json', 'markdown', etc.)"
            },
            {
                "name": "options",
                "type": NodeParameterType.COLLECTION,
                "display_name": "Options",
                "default": {},
                "options": [
                    {
                        "name": "systemMessage",
                        "type": NodeParameterType.STRING,
                        "display_name": "System Message",
                        "default": "You are a helpful AI assistant. Use the available tools when needed to provide accurate responses.",
                        "description": "System prompt to guide the agent's behavior"
                    },
                    {
                        "name": "maxIterations",
                        "type": NodeParameterType.NUMBER,
                        "display_name": "Max Iterations",
                        "default": 5,
                        "description": "Maximum number of tool-use iterations"
                    },
                    {
                        "name": "returnIntermediateSteps",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Return Intermediate Steps",
                        "default": False,
                        "description": "Whether to return intermediate steps"
                    },
                    {
                        "name": "enableMultiTurnTools",
                        "type": NodeParameterType.BOOLEAN,
                        "display_name": "Enable Multi-turn Tool Calls",
                        "default": True,
                        "description": "Allow the model to use multiple tools across conversation turns"
                    }
                ]
            }
        ]
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tool_manager = ToolManager(self)
        self.mcp_handler = create_mcp_handler(self)  # NEW
        
        # Track tool name -> canvas node name mapping (populated during tool preparation)
        # This enables robust shadow node name resolution regardless of tool naming patterns
        self._tool_to_node_map: Dict[str, str] = {}
        
        # Defer publisher initialization until execute() is called
        # (execution context is attached after __init__)
        self._publisher_initialized = False
    
    def _ensure_publisher_initialized(self):
        """Initialize publisher if not already done (called from execute())"""
        if self._publisher_initialized:
            return
        
        # Extract IDs from workflow/execution context
        workflow_id = str(getattr(self.workflow, "id", ""))
        execution_id = getattr(self, "_execution_id", None) or ""
        
        # Get pub_sub from execution context (now attached by executor)
        execution_ctx = getattr(self, "execution", None)
        
        pub_sub = getattr(execution_ctx, "pub_sub", False) if execution_ctx else False

        self._init_publisher(workflow_id, execution_id, pub_sub)
        
        self._publisher_initialized = True

    # ai_agent.py (inside class AIAgentNode)

    def _publish_workflow_update(self, event: str, node_name: str, data: dict | None = None) -> None:
        """
        Publish a workflow update to the 'workflow_updates' queue so that
        WorkflowMessageHandler -> WebSocket will forward it.
        
        DEPRECATED: Use _AgentEventPublisher methods instead for agent-specific events.
        This method remains for backward compatibility with legacy shadow node publishing.
        """
        if not self.pub_sub or not self.queue:
            return
        
        try:
            # Format the message to match what's expected by WebSocket clients
            inner_payload = {
                "event": event,                  # e.g. "node_completed"
                "workflow_id": self.workflow_id,
                "execution_id": self.execution_id,
                "node_name": node_name,          # shadow node's display name
                "data": data or []               # Must be an array of items with json_data
            }
            
            # Add the outer wrapper that the WebSocket client expects
            payload = {
                "type": "workflow_update",
                "data": inner_payload
            }

            self.queue.publish_sync(queue_name="workflow_updates", message=payload)
        except Exception as e:
            logger.warning(f"[AI Agent] publish_workflow_update failed: {e}")


    def _resolve_canvas_node_name(self, tool_name: str) -> str:
        """
        Map a tool name to the actual canvas node name that provides it.
        
        Resolution Strategy (in order of priority):
        1. Check self._tool_to_node_map (populated during tool preparation) - MOST RELIABLE
        2. Pattern matching against upstream tool nodes (fallback for legacy/unknown tools)
        
        Returns the real node name from the workflow, not a fabricated one.
        """
        #logger.info(f"[AI Agent Shadow] _resolve_canvas_node_name called for tool: {tool_name}")
        
        # PRIORITY 1: Check dynamic tool-to-node mapping (most reliable)
        # This mapping is populated during tool preparation (_get_retriever_tools, tool_manager.prepare)
        # and works regardless of tool naming patterns
        if tool_name in self._tool_to_node_map:
            canvas_node_name = self._tool_to_node_map[tool_name]
            logger.debug(f"[AI Agent Shadow] ✓ Resolved {tool_name} -> {canvas_node_name} (via mapping)")
            return canvas_node_name
        
        # PRIORITY 2: Fallback pattern matching (for tools not tracked in mapping)
        # Get all upstream tool nodes
        upstream_tools = self._resolve_tool_nodes()
        #logger.info(f"[AI Agent Shadow] Found {len(upstream_tools)} upstream tool nodes")
        
        # For MCP tools, find the MCP Client Tool node that provides this tool
        for node_model in upstream_tools:
            node_type = (node_model.type or "").lower()
            #logger.info(f"[AI Agent Shadow]   - Checking node: {node_model.name} (type: {node_type})")
            
            # If this is an MCP node, return its actual canvas name
            if node_type == "mcpclienttool":
                #logger.info(f"[AI Agent Shadow]   ✓ Found MCP node: {node_model.name}")
                # Return the actual node name from the workflow canvas
                return node_model.name
            
            # DEPRECATED PATTERN: Qdrant/Vector Store retrievers
            # This is now handled by _tool_to_node_map, but kept as fallback
            if tool_name.startswith("search_") and node_type == "qdrantvectorstore":
                logger.debug(f"[AI Agent Shadow] ⚠ Using legacy pattern match for {tool_name} (should use mapping)")
                return node_model.name
            
            # For other tools, check if the tool name matches the node type
            normalized_tool = tool_name.replace("-", "_").replace(" ", "_").replace("_", "").lower()
            normalized_type = node_type.replace("-", "_").replace(" ", "_").replace("_", "").lower()
            
            #logger.info(f"[AI Agent Shadow]   - Comparing (no underscores): {normalized_tool} vs {normalized_type}")
            
            if normalized_tool == normalized_type or normalized_tool in normalized_type or normalized_type in normalized_tool:
                #logger.info(f"[AI Agent Shadow]   ✓ Match found: {node_model.name}")
                return node_model.name
    
        # Fallback: return the tool name as-is if no matching node found
        logger.warning(f"[AI Agent Shadow] ✗ Could not map tool '{tool_name}' to a canvas node, using tool name as fallback")
        return tool_name

    def _project_steps_to_shadow_nodes(self, steps: list[dict]) -> dict[str, dict]:
        """
        Convert agent intermediate steps to shadow node outputs using ACTUAL node names.
        { "<ActualNodeName>": {"status":"completed","output":{...},"shadow":True} }
        """
        out: dict[str, dict] = {}
        for st in steps or []:
            act = (st.get("action") or {})
            obs = st.get("observation") or {}
            tool = (act.get("tool") or "").strip()
            if not tool:
                continue
            
            # Get the ACTUAL canvas node name (e.g., "Shopify Storefront MCP")
            node_name = self._resolve_canvas_node_name(tool)
            
            out[node_name] = {
                "status": "completed",
                "output": obs,
                "shadow": True,
                "source": "agent",
                "tool_name": tool,  # Keep original tool name for reference
            }
        return out


    @staticmethod
    def normalize_parameters(params: Any) -> Dict[str, Any]:
        return _normalize_parameters(params)

    # -------- Tool Argument Validation & Coercion --------
    @staticmethod
    def _coerce_primitive(expected_type: str, value: Any) -> Tuple[bool, Any]:
        return _coerce_primitive_utils(expected_type, value)

    @staticmethod
    def _validate_and_coerce_args(param_schema: Dict[str, Any], args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], Dict[str, Any]]:
        return _validate_and_coerce_args_utils(param_schema, args)

    # -------- Transient-error handling for model invoke --------
    def _is_transient_exc(self, e: Exception) -> bool:
        return _is_transient_exc(e)

    def _invoke_with_retries(self, chat_model_or_adapter, messages, tools, attempts: int = 3, base_delay: float = 0.6):
        """
        Invoke with retries. Supports both ChatModelRunnable and raw adapters.
        """
        try:
            # Check if it's a ChatModelRunnable (has invoke method that takes dict)
            if hasattr(chat_model_or_adapter, 'invoke') and hasattr(chat_model_or_adapter, '__class__'):
                class_name = chat_model_or_adapter.__class__.__name__
                if 'Runnable' in class_name or 'ChatModel' in class_name:
                    # It's a Runnable - call with dict input
                    return _retry_call(
                        lambda: chat_model_or_adapter.invoke({"messages": messages, "tools": tools}),
                        attempts=attempts,
                        base_delay=base_delay
                    )
            
            # Otherwise, it's a raw adapter - call with keyword args
            return _retry_call(
                lambda: chat_model_or_adapter.invoke(messages=messages, tools=tools),
                attempts=attempts,
                base_delay=base_delay
            )
        except Exception as e:
            return {"error": f"Model invoke failed: {e.__class__.__name__}: {str(e)}", "transient": True, "attempts": attempts}
    
    def _execute_tool_with_collection(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        tools_collection,
        messages: List[Dict[str, Any]],
        intermediate: List[Dict[str, Any]],
        user_query: str
    ) -> None:
        """
        Execute a single tool using ToolCollectionRunnable.
        Updates messages and intermediate steps in place.
        """
        try:
            # Invoke tool through collection
            result_dict = tools_collection.invoke({
                "tool_name": tool_name,
                "arguments": tool_args
            })
            
            # ToolRunnable returns {"ok": True/False, "data": ..., "error": ...}
            if result_dict.get("ok"):
                raw_result = result_dict.get("data")
                
                # Process the tool response (filtering, truncation, relevance selection)
                processed_result = _process_tool_response(
                    tool_key=tool_name,
                    tool_name=tool_name,
                    response=raw_result,
                    user_query=user_query
                )
                
                # Convert processed result to string for LLM consumption
                if isinstance(processed_result, dict):
                    result_str = json.dumps(processed_result, ensure_ascii=False)
                elif isinstance(processed_result, (list, tuple)):
                    result_str = json.dumps(processed_result, ensure_ascii=False)
                else:
                    result_str = str(processed_result)
            else:
                error_dict = result_dict.get('error', {})
                error_msg = error_dict.get('message', 'Unknown error') if isinstance(error_dict, dict) else str(error_dict)
                result_str = f"Error: {error_msg}"
                processed_result = {"error": error_msg}
                logger.warning(f"[AI Agent Tool] Tool execution failed: {error_msg}")
            
            # Add tool message to conversation
            messages.append({
                "role": "tool",
                "tool_call_id": tool_args.get("_call_id", ""),
                "name": tool_name,
                "content": result_str
            })
            
            # Track in intermediate steps
            intermediate.append({
                "action": {"tool": tool_name, "tool_input": tool_args},
                "observation": processed_result
            })
            
        except Exception as e:
            logger.error(f"[AI Agent] Tool execution error for {tool_name}: {e}", exc_info=True)
            error_msg = f"Tool execution failed: {str(e)}"
            messages.append({
                "role": "tool",
                "tool_call_id": tool_args.get("_call_id", ""),
                "name": tool_name,
                "content": error_msg
            })
            intermediate.append({
                "action": {"tool": tool_name, "tool_input": tool_args},
                "observation": {"error": error_msg}
            })

    @staticmethod
    def _coerce_node_definitions_mapping(raw) -> dict:
        return _coerce_node_defs_map(raw)

    def _dyn_import_node_class_from_type(self, node_type: str):
        return _dyn_import_node_cls(node_type)

    def _resolve_node_definitions(self, preferred: dict | None, tool_nodes: list) -> dict:
        return _resolve_node_defs(preferred, getattr(self, "workflow", None), tool_nodes or [])

    def _get_execution_data_ref(self) -> Dict[str, Any]:
        return _get_exec_ref(self)

    def _persist_provider_snapshot(self, input_name: str, payload_key: str, 
                                   payload_value: Dict[str, Any]) -> None:
        _persist_provider_snap(self, input_name, payload_key, payload_value)

    def _inline_execute_node(self, node_model, workflow, execution_data) -> None:
        _run_node_inline(node_model, workflow, execution_data)

    def _execute_tool(self, node_cls, node_model, args, expr_json: Optional[Dict[str, Any]] = None):
        # Sanitize tool input before execution (drop blanks, coerce booleans)
        try:
            args = _clean_tool_args(args or {})
        except Exception:
            pass
        return _execute_tool_util(self, node_cls, node_model, args, expr_json=expr_json)

    def _messages_for_memory(self, msgs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return _messages_for_memory_util(msgs)

    def _build_initial_messages(
        self,
        system_message: str,
        tools: List[Dict[str, Any]],
        memory: Optional[Dict[str, Any]],
        user_input: str,
    ) -> List[Dict[str, Any]]:
        return _build_initial_messages_util(
            system_message, tools, memory, user_input,
            tool_instruction_builder=self._tool_instruction,
            messages_for_memory_fn=self._messages_for_memory,
        )

    def _assistant_with_tool_calls_message(
        self, assistant_msg: Dict[str, Any], tool_calls: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        return _assistant_with_tool_calls_message_util(assistant_msg, tool_calls)

    # ---------------------------- Public execute ---------------------------
    def execute(self) -> List[List[NodeExecutionData]]:
        # Initialize publisher now that execution context is attached
        self._ensure_publisher_initialized()
        
        try:
            items = self.get_input_data()
            if not items:
                return [[]]

            # Store execution context and ID for later use
            execution_ctx = getattr(self, "execution", None)
            
            # For _fetch_or_exec_input, pass None as execution parameter to use inline execution fallback
            # (The execution parameter expects a WorkflowExecutor, not a WorkflowExecutionContext)
            ai_model = self._resolve_ai_model(self.workflow, None, self.execution_data)
            if not ai_model:
                return [[NodeExecutionData(json_data={"error": "No AI model connected"}, binary_data=None)]]
            # Persist a snapshot so model appears in all_results even if inlined
            self._persist_provider_snapshot("ai_model", "ai_model", ai_model)

            tool_nodes = self._resolve_tool_nodes()
            
            # CRITICAL FIX: Filter out Qdrant nodes (they'll be added as retriever tools later)
            regular_tool_nodes = [
                node for node in tool_nodes 
                if node.type != "qdrantVectorStore"
            ] if tool_nodes else []
            
            # NEW: Get tools as ToolRunnable instances (excluding Qdrant nodes)
            tool_runnables = self.tool_manager.prepare(regular_tool_nodes)
            
            # Create ToolCollectionRunnable from tool runnables
            from utils.langchain_tools import ToolCollectionRunnable
            if tool_runnables:
                tools_collection = ToolCollectionRunnable(tool_runnables)
            else:
                tools_collection = None

            # Lazy resolve memory and persist snapshot if found
            memory = self._resolve_memory(self.workflow, None, self.execution_data)
            if memory:
                self._persist_provider_snapshot("ai_memory", "ai_memory", memory)

            # Get tool schemas once for all items
            tool_schemas = []
            if tools_collection:
                tool_schemas = tools_collection.get_tool_schemas(format="openai")
            
            # ╔══════════════════════════════════════════════════════════════════════════════╗
            # ║ RABBITMQ OPTIMIZATION: agent_started event DISABLED                          ║
            # ║                                                                              ║
            # ║ REASON: Reduces RabbitMQ load by 1 message per execution                    ║
            # ║ IMPACT: UI loses real-time "agent starting" notification                    ║
            # ║ JUSTIFICATION: Minor UX loss for significant infrastructure stability       ║
            # ╚══════════════════════════════════════════════════════════════════════════════╝
            # self._agent_started(
            #     model=f"{ai_model.get('provider', 'unknown')}/{ai_model.get('model', 'unknown')}",
            #     tools_count=len(tool_schemas)
            # )
            
            results: List[NodeExecutionData] = []
            all_intermediate_steps = []  # Aggregate from all items
            all_messages = []  # Aggregate final messages
            total_iterations = 0
            total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            all_success = True
            
            for i, item in enumerate(items):
                #logger.info(f"[AI Agent] Processing item {i+1}/{len(items)}")
                user_input = self._compute_user_input(i, item)
                if not user_input:
                    results.append(NodeExecutionData(json_data={"error": "No user input provided"}, binary_data=None))
                    continue
                
                result = self._agent_loop(ai_model, tools_collection, memory, user_input, i)
                
                # Collect messages to populate message field
                if result.get("message"):
                    all_messages.append(result["message"])
                
                results.append(NodeExecutionData(json_data=result, binary_data=item.binary_data))
                
                # Aggregate metrics from all items
                if result.get("success"):
                    total_iterations += result.get("iterations", 0)
                    if result.get("intermediate_steps"):
                        all_intermediate_steps.extend(result["intermediate_steps"])
                    # Check for usage dict (legacy format)
                    if result.get("usage"):
                        total_usage["prompt_tokens"] += result["usage"].get("prompt_tokens", 0)
                        total_usage["completion_tokens"] += result["usage"].get("completion_tokens", 0)
                        total_usage["total_tokens"] += result["usage"].get("total_tokens", 0)
                    # Also check for direct total_tokens (AgentRunnable format)
                    elif result.get("total_tokens"):
                        total_usage["total_tokens"] += result.get("total_tokens", 0)
                else:
                    all_success = False
            
            # Publish agent_completed ONCE with aggregated metrics
            # Handle content that might be list or string
            clean_messages = []
            for msg in all_messages:
                if isinstance(msg, list):
                    # Extract text from content blocks
                    text = "".join(
                        block.get("text", "") 
                        for block in msg 
                        if isinstance(block, dict) and block.get("type") == "text"
                    )
                    clean_messages.append(text)
                else:
                    clean_messages.append(str(msg))
            
            aggregated_message = " | ".join(clean_messages) if clean_messages else f"Processed {len(results)} items"
            
            # ╔══════════════════════════════════════════════════════════════════════════════╗
            # ║ RABBITMQ OPTIMIZATION: ONLY FINAL OUTPUT PUBLISHED                          ║
            # ║                                                                              ║
            # ║ ENABLED: agent_completed event (1 message)                                  ║
            # ║   - This is the ONLY RabbitMQ message published by AI Agent                 ║
            # ║   - Contains final output text + execution summary                          ║
            # ║   - Essential for WebSocket clients to receive results                      ║
            # ║                                                                              ║
            # ║ REASON: Production workflows with 30 Qdrant retrievals were generating      ║
            # ║         100+ RabbitMQ messages (agent_started, tool_called × 30,            ║
            # ║         tool_result × 30, model_result × 5, shadow nodes × 33)              ║
            # ║         This caused CPU spikes and server crashes                           ║
            # ║                                                                              ║
            # ║ TRADEOFF: UI loses real-time progress updates but gains stability           ║
            # ╚══════════════════════════════════════════════════════════════════════════════╝
            
            # ╔══════════════════════════════════════════════════════════════════════════════╗
            # ║ RABBITMQ OPTIMIZATION: ALL custom agent events REMOVED                      ║
            # ║                                                                              ║
            # ║ The AI Agent now behaves exactly like ALL other nodes (Bale, HTTP, etc.):   ║
            # ║   ✓ Executes silently (no custom events)                                    ║
            # ║   ✓ Returns results via return statement                                    ║
            # ║   ✓ Execution engine publishes standard "node_completed" event              ║
            # ║                                                                              ║
            # ║ BEFORE: _agent_completed + _agent_started + all tool events = 100+ msgs     ║
            # ║ AFTER:  0 custom events - executor publishes 1 node_completed event         ║
            # ║                                                                              ║
            # ║ This matches Bale node, HTTP Request node, and all other nodes.             ║
            # ╚══════════════════════════════════════════════════════════════════════════════╝
            # REMOVED: self._agent_completed() - executor publishes node_completed instead
            
            # ╔══════════════════════════════════════════════════════════════════════════════╗
            # ║ RABBITMQ OPTIMIZATION: Shadow node publishing COMPLETELY DISABLED            ║
            # ║                                                                              ║
            # ║ REASON: Shadow nodes generate 30+ messages per execution:                   ║
            # ║   - 1 AI Model shadow                                                       ║
            # ║   - 1 Memory shadow (if used)                                               ║
            # ║   - 30 Tool shadows (for 30 Qdrant retrievals in production workflow)       ║
            # ║   - 1 Embedding provider shadow per unique tool                             ║
            # ║                                                                              ║
            # ║ IMPACT: Canvas no longer shows tool execution in UI                         ║
            # ║ JUSTIFICATION: Production stability > visual debugging convenience          ║
            # ║                                                                              ║
            # ║ NOTE: All execution data is still stored in database and returned           ║
            # ║       in final output - only real-time WebSocket updates are disabled       ║
            # ╚══════════════════════════════════════════════════════════════════════════════╝
            # self._publish_final_shadows(ai_model, memory, all_intermediate_steps, total_usage, tool_schemas, aggregated_message)
            
            #logger.info(f"[AI Agent] Completed processing {len(results)} items")
            return [results]
        except Exception as e:
            logger.error(f"[AI Agent] execute error: {e}")
            return [[NodeExecutionData(json_data={"error": str(e)}, binary_data=None)]]

    # ---------------------------- Resolution --------------------------------
    def _node_cls(self, type_name: str):
        from nodes import node_definitions
        info = node_definitions.get(type_name)
        return info and info.get("node_class")

    def _fetch_or_exec_input(
        self, workflow, execution, execution_data, input_name: str
    ) -> List[NodeExecutionData]:
        """
        n8n-like behavior:
         1) read items for the typed input
         2) if empty and we have an execution context, run upstream providers and read again
        """
        items = ConnectionResolver.get_items(workflow, execution_data, self.node_data.name, input_name)
        if items:
            return items

        upstream = ConnectionResolver.get_upstream_nodes(workflow, self.node_data.name, input_name)

        if execution:
            # Preferred path: use the workflow's executor
            for n in upstream:
                execution.execute_node(n)
        else:
            # Fallback: inline execute providers (n8n-like pull semantics)
            for n in upstream:
                try:
                    self._inline_execute_node(n, workflow, execution_data)
                except Exception as e:
                    logger.error(f"[AI Agent] Inline exec failed for provider '{n.name}': {e}")

        # re-collect after executing providers
        return ConnectionResolver.get_items(workflow, execution_data, self.node_data.name, input_name)


    def _resolve_ai_model(self, workflow, execution, execution_data) -> dict:
        items = self._fetch_or_exec_input(workflow, execution, execution_data, "ai_model")
        if not items:
            logger.warning(f"[AI Agent] No items from ai_model input (execution={'present' if execution else 'None'})")
            return {}
        for it in items:
            jd = getattr(it, "json_data", {}) or {}
            mi = jd.get("ai_model") or {}
            if mi:
                logger.debug(f"[AI Agent] Resolved ai_model: provider={mi.get('provider')}, model={mi.get('model')}, registry_id={mi.get('registry_id')}")
                return mi
            else:
                logger.warning(f"[AI Agent] Item has no ai_model field. json_data keys: {list(jd.keys())}")
        return {}

    def _resolve_tool_nodes(self) -> List[NodeModel]:
        upstream = ConnectionResolver.get_upstream_nodes(self.workflow, self.node_data.name, "ai_tool")
        result: List[NodeModel] = []
        for nm in upstream:
            node_cls = self._node_cls(nm.type)
            if not node_cls:
                continue
            try:
                if node_cls.description.get("usableAsTool", True) is False:  # type: ignore[attr-defined]
                    continue
            except Exception:
                pass
            result.append(nm)

        return result

    def _build_providers_meta(self, ai_model: Dict[str, Any], memory: Optional[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        return _build_providers_meta_util(ai_model, memory, tools)

    # ---------------------------- dynamic, compact tool instruction ----------------------------
    def _classify_tools(self, tools: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Heuristically classify tools by schema (no hardcoding)."""
        return _classify_tools_utils(tools)

    def _tool_instruction(self, tools):
        return _tool_instruction_utils(tools)


    def _stringify_item(self, item: Any, max_len: int = 2000) -> str:
        return _stringify_item_utils(item, max_len=max_len)

    def _select_relevant_items(self, items: List[Any], user_query: str, limit: int = 20, max_chars: int = 9000) -> Dict[str, Any]:
        return _select_relevant_items_utils(items, user_query=user_query, limit=limit, max_chars=max_chars)

    def _smart_truncate(self, text: str, max_length: int) -> str:
        return _smart_truncate_utils(text, max_length)


    def _resolve_memory(self, workflow, execution, execution_data) -> Optional[Dict[str, Any]]:
        """
        n8n-like lazy fetch: try to read inbound items for 'ai_memory'; if empty,
        inline-execute upstream providers and read again. Return the ai_memory dict.
        """
        items = self._fetch_or_exec_input(workflow, execution, execution_data, "ai_memory")
        for it in (items or []):
            jd = getattr(it, "json_data", {}) or {}
            mem = jd.get("ai_memory") or jd
            if isinstance(mem, dict):
                return mem
        return None

    def _compute_user_input(self, idx: int, item: NodeExecutionData) -> str:
        """Match n8n's handling of user input from triggers"""
        source = self.get_node_parameter("promptType", idx, "userInput")
        if source == "define":
            text = self.get_node_parameter("text", idx, "") or ""
            # BUGFIX: Strip leading '=' from expression evaluation artifacts
            if text.startswith("="):
                text = text[1:]
            return text.strip()
        # promptType == "userInput"
        expr = self.get_node_parameter("userInputExpression", idx, "{{$json.chatInput}}") or "{{$json.chatInput}}"
        if isinstance(expr, str) and expr.strip():
            # get_node_parameter already evaluates expressions with current item
            resolved = expr
            if isinstance(resolved, str) and resolved.strip():
                # BUGFIX: Strip leading '=' from expression evaluation artifacts
                if resolved.startswith("="):
                    resolved = resolved[1:]
                return resolved.strip()

        jd = item.json_data or {}
        return jd.get("chatInput") or jd.get("message") or jd.get("input") or jd.get("query") or jd.get("question") or ""


    # ---------------------------- Agent Loop -------------------------------
    def _get_chat_model_runnable(self, item_index: int) -> Optional[Any]:
        """
        Get ChatModelRunnable from ai_model provider node.
        
        Args:
            item_index: Current item index
            
        Returns:
            ChatModelRunnable instance or None
        """
        from utils.runnable_helpers import get_runnable_from_provider
        
        try:
            chat_model_runnable = get_runnable_from_provider(
                workflow=self.workflow,
                execution_data=self.execution_data,
                node_name=self.node_data.name,
                input_name="ai_model"
            )
            return chat_model_runnable
        except Exception as e:
            logger.error(f"[AI Agent] Failed to get ChatModelRunnable: {e}")
            return None
    
    def _get_memory_runnable(self, item_index: int) -> Optional[Any]:
        """
        Get MemoryRunnable from ai_memory provider node.
        
        Args:
            item_index: Current item index
            
        Returns:
            MemoryRunnable instance or None
        """
        from utils.runnable_helpers import get_runnable_from_provider
        
        try:
            memory_runnable = get_runnable_from_provider(
                workflow=self.workflow,
                execution_data=self.execution_data,
                node_name=self.node_data.name,
                input_name="ai_memory"
            )
            return memory_runnable
        except Exception as e:
            logger.debug(f"[AI Agent] No memory runnable: {e}")
            return None
    
    def _get_tools_collection(self) -> Optional[Any]:
        """
        Get ToolCollectionRunnable from all tool sources.
        
        This method unifies:
        - Regular tool nodes (ai_tool input)
        - Retriever tools (from Qdrant/vector stores)
        - MCP tools (future enhancement)
        
        Returns:
            ToolCollectionRunnable instance or None
        """
        tool_nodes = self._resolve_tool_nodes()
        
        # CRITICAL FIX: Filter out Qdrant nodes from regular tool preparation
        # Qdrant nodes must ONLY be registered as retriever tools (search_xxx)
        # not as regular tools (Qdrant_Vector_Store)
        regular_tool_nodes = [
            node for node in tool_nodes 
            if node.type != "qdrantVectorStore"
        ] if tool_nodes else []
        
        # Prepare regular tools (excluding Qdrant nodes)
        from utils.langchain_tools import ToolCollectionRunnable
        tool_runnables = self.tool_manager.prepare(regular_tool_nodes) if regular_tool_nodes else []
        
        # CRITICAL: Track regular tool name -> node name mappings
        # This enables robust shadow resolution for all tool types
        if tool_runnables and tool_nodes:
            for tool_runnable, node_model in zip(tool_runnables, tool_nodes):
                self._tool_to_node_map[tool_runnable.name] = node_model.name
                #logger.debug(f"[AI Agent] Tracked tool mapping: {tool_runnable.name} -> {node_model.name}")
        
        # Add retriever tools (these already track their mappings in _get_retriever_tools)
        retriever_tools = self._get_retriever_tools()
        if retriever_tools:
            tool_runnables.extend(retriever_tools)
            #logger.info(f"[AI Agent] Added {len(retriever_tools)} retriever tools")
        
        if tool_runnables:
            return ToolCollectionRunnable(tool_runnables)
        return None
    
    def _get_retriever_tools(self) -> List[Any]:
        """
        Get retriever tools from connected Qdrant/vector store nodes.
        
        This enables RAG (Retrieval-Augmented Generation) by allowing the agent
        to search knowledge bases during reasoning.
        
        Returns:
            List of RetrieverToolRunnable instances
        """
        from utils.retriever_tool_wrapper import wrap_qdrant_node_as_tool
        from utils.connection_resolver import ConnectionResolver
        
        retriever_tools = []
        
        try:
            # Get all nodes connected to ai_tool input
            # (Qdrant nodes with usableAsTool=True will appear here)
            upstream_nodes = ConnectionResolver.get_upstream_nodes(
                self.workflow,
                self.node_data.name,
                "ai_tool"
            )
            
            for node_model in upstream_nodes:
                # Check if this is a Qdrant vector store node
                if node_model.type == "qdrantVectorStore":
                    try:
                        # Instantiate the node
                        from nodes.qdrantVectorStore import QdrantVectorStoreNode
                        
                        qdrant_node = QdrantVectorStoreNode(
                            node_data=node_model,
                            workflow=self.workflow,
                            execution_data=self.execution_data
                        )
                        
                        # Get topK parameter from Qdrant node (default to 30 if not set)
                        max_results = qdrant_node.get_node_parameter("topK", 0, 30)
                        
                        # Wrap as retriever tool
                        retriever_tool = wrap_qdrant_node_as_tool(
                            qdrant_node=qdrant_node,
                            item_index=0,
                            max_results=max_results
                        )
                        
                        retriever_tools.append(retriever_tool)
                        
                        # CRITICAL: Track tool name -> canvas node name mapping
                        # This enables robust shadow resolution regardless of tool naming patterns
                        self._tool_to_node_map[retriever_tool.name] = node_model.name
                        
                    except Exception as e:
                        logger.error(
                            f"[AI Agent] Failed to create retriever tool from "
                            f"node {node_model.name}: {e}"
                        )
            
        except Exception as e:
            logger.error(f"[AI Agent] Error getting retriever tools: {e}")
        
        # Log summary of all registered tools
        if retriever_tools:
            logger.info(f"[AI Agent] ✓ Total retriever tools registered: {len(retriever_tools)}")
        else:
            logger.warning(f"[AI Agent] ⚠️ No retriever tools registered!")
        
        return retriever_tools
    
    def _agent_loop(
        self,
        ai_model: Dict[str, Any],
        tools_collection: Optional[Any],  # ToolCollectionRunnable
        memory: Optional[Dict[str, Any]],
        user_input: str,
        item_index: int,
    ) -> Dict[str, Any]:
        """
        Execute agent loop via AgentRunnable.
        
        This is the NEW implementation that delegates to AgentRunnable
        instead of implementing custom loop logic.
        
        Args:
            ai_model: Model metadata (DEPRECATED - now resolved via get_runnable)
            tools_collection: Tool collection (DEPRECATED - now resolved via helper)
            memory: Memory config (DEPRECATED - now resolved via get_runnable)
            user_input: User query
            item_index: Current item index
            
        Returns:
            Execution result dict
        """
        from utils.langchain_agents import AgentRunnable
        
        # Get node parameters
        options = self.get_node_parameter("options", item_index, {}) or {}
        system_message = options.get("systemMessage", "You are a helpful AI assistant.")
        max_iterations = int(options.get("maxIterations", 5))
        return_steps = bool(options.get("returnIntermediateSteps", False))
        enable_multi_turn = bool(options.get("enableMultiTurnTools", True))
        
        # Get Runnable instances from providers
        chat_model_runnable = self._get_chat_model_runnable(item_index)
        if not chat_model_runnable:
            # REMOVED: self._agent_error() - executor publishes node_error instead
            # Just raise the exception normally, executor will handle error publishing
            raise ValueError("Chat model not connected")
        
        memory_runnable = self._get_memory_runnable(item_index)
        tools_collection_runnable = self._get_tools_collection()
        
        # Import ToolCollectionRunnable and AgentEventPublisher
        from utils.langchain_tools import ToolCollectionRunnable
        from utils.agent_events import AgentEventPublisher
        
        # ╔══════════════════════════════════════════════════════════════════════════════╗
        # ║ RABBITMQ OPTIMIZATION: AgentRunnable event streaming DISABLED               ║
        # ║                                                                              ║
        # ║ REASON: AgentRunnable publishes granular events during agent loop:           ║
        # ║   - agent_step (per iteration: 2-5 messages)                                 ║
        # ║   - tool_called (per tool use: 30 messages in production workflow)           ║
        # ║   - tool_result (per tool use: 30 messages)                                  ║
        # ║   - model_result (per LLM call: 5-10 messages)                               ║
        # ║   - memory_result (per memory operation: 2 messages)                         ║
        # ║                                                                              ║
        # ║ TOTAL DISABLED: ~70-100 intermediate messages per execution                 ║
        # ║                                                                              ║
        # ║ IMPACT: UI no longer shows live agent reasoning steps                        ║
        # ║ JUSTIFICATION: Prevents RabbitMQ CPU spikes and server crashes              ║
        # ╚══════════════════════════════════════════════════════════════════════════════╝
        event_publisher = None  # DISABLED: Set to None to prevent intermediate events
        # if self.pub_sub and hasattr(self, 'workflow_id') and hasattr(self, 'execution_id'):
        #     event_publisher = AgentEventPublisher(
        #         workflow_id=self.workflow_id,
        #         execution_id=self.execution_id,
        #         node_name=self.node_data.name,
        #         lane=0,
        #         pub_sub=True,
        #         queue_service=self.queue if hasattr(self, 'queue') else None
        #     )
        
        # Create AgentRunnable
        agent = AgentRunnable(
            chat_model=chat_model_runnable,
            tools=tools_collection_runnable or ToolCollectionRunnable([]),  # Empty collection if no tools
            system_message=system_message,
            max_iterations=max_iterations,
            return_intermediate_steps=return_steps,
            enable_multi_turn_tools=enable_multi_turn,
            memory_runnable=memory_runnable,
            event_publisher=event_publisher,  # None = disables all intermediate events
            name=f"Agent_{self.node_data.name}"
        )
        
        # Register runnable for cleanup
        from utils.langchain_base import RunnableRegistry
        runnable_id = RunnableRegistry.register(agent)
        
        try:
            # Invoke agent
            result = agent.invoke({
                "user_input": user_input
            })
            
            # Add providers metadata
            providers = self._build_providers_meta(ai_model, memory, [] if not tools_collection_runnable else tools_collection_runnable.get_tool_schemas(format="openai"))
            result["providers"] = providers
            
            return result
            
        finally:
            # Cleanup
            RunnableRegistry.unregister(runnable_id)

    # =========== OLD AGENT LOOP CODE REMOVED ===========
    # The old 500+ line custom agent loop has been replaced with AgentRunnable delegation above.
    # The old code manually implemented:
    # - Message management
    # - Tool calling loop
    # - Memory loading/saving
    # - Event publishing
    # All of this is now handled by AgentRunnable.invoke()
    # ===================================================
    def _publish_shadow_node(self, node_name: str, node_data: Dict[str, Any]) -> None:
        """Publish a shadow node's output to the workflow updates queue"""
        #logger.info(f"[AI Agent Shadow] _publish_shadow_node called: node_name={node_name}, pub_sub={self.pub_sub}, queue={self.queue is not None}")
        
        if not self.pub_sub or not self.queue:
            logger.warning(f"[AI Agent Shadow] Skipping publish for {node_name}: pub_sub={self.pub_sub}, queue={self.queue is not None}")
            return
        
        try:
            # Format the data as expected by the WebSocket client
            formatted_data = [{"json_data": node_data}]
            
            # Generate a unique ID for this shadow node
            node_id = f"{node_name.lower().replace(' ', '_')}_{int(time.time()*1000)}"

            # CRITICAL ADDITION: Store the shadow node in execution data
            execution_data = self._get_execution_data_ref()
            if "shadow_nodes" not in execution_data:
                execution_data["shadow_nodes"] = {}

            execution_data["shadow_nodes"][node_id] = {
                "type": node_name.lower().replace(' ', '_'),
                "parent_node": self.node_data.name,
                "name": node_name,
                "data": node_data
            }
            
            #logger.info(f"[AI Agent Shadow] ✓ Stored {node_name} in execution data as shadow node")
            
            # CRITICAL ADDITION: Persist to database if we have an execution ID
            if self.execution_id:
                try:
                    with get_sync_session_manual() as session:
                        from database.crud import ExecutionCRUD
                        
                        # Update the execution data in the database
                        ExecutionCRUD.update_execution_data_sync(
                            session,
                            self.execution_id,
                            {"shadow_nodes": execution_data["shadow_nodes"]}
                        )
                        #logger.info(f"[AI Agent Shadow] ✓ Persisted {len(execution_data['shadow_nodes'])} shadow nodes to database for execution {self.execution_id}")
                except Exception as e:
                    logger.error(f"[AI Agent Shadow] ✗ Failed to persist shadow nodes to database: {e}")
            
            # Send to WebSocket via QueueService
            payload = {
                "event": "node_completed",
                "workflow_id": self.workflow_id,
                "execution_id": self.execution_id,
                "node_name": node_name,
                "data": formatted_data
            }
            
            # logger.info(f"[AI Agent Shadow] 📤 Publishing to workflow_updates: {node_name}")
            # logger.info(f"[AI Agent Shadow]    - workflow_id: {self.workflow_id}")
            # logger.info(f"[AI Agent Shadow]    - execution_id: {self.execution_id}")
            # logger.info(f"[AI Agent Shadow]    - payload keys: {list(payload.keys())}")
            
            self.queue.publish_sync(queue_name="workflow_updates", message=payload)
            #logger.info(f"[AI Agent Shadow] ✓ Successfully published shadow node: {node_name}")
        except Exception as e:
            logger.error(f"[AI Agent Shadow] ✗ Error publishing shadow node {node_name}: {e}", exc_info=True)

    def _publish_final_shadows(
        self,
        ai_model: Dict[str, Any],
        memory: Optional[Dict[str, Any]],
        intermediate_steps: List[Dict[str, Any]],
        aggregated_usage: Dict[str, int],
        tool_schemas: List[Dict[str, Any]],
        aggregated_message: str
    ) -> None:
        """
        Publish shadow nodes ONCE at the end of execution with aggregated data from all items.
        
        Args:
            ai_model: AI model configuration
            memory: Memory configuration (if any)
            intermediate_steps: All intermediate steps from all items
            aggregated_usage: Aggregated token usage from all items
            tool_schemas: Tool schemas used
            aggregated_message: Final aggregated message from all items
        """
        # OPTIMIZATION: Skip shadow node publishing for webhooks (pub_sub=False)
        # Shadow nodes are only useful for WebSocket UI visualization
        if not self.pub_sub:
            logger.info(f"[AI Agent Shadow] Skipping shadow node publishing: pub_sub=False (webhook execution)")
            return
        
        try:
            # logger.info(f"[AI Agent Shadow] ═══════ STARTING SHADOW NODE PUBLISHING ═══════")
            # logger.info(f"[AI Agent Shadow] pub_sub={self.pub_sub}, execution_id={self.execution_id}")
            # logger.info(f"[AI Agent Shadow] Total intermediate steps: {len(intermediate_steps)}")
            
            # Generate shadow nodes from ALL intermediate steps
            shadow_nodes = self._project_steps_to_shadow_nodes(intermediate_steps)
            #logger.info(f"[AI Agent Shadow] Generated {len(shadow_nodes)} tool shadow nodes")
            
            # Publish AI Model shadow ONCE with aggregated data
            model_shadow_name = self._resolve_ai_model_node_name()
            #logger.info(f"[AI Agent Shadow] Publishing AI Model shadow: {model_shadow_name}")
            model_data = {
                "provider": ai_model.get("provider", "unknown"),
                "model": ai_model.get("model", "unknown"),
                "temperature": ai_model.get("temperature", 0),
                "registry_id": ai_model.get("registry_id"),  # CRITICAL: Preserve registry_id
                "final_message": aggregated_message,  # Aggregated from all items
                "total_calls": len(intermediate_steps),  # Total across all items
                "usage": aggregated_usage,
            }
            self._publish_shadow_node(model_shadow_name, model_data)
            
            # Publish Memory shadow if used
            if memory and memory.get("type") == "simple_memory" and memory.get("session_id"):
                memory_shadow_name = self._resolve_memory_node_name()
                #logger.info(f"[AI Agent Shadow] Publishing Memory shadow: {memory_shadow_name}")
                memory_data = {
                    "type": memory.get("type"),
                    "session_id": memory.get("session_id"),
                    "messages_count": 0,  # Could track this if needed
                    "context_window": memory.get("context_window_length", 5)
                }
                self._publish_shadow_node(memory_shadow_name, memory_data)
                
                # ╔══════════════════════════════════════════════════════════════════════════════╗
                # ║ RABBITMQ OPTIMIZATION: memory_result event DISABLED                         ║
                # ║                                                                              ║
                # ║ This event was part of the intermediate event stream that caused            ║
                # ║ RabbitMQ overload (2 messages per execution).                               ║
                # ║                                                                              ║
                # ║ NOTE: This entire _publish_final_shadows method is already disabled at      ║
                # ║       the call site (line 968), but we're commenting this out defensively   ║
                # ║       to prevent accidental re-enablement.                                   ║
                # ╚══════════════════════════════════════════════════════════════════════════════╝
                # self._memory_result(
                #     operation="save",
                #     status="success",
                #     meta={
                #         "session_id": memory.get("session_id"),
                #         "messages_count": 0
                #     }
                # )
            
            # Publish all tool shadow nodes
           # logger.info(f"[AI Agent Shadow] Publishing {len(shadow_nodes)} tool shadow nodes...")
            for node_name, node_data in shadow_nodes.items():
                #logger.info(f"[AI Agent Shadow] Publishing tool shadow: {node_name}")
                self._publish_shadow_node(node_name, node_data.get("output", {}))
            
            # Detect and publish embedding provider shadows (for tools that use embeddings)
            embedding_shadows = self._detect_embedding_providers(shadow_nodes)
            for emb_node_name, emb_data in embedding_shadows.items():
                self._publish_shadow_node(emb_node_name, emb_data)
            
            # CRITICAL: Add shadow nodes to execution context so they appear as "executed"
            self._register_shadow_nodes_as_executed(
                model_shadow_name, model_data, shadow_nodes, memory_shadow_name if memory else None, memory_data if memory else None, embedding_shadows
            )
            
            #logger.info(f"[AI Agent Shadow] ═══════ SHADOW NODE PUBLISHING COMPLETE ═══════")
                
        except Exception as e:
            logger.error(f"[AI Agent Shadow] ✗ Failed to publish shadow nodes: {e}", exc_info=True)

    def _resolve_ai_model_node_name(self) -> str:
        """Get the actual AI model node name from workflow connections"""
        try:
            upstream_models = ConnectionResolver.get_upstream_nodes(
                self.workflow, self.node_data.name, "ai_model"
            )
            if upstream_models:
                return upstream_models[0].name  # Use the actual canvas name
        except Exception as e:
            logger.warning(f"[AI Agent] Error resolving AI model node name: {e}")
    
        return "AI Model"  # Fallback

    def _resolve_memory_node_name(self) -> str:
        """Get the actual memory node name from workflow connections"""
        try:
            upstream_memory = ConnectionResolver.get_upstream_nodes(
                self.workflow, self.node_data.name, "ai_memory"
            )
            if upstream_memory:
                return upstream_memory[0].name  # Use the actual canvas name
        except Exception as e:
            logger.warning(f"[AI Agent] Error resolving memory node name: {e}")
    
        return "Memory"  # Fallback

    def _detect_embedding_providers(self, tool_shadows: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Detect embedding provider nodes used by tools (e.g., Qdrant using OpenAI Embeddings).
        
        Returns dict of {embedding_node_name: embedding_data}
        """
        embedding_shadows = {}
        
        try:
            # For each tool shadow (e.g., Qdrant Retriever), check if it has upstream embeddings
            for tool_node_name in tool_shadows.keys():
                # Find the actual tool node in workflow
                tool_node = None
                for node in self.workflow.nodes:
                    if node.name == tool_node_name:
                        tool_node = node
                        break
                
                if not tool_node:
                    continue
                
                # Check if this tool has ai_embedding upstream connection
                try:
                    embedding_nodes = ConnectionResolver.get_upstream_nodes(
                        self.workflow, tool_node.name, "ai_embedding"
                    )
                    
                    if embedding_nodes:
                        emb_node = embedding_nodes[0]
                        # Create simple shadow data for embedding provider
                        emb_data = {
                            "type": "ai_embedding",
                            "node_type": emb_node.type,
                            "used_by": tool_node_name,
                            "status": "executed_as_provider"
                        }
                        embedding_shadows[emb_node.name] = emb_data
                        
                except Exception as e:
                    logger.debug(f"[AI Agent Shadow] Error checking embeddings for {tool_node_name}: {e}")
                    
        except Exception as e:
            logger.error(f"[AI Agent Shadow] ✗ Failed to detect embedding providers: {e}")
        
        return embedding_shadows
    
    def _register_shadow_nodes_as_executed(
        self,
        model_node_name: str,
        model_data: Dict[str, Any],
        tool_shadows: Dict[str, Dict[str, Any]],
        memory_node_name: Optional[str] = None,
        memory_data: Optional[Dict[str, Any]] = None,
        embedding_shadows: Optional[Dict[str, Dict[str, Any]]] = None
    ) -> None:
        """
        Register shadow nodes in execution context so they appear as executed nodes.
        
        This adds shadow nodes to the workflow's node_results, making them visible
        in the execution UI as completed nodes.
        """
        try:
            # Get execution context reference (where node_results are stored)
            execution_data = self._get_execution_data_ref()
            if not hasattr(self, 'execution') or not self.execution:
                logger.warning("[AI Agent Shadow] No execution context available for registering shadow nodes")
                return
            
            # Add AI Model as executed node
            model_result = [[NodeExecutionData(json_data=model_data, binary_data=None)]]
            self.execution.node_results[model_node_name] = model_result
            self.execution.completed_nodes.add(model_node_name)
            #logger.info(f"[AI Agent Shadow] ✓ Registered {model_node_name} as executed")
            
            # Add Memory as executed node (if used)
            if memory_node_name and memory_data:
                memory_result = [[NodeExecutionData(json_data=memory_data, binary_data=None)]]
                self.execution.node_results[memory_node_name] = memory_result
                self.execution.completed_nodes.add(memory_node_name)
                #logger.info(f"[AI Agent Shadow] ✓ Registered {memory_node_name} as executed")
            
            # Add tool nodes as executed
            for node_name, node_data in tool_shadows.items():
                tool_result = [[NodeExecutionData(json_data=node_data.get("output", {}), binary_data=None)]]
                self.execution.node_results[node_name] = tool_result
                self.execution.completed_nodes.add(node_name)
                #logger.info(f"[AI Agent Shadow] ✓ Registered {node_name} as executed")
            
            # Add embedding providers as executed
            if embedding_shadows:
                for emb_node_name, emb_data in embedding_shadows.items():
                    emb_result = [[NodeExecutionData(json_data=emb_data, binary_data=None)]]
                    self.execution.node_results[emb_node_name] = emb_result
                    self.execution.completed_nodes.add(emb_node_name)
            
            total = 1 + len(tool_shadows) + (1 if memory_node_name else 0) + len(embedding_shadows or {})
            #logger.info(f"[AI Agent Shadow] ✓ Registered {total} shadow nodes as executed")
            
        except Exception as e:
            logger.error(f"[AI Agent Shadow] ✗ Failed to register shadow nodes as executed: {e}", exc_info=True)

    # ==================== LangChain Runnable Integration ====================
    
    def get_runnable(self, item_index: int = 0) -> AgentRunnable:
        """
        Get LangChain-compatible AgentRunnable for LCEL composition.
        
        This method wraps the AI Agent's orchestration logic as a Runnable, enabling:
        - Composition with other Runnables using LCEL (|)
        - Integration with LangChain tools and chains
        - Batch processing and streaming (when available)
        
        Args:
            item_index: Index of the input item to use for configuration (default: 0)
            
        Returns:
            AgentRunnable: A Runnable that executes the agent orchestration
            
        Example:
            # Get the agent as a Runnable
            agent = agent_node.get_runnable()
            
            # Compose with other Runnables
            chain = agent | output_parser
            
            # Invoke directly
            result = agent.invoke({
                "user_input": "What's the weather?"
            })
        """
        
        # Get the chat model node
        model_nodes = ConnectionResolver.get_upstream_nodes(
            self.workflow, self.node_data.name, "ai_model"
        )
        if not model_nodes:
            raise ValueError("AI Agent requires a connected chat model node")
        
        model_node = model_nodes[0]
        model_node_instance = self._dyn_import_node_class_from_type(model_node.type)
        model_node_instance = model_node_instance(
            workflow=self.workflow,
            node_data=model_node,
            execution=getattr(self, "execution", None),
            item_index=item_index
        )
        
        # Get the chat model Runnable from the model node
        chat_model = model_node_instance.get_runnable(item_index=item_index)
        
        # Get tools (if any)
        tools_runnable = None
        tool_nodes = ConnectionResolver.get_upstream_nodes(
            self.workflow, self.node_data.name, "ai_tool"
        )
        
        if tool_nodes:
            # Prepare tools using ToolManager
            prepared_tools = self.tool_manager.prepare(
                item_index=item_index,
                upstream_tool_nodes=tool_nodes
            )
            
            if prepared_tools:
                # Import ToolCollectionRunnable here to avoid circular imports
                from utils.langchain_tools import ToolCollectionRunnable
                
                # Convert prepared tools to ToolCollectionRunnable
                tools_runnable = ToolCollectionRunnable(
                    tools={t["name"]: t for t in prepared_tools},
                    name="agent_tools"
                )
        
        # Get memory (if any)
        memory_runnable = None
        memory_nodes = ConnectionResolver.get_upstream_nodes(
            self.workflow, self.node_data.name, "ai_memory"
        )
        
        if memory_nodes:
            memory_node = memory_nodes[0]
            memory_node_instance = self._dyn_import_node_class_from_type(memory_node.type)
            memory_node_instance = memory_node_instance(
                workflow=self.workflow,
                node_data=memory_node,
                execution=getattr(self, "execution", None),
                item_index=item_index
            )
            
            # Check if memory node has get_runnable method
            if hasattr(memory_node_instance, "get_runnable"):
                memory_runnable = memory_node_instance.get_runnable(item_index=item_index)
        
        # Get agent parameters
        params = self.get_parameters(item_index=item_index)
        options = params.get("options", {})
        
        system_message = options.get("systemMessage", 
            "You are a helpful AI assistant. Use the available tools when needed to provide accurate responses."
        )
        max_iterations = options.get("maxIterations", 5)
        return_intermediate_steps = options.get("returnIntermediateSteps", False)
        
        # Create the AgentRunnable
        agent = AgentRunnable(
            chat_model=chat_model,
            system_message=system_message,
            max_iterations=max_iterations,
            return_intermediate_steps=return_intermediate_steps
        )
        
        # Attach tools if available
        if tools_runnable:
            agent = agent.with_tools(tools_runnable)
        
        # Attach memory if available
        if memory_runnable:
            agent = agent.with_memory(memory_runnable)
        
        # NOTE: Registry cleanup removed - use managed_runnable() context manager instead
        # For manual registration, call RunnableRegistry.register(agent) explicitly
        # See utils.runnable_helpers.managed_runnable for automatic lifecycle management
        
        return agent
