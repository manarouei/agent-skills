"""Summarize Skill - Uses LLM Gateway for text summarization."""
from pydantic import BaseModel, Field

from agentic_system.config import get_settings
from agentic_system.observability import get_logger
from agentic_system.runtime import (
    ExecutionContext,
    SideEffect,
    Skill,
    SkillSpec,
)
from agentic_system.runtime.registry import get_skill_registry

logger = get_logger(__name__)


class SummarizeInput(BaseModel):
    """Input schema for Summarize skill."""

    text: str = Field(..., description="Text to summarize")
    max_words: int = Field(
        default=100,
        description="Maximum words in summary",
    )


class SummarizeOutput(BaseModel):
    """Output schema for Summarize skill."""

    summary: str = Field(..., description="Generated summary")


class SummarizeSkill(Skill):
    """
    Summarize Skill - Generates concise summaries of text.

    Uses the LLM Gateway skill to perform actual summarization.
    """

    def spec(self) -> SkillSpec:
        """Return skill specification."""
        settings = get_settings()
        return SkillSpec(
            name="text.summarize",
            version="1.0.0",
            side_effect=SideEffect.NETWORK,  # Calls LLM Gateway which makes network calls
            timeout_s=settings.default_skill_timeout_s,
            idempotent=False,
        )

    def input_model(self) -> type[BaseModel]:
        """Return input model."""
        return SummarizeInput

    def output_model(self) -> type[BaseModel]:
        """Return output model."""
        return SummarizeOutput

    def _execute(
        self,
        input_data: SummarizeInput,
        context: ExecutionContext,
    ) -> SummarizeOutput:
        """Execute Summarize skill."""
        # Build prompt
        system_prompt = "You are a helpful assistant that creates concise summaries."
        user_message = (
            f"Summarize the following text in no more than {input_data.max_words} words. "
            f"Be concise and focus on the key points.\n\n"
            f"Text:\n{input_data.text}"
        )

        # Call LLM Gateway via registry
        skill_registry = get_skill_registry()

        llm_input = {
            "messages": [
                {
                    "role": "user",
                    "content": user_message,
                }
            ],
            "system": system_prompt,
            "max_tokens": 256,  # Conservative estimate for summaries
            "temperature": 0.2,  # Low temperature for consistent summaries
            "redact_prompt_in_logs": False,  # OK to log summaries (not sensitive)
        }

        logger.info(
            "Calling LLM Gateway for summarization",
            extra={
                "trace_id": context.trace_id,
                "job_id": context.job_id,
                "input_length": len(input_data.text),
                "max_words": input_data.max_words,
            },
        )

        llm_output = skill_registry.execute(
            name="llm.anthropic_gateway",
            input_data=llm_input,
            context=context,
        )

        summary_text = llm_output["text"].strip()

        # Post-process: enforce word limit as a guardrail
        words = summary_text.split()
        if len(words) > input_data.max_words:
            summary_text = " ".join(words[: input_data.max_words]) + "..."
            logger.info(
                "Summary truncated to word limit",
                extra={
                    "trace_id": context.trace_id,
                    "original_words": len(words),
                    "max_words": input_data.max_words,
                },
            )

        return SummarizeOutput(summary=summary_text)
