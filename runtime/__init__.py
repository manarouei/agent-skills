"""
Agent Skills Runtime Package

Contract-first skill execution with bounded autonomy.

Canonical contract models are in contracts/ package.
Runtime classes import from there - single source of truth.
"""

# Re-export canonical contract types for convenience
from contracts import (
    AutonomyLevel,
    ExecutionStatus,
    SideEffect,
    RetryPolicy,
    FailureMode,
    SkillContract,
    RetryConfig,
    IdempotencyConfig,
    ArtifactSpec,
    TraceEntry,
    TraceMap,
    ScopeAllowlist,
    ValidationResult,
)

# Export runtime types
from .executor import (
    ExecutionContext,
    ExecutionResult,
    SkillRegistry,
    SkillExecutor,
    BoundedFixLoop,
    IdempotencyStore,
    TraceMapGate,
    ScopeGate,
    GateResult,
    create_executor,
    run_with_timeout,
)

__all__ = [
    # Contract types (from contracts/)
    "AutonomyLevel",
    "ExecutionStatus",
    "SideEffect",
    "RetryPolicy",
    "FailureMode",
    "SkillContract",
    "RetryConfig",
    "IdempotencyConfig",
    "ArtifactSpec",
    "TraceEntry",
    "TraceMap",
    "ScopeAllowlist",
    "ValidationResult",
    # Runtime types
    "ExecutionContext",
    "ExecutionResult",
    "SkillRegistry",
    "SkillExecutor",
    "BoundedFixLoop",
    "IdempotencyStore",
    "TraceMapGate",
    "ScopeGate",
    "GateResult",
    "create_executor",
    "run_with_timeout",
]
