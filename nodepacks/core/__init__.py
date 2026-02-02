"""
Core Node Pack - Essential utility nodes.

This pack provides basic nodes for workflow operations:
- ManualTrigger: Start a workflow manually
- Set: Set/modify data fields
- Code: Execute custom Python code
- NoOp: Pass-through node (no operation)

All nodes are SYNC-CELERY SAFE.
"""

from .nodes import (
    ManualTriggerNode,
    SetNode,
    CodeNode,
    NoOpNode,
    HttpRequestNode,
)
from .manifest import MANIFEST, register_nodes

__all__ = [
    "ManualTriggerNode",
    "SetNode",
    "CodeNode",
    "NoOpNode",
    "HttpRequestNode",
    "MANIFEST",
    "register_nodes",
]
