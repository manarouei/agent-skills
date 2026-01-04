"""
Agent Capabilities Protocol - Message-based interaction primitives.

This module defines the protocol for agent-style skill execution:
- TaskState: Expanded states beyond terminal success/failure
- MessageType: Types of inter-agent messages
- MessageEnvelope: Container for typed messages
- AgentResponse: Result of a skill turn (may be intermediate)

DESIGN PRINCIPLES:
1. Degenerate case: one-shot tool execution remains simple (TaskState.COMPLETED)
2. Multi-turn: INPUT_REQUIRED pauses for caller input without being an error
3. Resumable: All state persists to StateStore; no long-lived threads
4. Sync-Celery safe: No async, no daemon threads, no event loops

COMPATIBILITY:
- TaskState maps cleanly to ExecutionStatus for backward compatibility
- AgentResponse wraps ExecutionResult concepts with additional states
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# IDENTITY TYPES (type aliases for clarity)
# =============================================================================

# AgentId: Identifier for an agent/skill instance
# Format: skill_name or skill_name:instance_id
# Examples: "schema-infer", "code-fix:correlation_abc123"
AgentId = str

# ContextId: Identifier for a conversation/session context
# This is the correlation_id that tracks a full pipeline run
# All state is keyed by ContextId for persistence and resumption
ContextId = str


# =============================================================================
# STATE AND MESSAGE ENUMS
# =============================================================================

class TaskState(str, Enum):
    """
    Expanded task states for agent-style execution.
    
    Tool-compatible states (map to ExecutionStatus):
    - PENDING: Not yet started
    - COMPLETED: Terminal success
    - FAILED: Terminal failure
    - TIMEOUT: Exceeded time limit
    - BLOCKED: Blocked by gate
    - ESCALATED: Exceeded iteration limit, needs human
    
    Agent-extended states (new):
    - IN_PROGRESS: Currently executing (for long tasks)
    - INPUT_REQUIRED: Paused, awaiting caller input (NOT an error)
    - DELEGATING: Handed off to another agent, awaiting response
    - PAUSED: Explicitly paused, can resume
    """
    
    # Tool-compatible (map to ExecutionStatus)
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    BLOCKED = "blocked"
    ESCALATED = "escalated"
    
    # Agent-extended (new for multi-turn)
    IN_PROGRESS = "in_progress"
    INPUT_REQUIRED = "input_required"
    DELEGATING = "delegating"
    PAUSED = "paused"
    
    @classmethod
    def is_terminal(cls, state: "TaskState") -> bool:
        """Check if state is terminal (no further action possible)."""
        return state in {cls.COMPLETED, cls.FAILED, cls.TIMEOUT, cls.BLOCKED, cls.ESCALATED}
    
    @classmethod
    def is_resumable(cls, state: "TaskState") -> bool:
        """Check if state can be resumed with additional input."""
        return state in {cls.INPUT_REQUIRED, cls.DELEGATING, cls.PAUSED}


class MessageType(str, Enum):
    """
    Types of messages in agent-to-agent communication.
    
    REQUEST: Initial or follow-up request to perform work
    RESPONSE: Reply with results (partial or complete)
    INPUT_REQUIRED: Request for specific inputs from caller (NOT an error)
    DELEGATE: Hand off to another agent
    EVENT: Status update or notification
    ERROR: Error notification (distinct from FAILED state - for unexpected issues)
    """
    
    REQUEST = "request"
    RESPONSE = "response"
    INPUT_REQUIRED = "input_required"
    DELEGATE = "delegate"
    EVENT = "event"
    ERROR = "error"


# =============================================================================
# MESSAGE ENVELOPE
# =============================================================================

class MessageEnvelope(BaseModel):
    """
    Container for typed messages between agents.
    
    This is the unit of communication in the agent protocol.
    All messages are persisted to StateStore for audit and resumption.
    """
    model_config = ConfigDict(extra="forbid")
    
    # Routing
    context_id: ContextId = Field(..., description="Session/correlation ID")
    sender: AgentId = Field(..., description="Source agent ID")
    recipient: AgentId = Field(..., description="Target agent ID")
    
    # Content
    message_type: MessageType = Field(..., description="Type of message")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Message data")
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_tag: Optional[str] = Field(
        default=None,
        description="Optional tag to correlate request/response pairs"
    )
    turn_number: int = Field(default=1, ge=1, description="Turn number in conversation")


# =============================================================================
# INPUT REQUEST SCHEMA
# =============================================================================

class InputFieldSpec(BaseModel):
    """Specification for a required input field."""
    model_config = ConfigDict(extra="forbid")
    
    name: str = Field(..., description="Field name")
    type: str = Field(default="string", description="Expected type (string, int, path, etc.)")
    description: str = Field(default="", description="Human-readable description")
    required: bool = Field(default=True, description="Whether field is required")
    default: Optional[Any] = Field(default=None, description="Default value if not provided")


class InputRequest(BaseModel):
    """
    Structured request for inputs from caller.
    
    Sent when skill cannot proceed without additional information.
    This is NOT an error - it's a normal intermediate state.
    """
    model_config = ConfigDict(extra="forbid")
    
    missing_fields: List[InputFieldSpec] = Field(
        default_factory=list,
        description="Fields that must be provided"
    )
    ambiguous_fields: List[InputFieldSpec] = Field(
        default_factory=list,
        description="Fields needing clarification"
    )
    reason: str = Field(
        default="Additional inputs required",
        description="Human-readable explanation"
    )
    partial_outputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Any outputs produced before pause"
    )


# =============================================================================
# AGENT RESPONSE
# =============================================================================

class AgentResponseMetadata(BaseModel):
    """
    Metadata preserving semantic state detail for ExecutionResult compatibility.
    
    When AgentResponse is converted to ExecutionResult, non-terminal states
    map to "blocked". This metadata preserves the actual agent state.
    """
    model_config = ConfigDict(extra="forbid")
    
    # Semantic state preservation
    agent_state: str = Field(
        ..., 
        description="Actual agent state (input_required, delegating, paused, etc.)"
    )
    
    # Detailed reason for state (for debugging/logging)
    detailed_reason: Optional[str] = Field(
        default=None,
        description="Detailed explanation of state (for debugging/logging)"
    )
    
    # Concurrency control
    context_version: int = Field(
        default=1, 
        ge=1,
        description="Version for optimistic concurrency"
    )
    resume_token: Optional[str] = Field(
        default=None,
        description="Token to validate state hasn't changed since last read"
    )
    
    # Input request detail (when agent_state=input_required)
    input_request_payload: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Structured payload for input requests"
    )


class AgentResponse(BaseModel):
    """
    Response from an agent turn.
    
    This replaces ExecutionResult for agent-style execution while remaining
    compatible with tool-style one-shot calls.
    
    Key differences from ExecutionResult:
    - state can be non-terminal (INPUT_REQUIRED, DELEGATING, etc.)
    - input_request provides structured spec when state=INPUT_REQUIRED
    - messages log for audit trail
    - state_handle enables resumption from StateStore
    - metadata preserves semantic detail when mapped to ExecutionResult
    """
    model_config = ConfigDict(extra="forbid")
    
    # Core result
    state: TaskState = Field(..., description="Current task state")
    outputs: Dict[str, Any] = Field(default_factory=dict, description="Produced outputs")
    
    # For INPUT_REQUIRED state
    input_request: Optional[InputRequest] = Field(
        default=None,
        description="Spec of required inputs when state=INPUT_REQUIRED"
    )
    
    # For DELEGATING state
    delegation_target: Optional[str] = Field(
        default=None,
        description="Target agent ID when state=DELEGATING"
    )
    
    # For error states
    errors: List[str] = Field(default_factory=list, description="Error messages if any")
    
    # Audit trail
    messages: List[MessageEnvelope] = Field(
        default_factory=list,
        description="Messages produced during this turn"
    )
    
    # Resumption handle
    state_handle: Optional[str] = Field(
        default=None,
        description="Opaque handle to resume from StateStore"
    )
    
    # Resume token for conflict detection
    resume_token: Optional[str] = Field(
        default=None,
        description="Token for validating state hasn't changed on resume"
    )
    
    # Metadata for semantic state preservation
    metadata: Optional[AgentResponseMetadata] = Field(
        default=None,
        description="Metadata preserving semantic state for ExecutionResult compatibility"
    )
    
    # Turn info
    turn_number: int = Field(default=1, ge=1, description="Which turn produced this response")
    duration_ms: int = Field(default=0, ge=0, description="Execution time in milliseconds")
    
    def is_terminal(self) -> bool:
        """Check if this response is terminal (no further action)."""
        return TaskState.is_terminal(self.state)
    
    def is_resumable(self) -> bool:
        """Check if execution can be resumed with additional input."""
        return TaskState.is_resumable(self.state)
    
    def needs_input(self) -> bool:
        """Check if caller must provide additional input."""
        return self.state == TaskState.INPUT_REQUIRED
    
    def with_metadata(
        self,
        context_version: int = 1,
        resume_token: Optional[str] = None,
    ) -> "AgentResponse":
        """
        Return a copy with metadata populated.
        
        This ensures semantic state is preserved when converting to ExecutionResult.
        """
        input_payload = None
        if self.input_request:
            input_payload = {
                "missing_fields": [f.model_dump() for f in self.input_request.missing_fields],
                "reason": self.input_request.reason,
            }
        
        return self.model_copy(update={
            "metadata": AgentResponseMetadata(
                agent_state=self.state.value,
                context_version=context_version,
                resume_token=resume_token,
                input_request_payload=input_payload,
            )
        })


# =============================================================================
# CONVERSION UTILITIES
# =============================================================================

def execution_status_to_task_state(status_value: str) -> TaskState:
    """
    Convert ExecutionStatus value to TaskState.
    
    This enables backward compatibility with existing code using ExecutionStatus.
    """
    mapping = {
        "success": TaskState.COMPLETED,
        "failed": TaskState.FAILED,
        "blocked": TaskState.BLOCKED,
        "escalated": TaskState.ESCALATED,
        "timeout": TaskState.TIMEOUT,
    }
    return mapping.get(status_value, TaskState.FAILED)


def task_state_to_execution_status_value(state: TaskState) -> str:
    """
    Convert TaskState to ExecutionStatus value string.
    
    Non-terminal states map to "blocked" to indicate "not complete".
    """
    mapping = {
        TaskState.COMPLETED: "success",
        TaskState.FAILED: "failed",
        TaskState.BLOCKED: "blocked",
        TaskState.ESCALATED: "escalated",
        TaskState.TIMEOUT: "timeout",
        # Non-terminal states → blocked (execution paused)
        TaskState.PENDING: "blocked",
        TaskState.IN_PROGRESS: "blocked",
        TaskState.INPUT_REQUIRED: "blocked",
        TaskState.DELEGATING: "blocked",
        TaskState.PAUSED: "blocked",
    }
    return mapping.get(state, "failed")
