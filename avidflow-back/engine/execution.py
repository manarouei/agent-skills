from typing import Dict, List, Any, Set, Optional
from services.queue import QueueService
from models.node import Node, NodeExecutionData
from models.workflow import WorkflowModel
from collections import deque, defaultdict
from utils.serialization import to_dict_without_binary, deep_serialize
from database.crud import ExecutionCRUD
from database.config import get_sync_session_manual
from nodes import node_definitions

# Langfuse observability (gracefully degrades if not configured)
from observability.langfuse_client import create_node_span, is_langfuse_enabled

import logging


logger = logging.getLogger(__name__)


class ExecutionPlanBuilder:
    def __init__(self, workflow_data: WorkflowModel):
        self.nodes = workflow_data.nodes
        self.connections = workflow_data.connections
        self.node_map = {node.name: node for node in self.nodes}

    def topological_sort(self) -> List[Node]:
        """
        Perform topological sorting of nodes based on their dependencies.
        Returns a list of nodes in execution order.
        """
        # Build dependency graph
        in_degree = defaultdict(int)
        adjacency_list = defaultdict(list)

        # Initialize in-degree for all nodes
        for node in self.nodes:
            in_degree[node.name] = 0

        # Build graph and calculate in-degrees
        for source_name, connection_types in self.connections.items():
            # Only consider 'main' connections for execution order
            if "main" in connection_types:
                for conn_array in connection_types["main"]:
                    if conn_array:
                        for conn in conn_array:
                            target_name = conn.node
                            adjacency_list[source_name].append(target_name)
                            in_degree[target_name] += 1

        # Find nodes with no incoming edges (start nodes)
        queue = deque()
        for node in self.nodes:
            if in_degree[node.name] == 0 or node.is_start:
                queue.append(node.name)

        sorted_nodes = []

        while queue:
            current_node_name = queue.popleft()
            current_node = self.node_map[current_node_name]
            sorted_nodes.append(current_node)

            # Reduce in-degree for adjacent nodes
            for neighbor in adjacency_list[current_node_name]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(sorted_nodes) != len(self.nodes):
            remaining_nodes = set(node.name for node in self.nodes) - set(
                node.name for node in sorted_nodes
            )
            raise ValueError(
                f"Circular dependency detected in workflow: {remaining_nodes}"
            )

        return sorted_nodes


class WorkflowExecutionContext:
    """
    Maintains state during workflow execution.
    
    Langfuse Integration:
    - Holds the parent trace context for creating per-node spans
    - Propagates langfuse_trace_id to all child components
    """

    def __init__(
        self,
        workflow: WorkflowModel,
        execution_id: str,
        pub_sub: bool = False,
        primary_result: Optional[Dict[str, Any]] = None,
        langfuse_trace_ctx: Optional[Any] = None,  # TraceContext from observability module
    ):
        self.workflow = workflow
        self.execution_id = execution_id
        self.pub_sub = pub_sub
        self.primary_result = primary_result or {}
        self.node_results: Dict[str, Any] = {}
        self.completed_nodes: Set[str] = set()
        # Langfuse trace context for creating per-node spans
        self.langfuse_trace_ctx = langfuse_trace_ctx
    
    @property
    def langfuse_trace_id(self) -> Optional[str]:
        """Get the Langfuse trace ID if available."""
        if self.langfuse_trace_ctx:
            return getattr(self.langfuse_trace_ctx, 'trace_id', None)
        return None

    def get_node_input_data(self, node_name: str) -> Dict[str, Any]:
        """Get input data for a node from previously executed nodes"""
        input_data = self.node_results

        # If no dependencies and this is a start node, use primary result
        if node_name in [node.name for node in self.workflow.nodes if node.is_start]:
            input_data = self.primary_result

        return input_data


class WorkflowExecutor:
    """Executes workflow nodes sequentially"""

    def __init__(self, context: WorkflowExecutionContext):
        self.context = context
        self.queue_service = QueueService() if context.pub_sub else None



    def execute_nodes(self, sorted_nodes: List[Node]) -> Dict[str, Any]:
        """Execute nodes in topological order (branch-aware)"""
        
        # Log node event publishing mode for debugging
        if not self.context.pub_sub:
            logger.info("[Executor] Webhook mode: Skipping per-node events (pub_sub=False)")
        else:
            logger.info("[Executor] WebSocket mode: Publishing per-node events (pub_sub=True)")

        # Start nodes detection (same as previous minimal branch logic)
        start_nodes = {n.name for n in self.context.workflow.nodes if getattr(n, "is_start", False)}
        if not start_nodes:
            in_degree = {n.name: 0 for n in self.context.workflow.nodes}
            for src, c_types in (self.context.workflow.connections or {}).items():
                if "main" in c_types:
                    for arr in c_types["main"]:
                        for conn in (arr or []):
                            in_degree[conn.node] = in_degree.get(conn.node, 0) + 1
            start_nodes = {name for name, deg in in_degree.items() if deg == 0}

        active_nodes = set(start_nodes)

        final_result = None
        connections = self.context.workflow.connections or {}

        for node in sorted_nodes:
            if node.name not in active_nodes and not node.is_start:
                continue

            try:
                node_result = self.execute_single_node(node)

                # Store raw node_result (list[list[NodeExecutionData]]) just like original
                self.context.node_results[node.name] = node_result
                self.context.completed_nodes.add(node.name)
                
                # Branch activation: only outputs with data
                if isinstance(node_result, list):
                    main_conns = (connections.get(node.name, {}) or {}).get("main", [])
                    for out_index, out_items in enumerate(node_result):
                        size = len(out_items) if isinstance(out_items, list) else 0
                        if size == 0:
                            logger.debug("Executor - Not activating downstream from %s output %d (empty)",
                                         node.name, out_index)
                            continue
                        if out_index < len(main_conns) and main_conns[out_index]:
                            for conn in main_conns[out_index]:
                                active_nodes.add(conn.node)
                                logger.debug("Executor - Activated node %s via %s output %d (%d items)",
                                             conn.node, node.name, out_index, size)

                # Match legacy logic: skip final_result update only if node_result == [[]]
                if node_result == [[]]:
                    continue
                final_result = node_result

                # Legacy queue publish logic (use first element of serialized node_result)
                # OPTIMIZATION: Skip node events for webhooks (pub_sub=False)
                # WebSocket users (pub_sub=True) need real-time updates, webhooks only need final result
                if self.queue_service and self.context.pub_sub:
                    try:
                        serialized = to_dict_without_binary(node_result)
                        first_part = serialized[0] if serialized and len(serialized) > 0 else {}
                        # Include langfuse_trace_id in message for frontend deep-linking
                        node_message = {
                            "event": "node_completed",
                            "workflow_id": str(self.context.workflow.id),
                            "execution_id": self.context.execution_id,
                            "node_name": node.name,
                            "data": first_part,
                        }
                        if self.context.langfuse_trace_id:
                            node_message["langfuse_trace_id"] = self.context.langfuse_trace_id
                        
                        self.queue_service.publish_sync(
                            queue_name="workflow_updates",
                            message=node_message,
                        )
                    except Exception as e:
                        logger.debug("Executor - Queue publish failed for %s: %s", node.name, e)

            except Exception as e:
                error_msg = str(e)
                logger.error("Executor - Error in node %s: %s", node.name, error_msg)
                # Always publish errors (regardless of pub_sub) for monitoring/alerting
                if self.queue_service:
                    try:
                        # Include langfuse_trace_id in error message for debugging
                        error_message = {
                            "event": "node_error",
                            "workflow_id": str(self.context.workflow.id),
                            "execution_id": self.context.execution_id,
                            "node_name": node.name,
                            "error": error_msg,
                        }
                        if self.context.langfuse_trace_id:
                            error_message["langfuse_trace_id"] = self.context.langfuse_trace_id
                        
                        self.queue_service.publish_sync(
                            queue_name="workflow_updates",
                            message=error_message,
                        )
                    except Exception:
                        pass
                
                # Include langfuse_trace_id in error data for debugging
                error_data = {
                    "error": error_msg,
                    "nodes_results": {
                        k: to_dict_without_binary(v)
                        for k, v in self.context.node_results.items()
                    },
                    "error_node_name": node.name,
                }
                if self.context.langfuse_trace_id:
                    error_data["langfuse_trace_id"] = self.context.langfuse_trace_id
                
                with get_sync_session_manual() as session:
                    ExecutionCRUD.update_execution_status_sync(
                        session,
                        self.context.execution_id,
                        "error",
                        finished=True,
                        data=error_data,
                    )
                return {
                    "status": "error",
                    "error_node_name": node.name,
                    "error_message": error_msg,
                    "all_results": self.context.node_results,
                }

        return {
            "status": "completed",
            "all_results": self.context.node_results,
            "final_result": final_result,
        }

    def execute_single_node(self, node: Node) -> List[List[NodeExecutionData]]:
        """
        Execute a single node and return its result.
        
        Langfuse Integration:
        - Creates a span per node execution, nested under the workflow trace
        - Captures input/output previews and errors
        - Span name format: "node:<node_name>"
        """

        # Get input data for this node
        input_data = self.context.get_node_input_data(node.name)

        # Get node executor
        node_type = node.type
        node_define = node_definitions.get(node_type)

        if not node_define:
            raise ValueError(f"Node executor for type '{node_type}' not found.")

        # Create and execute node
        node_class_def = node_define.get("node_class")
        if not node_class_def:
            raise ValueError(f"Node class for type '{node_type}' not found.")

        node_instance = node_class_def(node, self.context.workflow, input_data)
        node_instance.set_execution_id(self.context.execution_id)
        
        # CRITICAL: Pass execution context to node for pub_sub access
        # Must be set AFTER __init__ but BEFORE any execute() calls
        # Always overwrite to ensure context is propagated (fixes issue where execution=None)
        node_instance.execution = self.context

        # Wrap node execution in a Langfuse span for observability
        with create_node_span(
            name=f"node:{node.name}",
            node_type=node_type,
            workflow_id=str(self.context.workflow.id),
            execution_id=self.context.execution_id,
            parent_trace=self.context.langfuse_trace_ctx,
            metadata={
                "is_start": node.is_start,
                "is_end": node.is_end,
            },
            input_data=self._safe_serialize_for_span(input_data),
        ) as node_span:
            try:
                if node_define.get("type") == "trigger":
                    execute_result = node_instance.trigger()
                elif node_define.get("type") == "regular":
                    execute_result = node_instance.execute()
                else:
                    raise ValueError(f"Unknown node type: {node_define.get('type')}")
                
                # Update span with output preview (keep it small for performance)
                if node_span and execute_result:
                    output_preview = self._safe_serialize_for_span(execute_result)
                    node_span.update(output={"preview": output_preview})
                
                return execute_result
                
            except Exception as e:
                # Update span with error info before re-raising
                if node_span:
                    node_span.update(level="ERROR", output={"error": str(e)})
                raise
    
    def _safe_serialize_for_span(self, data: Any, max_size: int = 10000) -> Any:
        """
        Safely serialize data for Langfuse span input/output.
        
        Truncates large payloads to avoid performance issues.
        """
        try:
            serialized = deep_serialize(data)
            # Convert to string to check size
            import json
            as_str = json.dumps(serialized) if not isinstance(serialized, str) else serialized
            if len(as_str) > max_size:
                return {"_truncated": True, "preview": as_str[:max_size] + "..."}
            return serialized
        except Exception:
            return {"_serialization_error": True}
