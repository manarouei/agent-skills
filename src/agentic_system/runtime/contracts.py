"""Runtime contracts and data models."""
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SideEffect(str, Enum):
    """Side effect classification for skills."""

    NONE = "none"  # Pure computation, no side effects
    NETWORK = "network"  # Makes network calls
    STORAGE = "storage"  # Reads/writes storage
    BOTH = "both"  # Both network and storage


class SkillSpec(BaseModel):
    """Specification for a skill."""

    name: str = Field(..., description="Unique skill name")
    version: str = Field(..., description="Skill version (semver)")
    side_effect: SideEffect = Field(
        default=SideEffect.NONE,
        description="Side effect classification",
    )
    timeout_s: int = Field(..., description="Timeout in seconds")
    idempotent: bool = Field(
        default=False,
        description="Whether skill execution is idempotent",
    )

    def __str__(self) -> str:
        """String representation."""
        return f"{self.name}@{self.version}"


class AgentSpec(BaseModel):
    """Specification for an agent."""

    agent_id: str = Field(..., description="Unique agent ID")
    version: str = Field(..., description="Agent version (semver)")
    step_limit: int = Field(..., description="Maximum steps before timeout")
    description: str | None = Field(
        default=None,
        description="Human-readable description",
    )

    def __str__(self) -> str:
        """String representation."""
        return f"{self.agent_id}@{self.version}"


class ExecutionContext(BaseModel):
    """Context for skill/agent execution."""

    trace_id: str = Field(..., description="Trace ID for observability")
    job_id: str = Field(..., description="Job ID")
    agent_id: str = Field(..., description="Agent ID")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context metadata",
    )

    def with_metadata(self, **kwargs: Any) -> "ExecutionContext":
        """
        Create a new context with additional metadata.

        Args:
            **kwargs: Metadata key-value pairs

        Returns:
            New ExecutionContext with merged metadata
        """
        new_metadata = {**self.metadata, **kwargs}
        return self.model_copy(update={"metadata": new_metadata})
