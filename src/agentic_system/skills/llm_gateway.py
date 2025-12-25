"""LLM Gateway Skill - Centralized Anthropic API integration."""
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field, field_validator

from agentic_system.config import get_settings
from agentic_system.observability import get_logger, with_trace_context
from agentic_system.runtime import (
    ExecutionContext,
    SideEffect,
    Skill,
    SkillError,
    SkillSpec,
)

logger = get_logger(__name__)


class BudgetExceededError(SkillError):
    """Raised when budget limits are exceeded."""

    pass


class Message(BaseModel):
    """Chat message."""

    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        """Validate role is user or assistant."""
        if v not in ("user", "assistant"):
            raise ValueError("Role must be 'user' or 'assistant'")
        return v


class LLMBudget(BaseModel):
    """Budget constraints for LLM calls."""

    max_cost_usd: float | None = Field(
        default=None,
        description="Maximum cost in USD",
    )
    max_input_tokens: int | None = Field(
        default=None,
        description="Maximum input tokens",
    )
    max_output_tokens: int | None = Field(
        default=None,
        description="Maximum output tokens",
    )


class LLMGatewayInput(BaseModel):
    """Input schema for LLM Gateway."""

    model: str | None = Field(
        default=None,
        description="Model name (uses default if not provided)",
    )
    system: str | None = Field(
        default=None,
        description="System prompt",
    )
    messages: list[Message] = Field(
        ...,
        description="Conversation messages",
    )
    max_tokens: int = Field(
        ...,
        description="Maximum tokens to generate (REQUIRED)",
    )
    temperature: float = Field(
        default=0.2,
        description="Temperature (0-1)",
    )
    top_p: float | None = Field(
        default=None,
        description="Top-p sampling (0-1)",
    )
    stop_sequences: list[str] | None = Field(
        default=None,
        description="Stop sequences",
    )
    timeout_s: int | None = Field(
        default=None,
        description="Override timeout in seconds",
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Idempotency key for safe retries",
    )
    budget: LLMBudget = Field(
        default_factory=LLMBudget,
        description="Budget constraints",
    )
    redact_prompt_in_logs: bool = Field(
        default=True,
        description="Redact prompts from logs",
    )

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature bounds."""
        if not 0 <= v <= 1:
            raise ValueError("Temperature must be between 0 and 1")
        return v

    @field_validator("top_p")
    @classmethod
    def validate_top_p(cls, v: float | None) -> float | None:
        """Validate top_p bounds."""
        if v is not None and not 0 <= v <= 1:
            raise ValueError("Top-p must be between 0 and 1")
        return v


class LLMUsage(BaseModel):
    """Token usage information."""

    input_tokens: int | None = None
    output_tokens: int | None = None


class LLMGatewayOutput(BaseModel):
    """Output schema for LLM Gateway."""

    text: str = Field(..., description="Generated text")
    model: str = Field(..., description="Model used")
    usage: LLMUsage = Field(..., description="Token usage")
    cost_usd_estimate: float | None = Field(
        default=None,
        description="Estimated cost in USD",
    )
    raw: dict[str, Any] | None = Field(
        default=None,
        description="Safe raw response fields",
    )


class LLMGatewaySkill(Skill):
    """
    LLM Gateway Skill - Centralized Anthropic API integration.

    This is the ONLY place in the system that calls Anthropic API.
    Provides budget controls, retries, and centralized logging.
    """

    def spec(self) -> SkillSpec:
        """Return skill specification."""
        settings = get_settings()
        return SkillSpec(
            name="llm.anthropic_gateway",
            version="1.0.0",
            side_effect=SideEffect.NETWORK,
            timeout_s=settings.default_skill_timeout_s,
            idempotent=False,  # Depends on idempotency_key at runtime
        )

    def input_model(self) -> type[BaseModel]:
        """Return input model."""
        return LLMGatewayInput

    def output_model(self) -> type[BaseModel]:
        """Return output model."""
        return LLMGatewayOutput

    def _execute(
        self,
        input_data: LLMGatewayInput,
        context: ExecutionContext,
    ) -> LLMGatewayOutput:
        """Execute LLM Gateway skill."""
        settings = get_settings()

        # Use default model if not specified
        model = input_data.model or settings.anthropic_default_model

        # Get pricing
        pricing_map = settings.get_llm_pricing()
        pricing = pricing_map.get(model, {"input_per_1k": 0.0, "output_per_1k": 0.0})

        extra = with_trace_context(
            logger,
            trace_id=context.trace_id,
            job_id=context.job_id,
            agent_id=context.agent_id,
            skill_name=self._spec.name,
            skill_version=self._spec.version,
            model=model,
            max_tokens=input_data.max_tokens,
        )

        # Pre-call budget checks
        self._check_budget_pre_call(input_data, model, pricing, settings)

        # Log call start (redact prompts if requested)
        log_data = extra.copy()
        if not input_data.redact_prompt_in_logs:
            log_data["system"] = input_data.system
            log_data["message_count"] = len(input_data.messages)

        logger.info("llm_call_start", extra=log_data)

        # Make API call with retries
        response_data = self._call_anthropic_api(
            input_data, model, settings, extra
        )

        # Parse response
        output = self._parse_response(
            response_data, model, pricing, input_data, extra
        )

        # Post-call budget check
        self._check_budget_post_call(output, input_data, extra)

        # Log call end
        logger.info(
            "llm_call_end",
            extra={
                **extra,
                "input_tokens": output.usage.input_tokens,
                "output_tokens": output.usage.output_tokens,
                "cost_usd_estimate": output.cost_usd_estimate,
            },
        )

        return output

    def _check_budget_pre_call(
        self,
        input_data: LLMGatewayInput,
        model: str,
        pricing: dict[str, float],
        settings: Any,
    ) -> None:
        """Check budget constraints before API call."""
        # Check max_tokens against hard cap
        if input_data.max_tokens > settings.llm_max_tokens_cap:
            raise BudgetExceededError(
                f"max_tokens {input_data.max_tokens} exceeds cap "
                f"{settings.llm_max_tokens_cap}"
            )

        # Check budget.max_output_tokens
        if (
            input_data.budget.max_output_tokens
            and input_data.max_tokens > input_data.budget.max_output_tokens
        ):
            raise BudgetExceededError(
                f"max_tokens {input_data.max_tokens} exceeds budget "
                f"max_output_tokens {input_data.budget.max_output_tokens}"
            )

        # Estimate input tokens (rough heuristic: chars / 4)
        input_text = (input_data.system or "") + "".join(
            [m.content for m in input_data.messages]
        )
        estimated_input_tokens = len(input_text) // 4

        # Check budget.max_input_tokens
        if (
            input_data.budget.max_input_tokens
            and estimated_input_tokens > input_data.budget.max_input_tokens
        ):
            raise BudgetExceededError(
                f"Estimated input tokens {estimated_input_tokens} exceeds budget "
                f"max_input_tokens {input_data.budget.max_input_tokens}"
            )

        # Check budget.max_cost_usd
        max_cost = input_data.budget.max_cost_usd or settings.llm_default_max_cost_usd
        if max_cost:
            estimated_cost = (
                estimated_input_tokens / 1000 * pricing["input_per_1k"]
                + input_data.max_tokens / 1000 * pricing["output_per_1k"]
            )
            if estimated_cost > max_cost:
                raise BudgetExceededError(
                    f"Estimated cost ${estimated_cost:.4f} exceeds budget "
                    f"max_cost_usd ${max_cost}"
                )

    def _check_budget_post_call(
        self,
        output: LLMGatewayOutput,
        input_data: LLMGatewayInput,
        extra: dict[str, Any],
    ) -> None:
        """Check budget constraints after API call."""
        settings = get_settings()
        max_cost = input_data.budget.max_cost_usd or settings.llm_default_max_cost_usd

        if max_cost and output.cost_usd_estimate:
            if output.cost_usd_estimate > max_cost:
                logger.error(
                    "Budget exceeded post-call",
                    extra={
                        **extra,
                        "cost": output.cost_usd_estimate,
                        "max_cost": max_cost,
                    },
                )
                raise BudgetExceededError(
                    f"Actual cost ${output.cost_usd_estimate:.4f} exceeds budget "
                    f"max_cost_usd ${max_cost}"
                )

    def _call_anthropic_api(
        self,
        input_data: LLMGatewayInput,
        model: str,
        settings: Any,
        extra: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Call Anthropic API with retry logic.

        Args:
            input_data: Input data
            model: Model name
            settings: Settings
            extra: Log extra context

        Returns:
            Response data

        Raises:
            SkillError: If API call fails
        """
        # Build request
        request_body = {
            "model": model,
            "max_tokens": input_data.max_tokens,
            "messages": [m.model_dump() for m in input_data.messages],
            "temperature": input_data.temperature,
        }

        if input_data.system:
            request_body["system"] = input_data.system
        if input_data.top_p is not None:
            request_body["top_p"] = input_data.top_p
        if input_data.stop_sequences:
            request_body["stop_sequences"] = input_data.stop_sequences

        headers = {
            "x-api-key": settings.anthropic_api_key.get_secret_value(),
            "anthropic-version": settings.anthropic_version,
            "content-type": "application/json",
        }

        # Determine timeout
        timeout_s = input_data.timeout_s or self._spec.timeout_s
        timeout = httpx.Timeout(
            connect=5.0,
            read=timeout_s,
            write=5.0,
            pool=5.0,
        )

        # Determine retry behavior
        max_retries = 2 if input_data.idempotency_key else 0

        url = f"{settings.anthropic_base_url}/v1/messages"

        # Execute with retries
        for attempt in range(max_retries + 1):
            try:
                with httpx.Client(timeout=timeout) as client:
                    response = client.post(url, json=request_body, headers=headers)

                    # Check for errors
                    if response.status_code == 429:
                        if attempt < max_retries:
                            wait_time = 0.5 * (2**attempt)
                            logger.warning(
                                f"Rate limited, retrying in {wait_time}s",
                                extra=extra,
                            )
                            time.sleep(wait_time)
                            continue
                        response.raise_for_status()

                    elif 500 <= response.status_code < 600:
                        if attempt < max_retries:
                            wait_time = 0.5 * (2**attempt)
                            logger.warning(
                                f"Server error {response.status_code}, "
                                f"retrying in {wait_time}s",
                                extra=extra,
                            )
                            time.sleep(wait_time)
                            continue
                        response.raise_for_status()

                    elif response.status_code >= 400:
                        # Don't retry client errors (except 429)
                        response.raise_for_status()

                    return response.json()

            except httpx.TimeoutException as e:
                if attempt < max_retries:
                    wait_time = 0.5 * (2**attempt)
                    logger.warning(
                        f"Request timeout, retrying in {wait_time}s",
                        extra=extra,
                    )
                    time.sleep(wait_time)
                    continue
                raise SkillError(f"Request timeout: {e}") from e

            except httpx.HTTPError as e:
                raise SkillError(f"HTTP error: {e}") from e

        raise SkillError("Max retries exceeded")

    def _parse_response(
        self,
        response_data: dict[str, Any],
        model: str,
        pricing: dict[str, float],
        input_data: LLMGatewayInput,
        extra: dict[str, Any],
    ) -> LLMGatewayOutput:
        """Parse Anthropic API response."""
        # Extract text from content blocks
        content_blocks = response_data.get("content", [])
        text_parts = []
        for block in content_blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))

        text = "".join(text_parts)

        # Extract usage
        usage_data = response_data.get("usage", {})
        usage = LLMUsage(
            input_tokens=usage_data.get("input_tokens"),
            output_tokens=usage_data.get("output_tokens"),
        )

        # Calculate cost
        cost_usd_estimate = None
        if usage.input_tokens and usage.output_tokens:
            cost_usd_estimate = (
                usage.input_tokens / 1000 * pricing["input_per_1k"]
                + usage.output_tokens / 1000 * pricing["output_per_1k"]
            )

        # Build safe raw response (exclude sensitive fields)
        raw = {
            "id": response_data.get("id"),
            "type": response_data.get("type"),
            "role": response_data.get("role"),
            "stop_reason": response_data.get("stop_reason"),
        }

        return LLMGatewayOutput(
            text=text,
            model=model,
            usage=usage,
            cost_usd_estimate=cost_usd_estimate,
            raw=raw,
        )
