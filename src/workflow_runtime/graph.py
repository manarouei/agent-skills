"""
Compiled Graph - Executable workflow DAG.

Takes a WorkflowDefinition and compiles it into an executable graph
with topological ordering for sync execution.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from .models import WorkflowDefinition, WorkflowNode


logger = logging.getLogger(__name__)


class NodeStatus(str, Enum):
    """Status of a node during execution."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class NodeRunResult:
    """
    Result of running a single node.
    """
    node_name: str
    status: NodeStatus
    output_data: List[List[Dict[str, Any]]] = field(default_factory=list)
    error: Optional[str] = None
    error_traceback: Optional[str] = None
    duration_ms: float = 0
    
    @property
    def is_success(self) -> bool:
        return self.status == NodeStatus.SUCCESS
    
    @property
    def is_error(self) -> bool:
        return self.status == NodeStatus.ERROR


@dataclass
class CompiledNode:
    """
    A node in the compiled graph with execution metadata.
    """
    name: str
    node_type: str
    type_version: int
    parameters: Dict[str, Any]
    credentials: Dict[str, Any]
    disabled: bool
    continue_on_fail: bool
    
    # Computed during compilation
    upstream: List[str] = field(default_factory=list)
    downstream: List[str] = field(default_factory=list)
    
    # Runtime state
    status: NodeStatus = NodeStatus.PENDING
    result: Optional[NodeRunResult] = None
    
    @classmethod
    def from_workflow_node(
        cls, 
        node: WorkflowNode,
        upstream: List[str],
        downstream: List[str],
    ) -> "CompiledNode":
        """Create from workflow node."""
        return cls(
            name=node.name,
            node_type=node.type,
            type_version=node.type_version,
            parameters=node.parameters,
            credentials=node.credentials,
            disabled=node.disabled,
            continue_on_fail=node.continue_on_fail,
            upstream=upstream,
            downstream=downstream,
        )


class CompiledGraph:
    """
    Compiled workflow ready for execution.
    
    Contains:
    - Nodes with their connections
    - Topological order for sync execution
    - Methods for traversing the graph
    
    SYNC-CELERY SAFE: No async operations.
    """
    
    def __init__(self, workflow: WorkflowDefinition):
        """
        Compile workflow into executable graph.
        
        Args:
            workflow: Source workflow definition
        """
        self.workflow_id = workflow.id or "unnamed"
        self.workflow_name = workflow.name
        self._workflow = workflow
        
        # Build node map with connections
        self._nodes: Dict[str, CompiledNode] = {}
        self._build_nodes()
        
        # Compute execution order
        self._execution_order: List[str] = []
        self._compute_execution_order()
    
    def _build_nodes(self) -> None:
        """Build compiled nodes with connections."""
        for node in self._workflow.nodes:
            upstream = self._workflow.get_upstream_nodes(node.name)
            downstream = self._workflow.get_downstream_nodes(node.name)
            
            self._nodes[node.name] = CompiledNode.from_workflow_node(
                node=node,
                upstream=upstream,
                downstream=downstream,
            )
    
    def _compute_execution_order(self) -> None:
        """
        Compute topological order for execution.
        
        Uses Kahn's algorithm for stable ordering.
        """
        # Calculate in-degree for each node
        in_degree: Dict[str, int] = {name: 0 for name in self._nodes}
        for name, node in self._nodes.items():
            for upstream_name in node.upstream:
                if upstream_name in in_degree:
                    in_degree[name] += 1
        
        # Start with nodes that have no dependencies
        queue = [name for name, degree in in_degree.items() if degree == 0]
        order = []
        
        while queue:
            # Sort for deterministic order
            queue.sort()
            node_name = queue.pop(0)
            order.append(node_name)
            
            # Reduce in-degree for downstream nodes
            node = self._nodes[node_name]
            for downstream_name in node.downstream:
                if downstream_name in in_degree:
                    in_degree[downstream_name] -= 1
                    if in_degree[downstream_name] == 0:
                        queue.append(downstream_name)
        
        if len(order) != len(self._nodes):
            # Cycle detected
            remaining = set(self._nodes.keys()) - set(order)
            raise ValueError(f"Workflow has cycles involving: {remaining}")
        
        self._execution_order = order
    
    @property
    def execution_order(self) -> List[str]:
        """Get nodes in execution order."""
        return self._execution_order.copy()
    
    @property
    def node_names(self) -> List[str]:
        """Get all node names."""
        return list(self._nodes.keys())
    
    def get_node(self, name: str) -> Optional[CompiledNode]:
        """Get compiled node by name."""
        return self._nodes.get(name)
    
    def get_start_nodes(self) -> List[str]:
        """Get entry point node names."""
        return [
            name for name, node in self._nodes.items()
            if not node.upstream and not node.disabled
        ]
    
    def get_ready_nodes(self, completed: Set[str]) -> List[str]:
        """
        Get nodes ready to execute.
        
        A node is ready when all its upstream nodes are in completed set.
        """
        ready = []
        for name, node in self._nodes.items():
            if node.disabled:
                continue
            if node.status != NodeStatus.PENDING:
                continue
            
            # Check all upstream nodes are completed
            all_upstream_done = all(
                up in completed or self._nodes[up].disabled
                for up in node.upstream
                if up in self._nodes
            )
            if all_upstream_done:
                ready.append(name)
        
        return ready
    
    def mark_running(self, name: str) -> None:
        """Mark node as running."""
        if name in self._nodes:
            self._nodes[name].status = NodeStatus.RUNNING
    
    def mark_complete(self, name: str, result: NodeRunResult) -> None:
        """Mark node as complete with result."""
        if name in self._nodes:
            self._nodes[name].status = result.status
            self._nodes[name].result = result
    
    def mark_skipped(self, name: str) -> None:
        """Mark node as skipped."""
        if name in self._nodes:
            self._nodes[name].status = NodeStatus.SKIPPED
    
    def get_input_data(self, node_name: str, completed_results: Dict[str, NodeRunResult]) -> List[Dict[str, Any]]:
        """
        Get input data for a node from upstream results.
        
        Collects output from all upstream nodes and merges them.
        """
        node = self._nodes.get(node_name)
        if not node:
            return []
        
        # If no upstream, return empty (trigger node)
        if not node.upstream:
            return [{"json": {}}]  # Single empty item
        
        # Collect outputs from upstream
        input_items = []
        for upstream_name in node.upstream:
            result = completed_results.get(upstream_name)
            if result and result.output_data:
                # Take first branch (main output)
                for branch in result.output_data:
                    input_items.extend(branch)
        
        return input_items if input_items else [{"json": {}}]
    
    def get_results_summary(self) -> Dict[str, Any]:
        """Get summary of execution results."""
        return {
            "workflow_id": self.workflow_id,
            "workflow_name": self.workflow_name,
            "total_nodes": len(self._nodes),
            "status_counts": {
                status.value: sum(1 for n in self._nodes.values() if n.status == status)
                for status in NodeStatus
            },
            "nodes": {
                name: {
                    "status": node.status.value,
                    "error": node.result.error if node.result else None,
                }
                for name, node in self._nodes.items()
            },
        }


__all__ = [
    "CompiledGraph",
    "CompiledNode",
    "NodeRunResult",
    "NodeStatus",
]
