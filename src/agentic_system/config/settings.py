"""Configuration and settings management using pydantic-settings."""
import json
from typing import Any

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable loading."""

    model_config = SettingsConfigDict(
        env_prefix="AGENTIC_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core service settings
    env: str = Field(default="development", description="Environment name")
    log_level: str = Field(default="INFO", description="Log level")

    # Redis settings
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # RabbitMQ settings
    rabbitmq_url: str = Field(
        default="amqp://guest:guest@localhost:5672//",
        description="RabbitMQ connection URL",
    )

    # Anthropic LLM settings
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        description="Anthropic API key (optional when using Copilot assistant)",
    )
    anthropic_base_url: str = Field(
        default="https://api.anthropic.com",
        description="Anthropic API base URL",
    )
    anthropic_version: str = Field(
        default="2023-06-01",
        description="Anthropic API version",
    )
    anthropic_default_model: str = Field(
        default="claude-3-5-sonnet-20241022",
        description="Default Anthropic model",
    )

    # LLM budget controls
    llm_max_tokens_cap: int = Field(
        default=4096,
        description="Hard cap on max_tokens for any LLM call",
    )
    llm_default_max_cost_usd: float | None = Field(
        default=None,
        description="Default max cost per LLM call in USD",
    )
    llm_pricing_json: str | None = Field(
        default=None,
        description="JSON string with model pricing overrides",
    )

    # Runtime limits
    default_skill_timeout_s: int = Field(
        default=30,
        description="Default skill timeout in seconds",
    )
    default_agent_step_limit: int = Field(
        default=10,
        description="Default agent step limit",
    )

    # Celery settings
    celery_task_time_limit: int = Field(
        default=300,
        description="Celery hard task time limit in seconds",
    )
    celery_task_soft_time_limit: int = Field(
        default=270,
        description="Celery soft task time limit in seconds",
    )

    @field_validator("llm_max_tokens_cap")
    @classmethod
    def validate_tokens_cap(cls, v: int) -> int:
        """Validate that tokens cap is positive."""
        if v <= 0:
            raise ValueError("llm_max_tokens_cap must be positive")
        return v

    def get_llm_pricing(self) -> dict[str, dict[str, float]]:
        """
        Get LLM pricing map from settings or default fallback.

        Returns:
            Dict mapping model name to pricing dict with input_per_1k and output_per_1k.
        """
        # Default pricing map (as of Dec 2024, clearly marked for override)
        default_pricing = {
            "claude-3-5-sonnet-20241022": {
                "input_per_1k": 0.003,
                "output_per_1k": 0.015,
            },
            "claude-3-5-haiku-20241022": {
                "input_per_1k": 0.001,
                "output_per_1k": 0.005,
            },
            "claude-3-opus-20240229": {
                "input_per_1k": 0.015,
                "output_per_1k": 0.075,
            },
        }

        if self.llm_pricing_json:
            try:
                custom_pricing = json.loads(self.llm_pricing_json)
                # Merge custom pricing with defaults
                return {**default_pricing, **custom_pricing}
            except json.JSONDecodeError:
                # Fall back to defaults if JSON is invalid
                return default_pricing

        return default_pricing


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get or create the global settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings (useful for testing)."""
    global _settings
    _settings = None
