"""
Workflow Models - JSON structures for workflow definitions.

These models match the n8n workflow JSON format.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class WorkflowConnection(BaseModel):
    """
    Connection between two nodes.
    
    Example: {"node": "HTTP Request", "type": "main", "index": 0}
    """
    model_config = ConfigDict(extra="allow")
    
    node: str = Field(..., description="Target node name")
    type: str = Field("main", description="Connection type")
    index: int = Field(0, description="Output index")


class WorkflowNodeConnections(BaseModel):
    """
    Node connection mapping.
    
    Maps output types to lists of connections.
    Example: {"main": [[{"node": "NextNode", "type": "main", "index": 0}]]}
    """
    model_config = ConfigDict(extra="allow")
    
    main: List[List[WorkflowConnection]] = Field(default_factory=list)


class WorkflowNodePosition(BaseModel):
    """Node position in the canvas."""
    x: float = 0
    y: float = 0


class WorkflowNode(BaseModel):
    """
    A node in a workflow.
    
    Matches n8n workflow JSON node format.
    """
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    
    # Required
    name: str = Field(..., description="Node name (unique within workflow)")
    type: str = Field(..., description="Node type (e.g., 'n8n-nodes-base.telegram')")
    
    # Optional
    type_version: int = Field(1, alias="typeVersion", description="Node type version")
    position: WorkflowNodePosition = Field(default_factory=WorkflowNodePosition)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    credentials: Dict[str, Any] = Field(default_factory=dict)
    disabled: bool = Field(False, description="If true, node is skipped")
    continue_on_fail: bool = Field(False, alias="continueOnFail")
    notes: Optional[str] = Field(None, description="Node notes")
    
    @property
    def id(self) -> str:
        """Node ID is its name."""
        return self.name


class WorkflowConnections(BaseModel):
    """
    Full workflow connection map.
    
    Format: {source_node_name: {output_type: [[connections]]}}
    """
    model_config = ConfigDict(extra="allow")
    
    # Dynamic keys - source node names map to their connections
    # We use extra="allow" to handle arbitrary node names


class WorkflowSettings(BaseModel):
    """Workflow-level settings."""
    model_config = ConfigDict(extra="allow")
    
    save_data_error_execution: str = Field("all", alias="saveDataErrorExecution")
    save_data_success_execution: str = Field("all", alias="saveDataSuccessExecution")
    save_manual_executions: bool = Field(True, alias="saveManualExecutions")
    timezone: str = Field("UTC")
    execution_timeout: int = Field(-1, alias="executionTimeout", description="-1 = no timeout")


class WorkflowDefinition(BaseModel):
    """
    Complete workflow definition.
    
    Matches n8n workflow JSON format.
    """
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    
    # Metadata
    id: Optional[str] = Field(None, description="Workflow ID")
    name: str = Field("Unnamed Workflow", description="Workflow name")
    active: bool = Field(False, description="Is workflow active?")
    
    # Structure
    nodes: List[WorkflowNode] = Field(default_factory=list)
    connections: Dict[str, Dict[str, List[List[Dict[str, Any]]]]] = Field(
        default_factory=dict,
        description="Node connections: {source: {type: [[{node, type, index}]]}}"
    )
    
    # Settings
    settings: WorkflowSettings = Field(default_factory=WorkflowSettings)
    
    # Optional
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")
    tags: List[str] = Field(default_factory=list)
    
    def get_node(self, name: str) -> Optional[WorkflowNode]:
        """Get node by name."""
        for node in self.nodes:
            if node.name == name:
                return node
        return None
    
    def get_start_nodes(self) -> List[WorkflowNode]:
        """
        Get nodes that have no incoming connections (entry points).
        """
        # Collect all nodes that are targets of connections
        target_nodes: set[str] = set()
        for source_name, outputs in self.connections.items():
            for output_type, branches in outputs.items():
                for branch in branches:
                    for conn in branch:
                        if "node" in conn:
                            target_nodes.add(conn["node"])
        
        # Return nodes that are not targets
        return [
            node for node in self.nodes
            if node.name not in target_nodes and not node.disabled
        ]
    
    def get_downstream_nodes(self, node_name: str) -> List[str]:
        """Get names of nodes connected to this node's outputs."""
        downstream = []
        if node_name in self.connections:
            for output_type, branches in self.connections[node_name].items():
                for branch in branches:
                    for conn in branch:
                        if "node" in conn:
                            downstream.append(conn["node"])
        return downstream
    
    def get_upstream_nodes(self, node_name: str) -> List[str]:
        """Get names of nodes that connect to this node."""
        upstream = []
        for source_name, outputs in self.connections.items():
            for output_type, branches in outputs.items():
                for branch in branches:
                    for conn in branch:
                        if conn.get("node") == node_name:
                            upstream.append(source_name)
        return upstream


def parse_workflow(data: Dict[str, Any]) -> WorkflowDefinition:
    """Parse workflow JSON into WorkflowDefinition."""
    return WorkflowDefinition.model_validate(data)


__all__ = [
    "WorkflowDefinition",
    "WorkflowNode",
    "WorkflowConnection",
    "WorkflowNodeConnections",
    "WorkflowSettings",
    "parse_workflow",
]
