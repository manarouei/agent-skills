"""
Node Registry Models - Metadata structures for nodes and node packs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel, ConfigDict, Field


class NodeDefinition(BaseModel):
    """
    Metadata about a registered node.
    
    Contains everything needed to instantiate and use a node.
    """
    model_config = ConfigDict(extra="allow")
    
    # Identity
    node_type: str = Field(..., description="Unique node type identifier")
    version: int = Field(1, description="Node version")
    
    # Display
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field("", description="Node description")
    icon: str = Field("file:icon.svg", description="Node icon")
    group: List[str] = Field(default_factory=list, description="Categories")
    
    # Technical
    node_class: Optional[str] = Field(None, description="Fully qualified class name")
    node_pack: Optional[str] = Field(None, description="Source node pack")
    
    # Runtime
    inputs: List[str] = Field(default_factory=lambda: ["main"])
    outputs: List[str] = Field(default_factory=lambda: ["main"])
    credentials: List[Dict[str, Any]] = Field(default_factory=list)
    parameters: List[Dict[str, Any]] = Field(default_factory=list)
    
    @classmethod
    def from_node_class(cls, node_class: Type) -> "NodeDefinition":
        """Create definition from a BaseNode class."""
        # Get attributes from class
        node_type = getattr(node_class, "type", node_class.__name__.lower())
        version = getattr(node_class, "version", 1)
        description = getattr(node_class, "description", {})
        properties = getattr(node_class, "properties", {})
        
        # Handle description as dict (n8n style) or string
        if isinstance(description, dict):
            display_name = description.get("displayName", node_type)
            desc_text = description.get("description", "")
            icon = description.get("icon", "file:icon.svg")
            group = description.get("group", [])
            inputs = description.get("inputs", ["main"])
            outputs = description.get("outputs", ["main"])
            credentials = description.get("credentials", [])
        else:
            display_name = node_type.replace("-", " ").title()
            desc_text = str(description) if description else ""
            icon = "file:icon.svg"
            group = []
            inputs = ["main"]
            outputs = ["main"]
            credentials = []
        
        # Handle properties
        if isinstance(properties, dict):
            parameters = properties.get("parameters", [])
            if not credentials:
                credentials = properties.get("credentials", [])
        else:
            parameters = list(properties) if properties else []
        
        return cls(
            node_type=node_type,
            version=version,
            display_name=display_name,
            description=desc_text,
            icon=icon,
            group=group,
            node_class=f"{node_class.__module__}.{node_class.__name__}",
            inputs=inputs if isinstance(inputs, list) else ["main"],
            outputs=outputs if isinstance(outputs, list) else ["main"],
            credentials=credentials if isinstance(credentials, list) else [],
            parameters=parameters if isinstance(parameters, list) else [],
        )


class NodePackManifest(BaseModel):
    """
    Manifest for a node pack (collection of nodes).
    
    Used for discovery and registration of bundled nodes.
    """
    model_config = ConfigDict(extra="allow")
    
    # Identity
    name: str = Field(..., description="Pack name (e.g., 'n8n-nodes-base')")
    version: str = Field("1.0.0", description="Pack version")
    description: str = Field("", description="Pack description")
    
    # Author
    author: str = Field("", description="Author name")
    license: str = Field("MIT", description="License type")
    
    # Contents
    nodes: List[str] = Field(
        default_factory=list,
        description="List of node types in this pack"
    )
    credentials: List[str] = Field(
        default_factory=list,
        description="List of credential types in this pack"
    )
    
    # Technical
    entry_point: str = Field(
        "",
        description="Module path for node discovery (e.g., 'mypack.nodes')"
    )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NodePackManifest":
        """Create from dictionary."""
        return cls.model_validate(data)


class CredentialDefinition(BaseModel):
    """
    Definition of a credential type.
    """
    model_config = ConfigDict(extra="allow")
    
    name: str = Field(..., description="Credential type name")
    display_name: str = Field(..., description="Human-readable name")
    description: str = Field("", description="Credential description")
    
    # Fields
    properties: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Credential properties/fields"
    )
    
    # Authentication
    auth_type: str = Field("generic", description="Auth type: generic, oauth2, etc.")


__all__ = [
    "NodeDefinition",
    "NodePackManifest",
    "CredentialDefinition",
]
