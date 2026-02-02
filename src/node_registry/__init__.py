"""
Node Registry - Discovery and registration of node implementations.

This package provides:
- NodeDefinition: Metadata about a registered node
- NodePackManifest: Package metadata for a node pack
- NodeRegistry: Central registry for discovering nodes

Supports entry-points based discovery for plugin node packs.
"""

from .models import NodeDefinition, NodePackManifest
from .registry import NodeRegistry

__all__ = [
    "NodeDefinition",
    "NodePackManifest",
    "NodeRegistry",
]
