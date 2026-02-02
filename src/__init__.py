"""
Agent Skills Framework

A robust, maintainable, Python-first framework for automatically implementing
n8n-like nodes as Python equivalents via an end-to-end pipeline:
analyze → generate → implement → test

Architecture:
- agent_skills/: Skills + pipeline orchestrator + executor enforcement
- node_sdk/: Node execution semantics (BaseNode, NodeContext, items)
- workflow_runtime/: Sync DAG executor for workflows
- node_registry/: Plugin discovery + validation
"""

__version__ = "1.0.0"
