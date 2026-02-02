"""
Workflow Executor - Sync DAG execution engine.

Executes a compiled workflow graph synchronously,
respecting node dependencies and error handling.

SYNC-CELERY SAFE: All execution is synchronous.
"""

from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol, Set, Type

from .models import WorkflowDefinition, parse_workflow
from .graph import CompiledGraph, CompiledNode, NodeRunResult, NodeStatus


logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    """Overall workflow execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"  # Some nodes succeeded, some failed


@dataclass
class WorkflowResult:
    """
    Result of workflow execution.
    """
    workflow_id: str
    workflow_name: str
    status: WorkflowStatus
    node_results: Dict[str, NodeRunResult] = field(default_factory=dict)
    output_data: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    duration_ms: float = 0
    
    @property
    def is_success(self) -> bool:
        return self.status == WorkflowStatus.SUCCESS
    
    @property
    def is_error(self) -> bool:
        return self.status == WorkflowStatus.ERROR


class NodeExecutorProtocol(Protocol):
    """Protocol for node executors."""
    
    def execute_node(
        self,
        node_type: str,
        type_version: int,
        parameters: Dict[str, Any],
        credentials: Dict[str, Any],
        input_data: List[Dict[str, Any]],
    ) -> List[List[Dict[str, Any]]]:
        """
        Execute a node.
        
        Args:
            node_type: Node type identifier
            type_version: Node type version
            parameters: Node parameters
            credentials: Node credentials
            input_data: Input items from upstream
            
        Returns:
            Output data: List[List[Dict]] - branches of items
        """
        ...


class DefaultNodeExecutor:
    """
    Default node executor that uses a registry to find nodes.
    """
    
    def __init__(
        self, 
        node_registry: Optional[Dict[str, Type]] = None,
        credential_store: Optional[Dict[str, Dict[str, Any]]] = None,
    ):
        """
        Initialize executor.
        
        Args:
            node_registry: Map of node_type -> node class
            credential_store: Map of credential_name -> credential dict
        """
        self._registry = node_registry or {}
        self._credentials = credential_store or {}
    
    def register_node(self, node_type: str, node_class: Type) -> None:
        """Register a node class."""
        self._registry[node_type] = node_class
    
    def set_credentials(self, name: str, credentials: Dict[str, Any]) -> None:
        """Set credentials for use by nodes."""
        self._credentials[name] = credentials
    
    def execute_node(
        self,
        node_type: str,
        type_version: int,
        parameters: Dict[str, Any],
        credentials: Dict[str, Any],
        input_data: List[Dict[str, Any]],
    ) -> List[List[Dict[str, Any]]]:
        """Execute a node by looking it up in the registry."""
        # Import here to avoid circular imports
        from src.node_sdk.basenode import BaseNode, NodeExecutionContext
        
        if node_type not in self._registry:
            raise ValueError(f"Unknown node type: {node_type}")
        
        node_class = self._registry[node_type]
        node: BaseNode = node_class()
        
        # Resolve credentials
        resolved_creds: Dict[str, Dict[str, Any]] = {}
        for cred_type, cred_ref in credentials.items():
            if isinstance(cred_ref, str) and cred_ref in self._credentials:
                resolved_creds[cred_type] = self._credentials[cred_ref]
            elif isinstance(cred_ref, dict):
                resolved_creds[cred_type] = cred_ref
        
        # Create execution context
        context = NodeExecutionContext(
            parameters=parameters,
            credentials=resolved_creds,
            input_data=input_data,
        )
        
        # Execute
        node.set_context(context)
        return node.execute()


class WorkflowExecutor:
    """
    Sync workflow executor.
    
    Executes a workflow DAG synchronously, respecting:
    - Node dependencies (topological order)
    - Error handling (continue_on_fail)
    - Disabled nodes (skip)
    
    SYNC-CELERY SAFE: All execution is synchronous.
    
    Usage:
        executor = WorkflowExecutor(node_executor=MyNodeExecutor())
        result = executor.execute(workflow_definition)
    """
    
    def __init__(
        self,
        node_executor: Optional[NodeExecutorProtocol] = None,
        max_iterations: int = 1000,
    ):
        """
        Initialize executor.
        
        Args:
            node_executor: Node executor implementation
            max_iterations: Safety limit for execution iterations
        """
        self._node_executor = node_executor or DefaultNodeExecutor()
        self._max_iterations = max_iterations
    
    def execute(
        self, 
        workflow: WorkflowDefinition | Dict[str, Any],
        input_data: Optional[List[Dict[str, Any]]] = None,
    ) -> WorkflowResult:
        """
        Execute a workflow.
        
        Args:
            workflow: Workflow definition or JSON dict
            input_data: Optional input data for start nodes
            
        Returns:
            WorkflowResult with execution outcome
        """
        start_time = time.perf_counter()
        
        # Parse if dict
        if isinstance(workflow, dict):
            workflow = parse_workflow(workflow)
        
        # Compile workflow
        try:
            graph = CompiledGraph(workflow)
        except ValueError as e:
            return WorkflowResult(
                workflow_id=workflow.id or "unknown",
                workflow_name=workflow.name,
                status=WorkflowStatus.ERROR,
                error=f"Compilation failed: {e}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )
        
        # Execute
        result = self._execute_graph(graph, input_data)
        result.duration_ms = (time.perf_counter() - start_time) * 1000
        
        return result
    
    def _execute_graph(
        self,
        graph: CompiledGraph,
        input_data: Optional[List[Dict[str, Any]]] = None,
    ) -> WorkflowResult:
        """Execute compiled graph."""
        completed: Set[str] = set()
        results: Dict[str, NodeRunResult] = {}
        has_errors = False
        
        # Default input data
        if input_data is None:
            input_data = [{"json": {}}]
        
        # Store input for start nodes
        start_node_input = input_data
        
        # First, mark all disabled nodes as skipped
        for node_name in graph.node_names:
            node = graph.get_node(node_name)
            if node and node.disabled:
                graph.mark_skipped(node_name)
                completed.add(node_name)
                results[node_name] = NodeRunResult(
                    node_name=node_name,
                    status=NodeStatus.SKIPPED,
                )
        
        iteration = 0
        while iteration < self._max_iterations:
            iteration += 1
            
            # Get ready nodes
            ready = graph.get_ready_nodes(completed)
            
            if not ready:
                # No more nodes to execute
                break
            
            # Execute each ready node
            for node_name in ready:
                node = graph.get_node(node_name)
                if not node:
                    continue
                
                # Get input data
                if not node.upstream:
                    # Start node - use provided input
                    node_input = start_node_input
                else:
                    # Non-start node - collect from upstream
                    node_input = graph.get_input_data(node_name, results)
                
                # Execute node
                logger.debug(f"Executing node: {node_name} ({node.node_type})")
                graph.mark_running(node_name)
                
                result = self._execute_node(node, node_input)
                
                # Record result
                results[node_name] = result
                graph.mark_complete(node_name, result)
                completed.add(node_name)
                
                if result.is_error:
                    has_errors = True
                    if not node.continue_on_fail:
                        # Stop execution on error
                        logger.error(f"Node {node_name} failed: {result.error}")
                        # Skip downstream nodes
                        self._mark_downstream_skipped(graph, node_name, completed, results)
                
                logger.debug(f"Node {node_name} completed: {result.status.value}")
        
        # Determine overall status
        if has_errors:
            # Check if any nodes succeeded
            success_count = sum(1 for r in results.values() if r.is_success)
            if success_count > 0:
                status = WorkflowStatus.PARTIAL
            else:
                status = WorkflowStatus.ERROR
        else:
            status = WorkflowStatus.SUCCESS
        
        # Collect output from terminal nodes (no downstream)
        output_data = self._collect_output(graph, results)
        
        # Get error message from first failed node
        error_msg = None
        for r in results.values():
            if r.is_error:
                error_msg = r.error
                break
        
        return WorkflowResult(
            workflow_id=graph.workflow_id,
            workflow_name=graph.workflow_name,
            status=status,
            node_results=results,
            output_data=output_data,
            error=error_msg,
        )
    
    def _execute_node(
        self,
        node: CompiledNode,
        input_data: List[Dict[str, Any]],
    ) -> NodeRunResult:
        """Execute a single node."""
        start_time = time.perf_counter()
        
        try:
            output = self._node_executor.execute_node(
                node_type=node.node_type,
                type_version=node.type_version,
                parameters=node.parameters,
                credentials=node.credentials,
                input_data=input_data,
            )
            
            duration = (time.perf_counter() - start_time) * 1000
            
            return NodeRunResult(
                node_name=node.name,
                status=NodeStatus.SUCCESS,
                output_data=output,
                duration_ms=duration,
            )
            
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            
            return NodeRunResult(
                node_name=node.name,
                status=NodeStatus.ERROR,
                error=str(e),
                error_traceback=traceback.format_exc(),
                duration_ms=duration,
            )
    
    def _mark_downstream_skipped(
        self,
        graph: CompiledGraph,
        failed_node: str,
        completed: Set[str],
        results: Dict[str, NodeRunResult],
    ) -> None:
        """Mark all downstream nodes as skipped after a failure."""
        to_skip = set()
        queue = list(graph.get_node(failed_node).downstream if graph.get_node(failed_node) else [])
        
        while queue:
            name = queue.pop(0)
            if name in completed or name in to_skip:
                continue
            
            to_skip.add(name)
            node = graph.get_node(name)
            if node:
                queue.extend(node.downstream)
        
        for name in to_skip:
            graph.mark_skipped(name)
            completed.add(name)
            results[name] = NodeRunResult(
                node_name=name,
                status=NodeStatus.SKIPPED,
            )
    
    def _collect_output(
        self,
        graph: CompiledGraph,
        results: Dict[str, NodeRunResult],
    ) -> List[Dict[str, Any]]:
        """Collect output from terminal nodes."""
        output = []
        
        for name in graph.node_names:
            node = graph.get_node(name)
            if not node:
                continue
            
            # Terminal node = no downstream
            if not node.downstream:
                result = results.get(name)
                if result and result.output_data:
                    # Flatten branches
                    for branch in result.output_data:
                        output.extend(branch)
        
        return output


__all__ = [
    "WorkflowExecutor",
    "WorkflowResult",
    "WorkflowStatus",
    "DefaultNodeExecutor",
    "NodeExecutorProtocol",
]
