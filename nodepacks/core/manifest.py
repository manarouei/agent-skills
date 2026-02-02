"""
Core Node Pack Manifest - Registration function for entry-points.
"""

from src.node_registry.models import NodePackManifest
from .nodes import (
    ManualTriggerNode,
    SetNode,
    CodeNode,
    NoOpNode,
    HttpRequestNode,
)


MANIFEST = NodePackManifest(
    name="core",
    version="1.0.0",
    description="Core utility nodes for workflow operations",
    author="agent-skills",
    license="MIT",
    nodes=[
        "n8n-nodes-base.manualTrigger",
        "n8n-nodes-base.set",
        "n8n-nodes-base.code",
        "n8n-nodes-base.noOp",
        "n8n-nodes-base.httpRequest",
    ],
    entry_point="nodepacks.core",
)


# Node classes by type
NODE_CLASSES = {
    "n8n-nodes-base.manualTrigger": ManualTriggerNode,
    "n8n-nodes-base.set": SetNode,
    "n8n-nodes-base.code": CodeNode,
    "n8n-nodes-base.noOp": NoOpNode,
    "n8n-nodes-base.httpRequest": HttpRequestNode,
}


def register_nodes():
    """
    Entry point function for node pack discovery.
    
    Returns tuple of (manifest, node_classes).
    """
    return MANIFEST, NODE_CLASSES


__all__ = [
    "MANIFEST",
    "NODE_CLASSES",
    "register_nodes",
]
