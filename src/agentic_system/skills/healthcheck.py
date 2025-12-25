"""Simple healthcheck skill - demonstrates a skill with no side effects."""
from pydantic import BaseModel, Field

from agentic_system.config import get_settings
from agentic_system.runtime import ExecutionContext, SideEffect, Skill, SkillSpec


class HealthCheckInput(BaseModel):
    """Input schema for HealthCheck skill."""

    include_config: bool = Field(
        default=False,
        description="Include configuration info in response",
    )


class HealthCheckOutput(BaseModel):
    """Output schema for HealthCheck skill."""

    status: str = Field(..., description="Health status")
    service: str = Field(..., description="Service name")
    environment: str | None = Field(default=None, description="Environment name")
    model: str | None = Field(default=None, description="Default LLM model")


class HealthCheckSkill(Skill):
    """
    Health Check Skill - Simple skill with no side effects.

    Returns health status and optionally configuration info.
    Useful for testing and demonstrating skill patterns.
    """

    def spec(self) -> SkillSpec:
        """Return skill specification."""
        return SkillSpec(
            name="system.healthcheck",
            version="1.0.0",
            side_effect=SideEffect.NONE,
            timeout_s=5,
            idempotent=True,
        )

    def input_model(self) -> type[BaseModel]:
        """Return input model."""
        return HealthCheckInput

    def output_model(self) -> type[BaseModel]:
        """Return output model."""
        return HealthCheckOutput

    def _execute(
        self,
        input_data: HealthCheckInput,
        context: ExecutionContext,
    ) -> HealthCheckOutput:
        """Execute HealthCheck skill."""
        settings = get_settings()

        output = HealthCheckOutput(
            status="healthy",
            service="agentic-system",
        )

        if input_data.include_config:
            output.environment = settings.env
            output.model = settings.anthropic_default_model

        return output
