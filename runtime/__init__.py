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
    IntermediateState,
    InteractionOutcomes,
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
    # Hybrid backbone
    RuntimeConfig,
    DEFAULT_RUNTIME_CONFIG,
    AdvisorOutputValidator,
)

# Export agent capabilities protocol
from .protocol import (
    AgentId,
    ContextId,
    TaskState,
    MessageType,
    MessageEnvelope,
    InputFieldSpec,
    InputRequest,
    AgentResponse,
    execution_status_to_task_state,
    task_state_to_execution_status_value,
)

# Export state store
from .state_store import (
    StateStore,
    SQLiteStateStore,
    PostgresStateStore,
    create_state_store,
    ConversationEvent,
    PocketFact,
    ConversationSummary,
    ContextState,
    DuplicateMessageError,
    VersionConflictError,
    MAX_EVENTS_PER_CONTEXT,
    MAX_POCKET_FACTS_PER_BUCKET,
    MAX_SUMMARY_SIZE_CHARS,
)

# Export adapter
from .adapter import (
    AgentAdapter,
    AgentSkillWrapper,
    ResumeTokenConflictError,
    create_agent_adapter,
    ROUTER_ENABLED,
)

# Export learning loop
from .learning_loop import (
    GoldenArtifactPackage,
    PromotionCandidate,
    LearningLoopEmitter,
    compute_source_hash,
    categorize_error,
)

# Export knowledge base
from .kb import (
    KnowledgeBase,
    KBPattern,
    KBValidationError,
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
    "IntermediateState",
    "InteractionOutcomes",
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
    # Hybrid backbone
    "RuntimeConfig",
    "DEFAULT_RUNTIME_CONFIG",
    "AdvisorOutputValidator",
    # Agent capabilities protocol
    "AgentId",
    "ContextId",
    "TaskState",
    "MessageType",
    "MessageEnvelope",
    "InputFieldSpec",
    "InputRequest",
    "AgentResponse",
    "execution_status_to_task_state",
    "task_state_to_execution_status_value",
    # State store
    "StateStore",
    "SQLiteStateStore",
    "PostgresStateStore",
    "create_state_store",
    "ConversationEvent",
    "PocketFact",
    "ConversationSummary",
    "ContextState",
    "DuplicateMessageError",
    "VersionConflictError",
    "MAX_EVENTS_PER_CONTEXT",
    "MAX_POCKET_FACTS_PER_BUCKET",
    "MAX_SUMMARY_SIZE_CHARS",
    # Adapter
    "AgentAdapter",
    "AgentSkillWrapper",
    "ResumeTokenConflictError",
    "create_agent_adapter",
    "ROUTER_ENABLED",
    # Learning loop
    "GoldenArtifactPackage",
    "PromotionCandidate",
    "LearningLoopEmitter",
    "compute_source_hash",
    "categorize_error",
    # Knowledge base
    "KnowledgeBase",
    "KBPattern",
    "KBValidationError",
]
