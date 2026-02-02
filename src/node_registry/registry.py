"""
Node Registry - Central registry for node discovery and instantiation.

Supports multiple discovery methods:
1. Manual registration
2. Entry-points (for plugin node packs)
3. Module scanning
"""

from __future__ import annotations

import importlib
import logging
import sys
from typing import Any, Callable, Dict, Iterator, List, Optional, Type, TYPE_CHECKING

if sys.version_info >= (3, 10):
    from importlib.metadata import entry_points
else:
    from importlib_metadata import entry_points

from .models import NodeDefinition, NodePackManifest


if TYPE_CHECKING:
    from src.node_sdk.basenode import BaseNode


logger = logging.getLogger(__name__)

# Entry point group for node packs
NODE_PACK_ENTRY_POINT = "agent_skills.nodepacks"


class NodeRegistry:
    """
    Central registry for discovering and instantiating nodes.
    
    Nodes can be registered via:
    - register_node(): Manual registration
    - discover_entry_points(): Automatic discovery via entry points
    - register_pack(): Register all nodes from a pack
    
    Usage:
        registry = NodeRegistry()
        registry.discover_entry_points()
        
        # Get a node class
        node_class = registry.get_node_class("n8n-nodes-base.telegram")
        
        # Create instance
        node = registry.create_node("n8n-nodes-base.telegram")
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._nodes: Dict[str, NodeDefinition] = {}
        self._node_classes: Dict[str, Type["BaseNode"]] = {}
        self._packs: Dict[str, NodePackManifest] = {}
        self._discovered = False
    
    def register_node(
        self,
        node_class: Type["BaseNode"],
        node_type: Optional[str] = None,
    ) -> NodeDefinition:
        """
        Register a node class.
        
        Args:
            node_class: BaseNode subclass
            node_type: Override node type (uses class.type if not provided)
            
        Returns:
            NodeDefinition for the registered node
        """
        # Get node type from class if not provided
        if node_type is None:
            node_type = getattr(node_class, "type", node_class.__name__.lower())
        
        # Create definition
        definition = NodeDefinition.from_node_class(node_class)
        definition.node_type = node_type
        
        # Store
        self._nodes[node_type] = definition
        self._node_classes[node_type] = node_class
        
        logger.debug(f"Registered node: {node_type}")
        return definition
    
    def register_pack(
        self,
        manifest: NodePackManifest,
        node_classes: Dict[str, Type["BaseNode"]],
    ) -> None:
        """
        Register a node pack with its nodes.
        
        Args:
            manifest: Pack manifest
            node_classes: Map of node_type -> node class
        """
        self._packs[manifest.name] = manifest
        
        for node_type, node_class in node_classes.items():
            definition = self.register_node(node_class, node_type)
            definition.node_pack = manifest.name
        
        logger.info(f"Registered pack '{manifest.name}' with {len(node_classes)} nodes")
    
    def discover_entry_points(self, force: bool = False) -> int:
        """
        Discover node packs via entry points.
        
        Entry points are defined in pyproject.toml or setup.py:
        
            [project.entry-points."agent_skills.nodepacks"]
            mypack = "mypack:register_nodes"
        
        The entry point should be a function that returns:
        - (manifest, node_classes): Tuple of manifest and node class dict
        - Or just node_classes dict
        
        Args:
            force: Re-discover even if already done
            
        Returns:
            Number of packs discovered
        """
        if self._discovered and not force:
            return len(self._packs)
        
        count = 0
        
        try:
            eps = entry_points(group=NODE_PACK_ENTRY_POINT)
        except TypeError:
            # Older Python/importlib_metadata
            all_eps = entry_points()
            eps = all_eps.get(NODE_PACK_ENTRY_POINT, [])
        
        for ep in eps:
            try:
                register_func = ep.load()
                result = register_func()
                
                if isinstance(result, tuple):
                    manifest, node_classes = result
                    self.register_pack(manifest, node_classes)
                elif isinstance(result, dict):
                    # Just node classes - create default manifest
                    manifest = NodePackManifest(
                        name=ep.name,
                        nodes=list(result.keys()),
                    )
                    self.register_pack(manifest, result)
                
                count += 1
                logger.info(f"Discovered node pack: {ep.name}")
                
            except Exception as e:
                logger.error(f"Failed to load node pack '{ep.name}': {e}")
        
        self._discovered = True
        return count
    
    def discover_module(self, module_path: str) -> int:
        """
        Discover nodes from a module.
        
        Scans module for BaseNode subclasses and registers them.
        
        Args:
            module_path: Module path to import (e.g., 'mypack.nodes')
            
        Returns:
            Number of nodes discovered
        """
        from src.node_sdk.basenode import BaseNode
        
        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            logger.error(f"Failed to import module '{module_path}': {e}")
            return 0
        
        count = 0
        for name in dir(module):
            obj = getattr(module, name)
            if (
                isinstance(obj, type) 
                and issubclass(obj, BaseNode) 
                and obj is not BaseNode
            ):
                self.register_node(obj)
                count += 1
        
        return count
    
    def get_node(self, node_type: str) -> Optional[NodeDefinition]:
        """Get node definition by type."""
        return self._nodes.get(node_type)
    
    def get_node_class(self, node_type: str) -> Optional[Type["BaseNode"]]:
        """Get node class by type."""
        return self._node_classes.get(node_type)
    
    def create_node(self, node_type: str) -> Optional["BaseNode"]:
        """
        Create a node instance.
        
        Args:
            node_type: Node type identifier
            
        Returns:
            Node instance or None if not found
        """
        node_class = self.get_node_class(node_type)
        if node_class:
            return node_class()
        return None
    
    def list_nodes(self) -> List[NodeDefinition]:
        """List all registered nodes."""
        return list(self._nodes.values())
    
    def list_packs(self) -> List[NodePackManifest]:
        """List all registered packs."""
        return list(self._packs.values())
    
    def list_node_types(self) -> List[str]:
        """List all registered node types."""
        return list(self._nodes.keys())
    
    def has_node(self, node_type: str) -> bool:
        """Check if node type is registered."""
        return node_type in self._nodes
    
    def __len__(self) -> int:
        """Number of registered nodes."""
        return len(self._nodes)
    
    def __iter__(self) -> Iterator[NodeDefinition]:
        """Iterate over node definitions."""
        return iter(self._nodes.values())
    
    def __contains__(self, node_type: str) -> bool:
        """Check if node type is registered."""
        return self.has_node(node_type)


# Global registry instance
_global_registry: Optional[NodeRegistry] = None


def get_global_registry() -> NodeRegistry:
    """Get the global node registry (lazy initialized)."""
    global _global_registry
    if _global_registry is None:
        _global_registry = NodeRegistry()
    return _global_registry


def register_node(
    node_class: Type["BaseNode"],
    node_type: Optional[str] = None,
) -> NodeDefinition:
    """Register a node in the global registry."""
    return get_global_registry().register_node(node_class, node_type)


__all__ = [
    "NodeRegistry",
    "get_global_registry",
    "register_node",
    "NODE_PACK_ENTRY_POINT",
]
