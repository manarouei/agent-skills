"""Simple Summarizer Agent - Orchestrates summarization workflow."""
from pydantic import BaseModel, Field

from agentic_system.config import get_settings
from agentic_system.runtime import Agent, AgentSpec, ExecutionContext
from agentic_system.runtime.registry import get_skill_registry


class SimpleSummarizerInput(BaseModel):
    """Input schema for Simple Summarizer agent."""

    text: str = Field(..., description="Text to summarize")
    max_words: int = Field(
        default=100,
        description="Maximum words in summary",
    )


class SimpleSummarizerOutput(BaseModel):
    """Output schema for Simple Summarizer agent."""

    summary: str = Field(..., description="Generated summary")


class SimpleSummarizerAgent(Agent):
    """
    Simple Summarizer Agent.

    Orchestrates the summarization workflow by calling the Summarize skill.
    """

    def spec(self) -> AgentSpec:
        """Return agent specification."""
        settings = get_settings()
        return AgentSpec(
            agent_id="simple_summarizer",
            version="1.0.0",
            step_limit=settings.default_agent_step_limit,
            description="Simple agent that summarizes text",
        )

    def input_model(self) -> type[BaseModel]:
        """Return input model."""
        return SimpleSummarizerInput

    def output_model(self) -> type[BaseModel]:
        """Return output model."""
        return SimpleSummarizerOutput

    def _run(
        self,
        input_data: SimpleSummarizerInput,
        context: ExecutionContext,
    ) -> SimpleSummarizerOutput:
        """Execute agent logic."""
        self._check_step_limit()

        # Get skill registry
        skill_registry = get_skill_registry()

        # Call summarize skill
        summarize_input = {
            "text": input_data.text,
            "max_words": input_data.max_words,
        }

        result = skill_registry.execute(
            name="text.summarize",
            input_data=summarize_input,
            context=context,
        )

        return SimpleSummarizerOutput(summary=result["summary"])
