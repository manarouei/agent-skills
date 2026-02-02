"""
Agent Skills - Automation Plane

Contract-first skill library for bounded agent autonomy.
Skills form a pipeline: analyze → generate → implement → test

This package re-exports the runtime components for convenience.
"""

from pathlib import Path

# Re-export runtime components
from runtime.executor import (
    SkillExecutor,
    ExecutionContext,
    ExecutionResult,
    ExecutionStatus,
    SkillRegistry,
    RuntimeConfig,
    DEFAULT_RUNTIME_CONFIG,
)
from runtime.adapter import AgentAdapter
from runtime.protocol import AgentResponse, TaskState
from runtime.state_store import StateStore, create_state_store

# Package paths
PACKAGE_ROOT = Path(__file__).parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent  # src/agent_skills -> project root

__all__ = [
    "SkillExecutor",
    "ExecutionContext", 
    "ExecutionResult",
    "ExecutionStatus",
    "SkillRegistry",
    "RuntimeConfig",
    "DEFAULT_RUNTIME_CONFIG",
    "AgentAdapter",
    "AgentResponse",
    "TaskState",
    "StateStore",
    "create_state_store",
    "PACKAGE_ROOT",
    "PROJECT_ROOT",
]
