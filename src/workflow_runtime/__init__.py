"""
Workflow Runtime - Sync DAG execution for n8n-compatible workflows.

This package provides:
- WorkflowDefinition: JSON structure describing a workflow
- CompiledGraph: Executable workflow DAG
- WorkflowExecutor: Sync execution engine

All execution is synchronous (sync-Celery safe).
"""

from .models import WorkflowDefinition, WorkflowNode, WorkflowConnection
from .graph import CompiledGraph, NodeRunResult
from .executor import WorkflowExecutor, WorkflowResult

__all__ = [
    # Models
    "WorkflowDefinition",
    "WorkflowNode",
    "WorkflowConnection",
    # Graph
    "CompiledGraph",
    "NodeRunResult",
    # Executor
    "WorkflowExecutor",
    "WorkflowResult",
]
