"""Unit tests for Summarize skill."""
import pytest

from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.skills.llm_gateway import LLMGatewaySkill
from agentic_system.skills.summarize import SummarizeInput, SummarizeSkill


def test_summarize_skill_calls_gateway(execution_context, monkeypatch):
    """Test that Summarize skill calls LLM Gateway correctly."""
    # Register skills
    skill_registry = get_skill_registry()
    skill_registry.register(LLMGatewaySkill())
    skill_registry.register(SummarizeSkill())

    # Mock LLM Gateway execute to return known text
    def mock_execute(name, input_data, context):
        if name == "llm.anthropic_gateway":
            return {
                "text": "This is a concise summary of the provided text.",
                "model": "claude-3-5-sonnet-20241022",
                "usage": {"input_tokens": 50, "output_tokens": 15},
                "cost_usd_estimate": 0.0003,
            }
        raise ValueError(f"Unexpected skill: {name}")

    # Monkeypatch skill registry execute
    monkeypatch.setattr(skill_registry, "execute", mock_execute)

    # Execute summarize skill
    summarize_skill = SummarizeSkill()
    input_data = SummarizeInput(
        text="This is a long text that needs to be summarized. " * 20,
        max_words=50,
    )

    result = summarize_skill.execute(input_data.model_dump(), execution_context)

    # Check result
    assert "summary" in result
    assert result["summary"] == "This is a concise summary of the provided text."


def test_summarize_skill_enforces_word_limit(execution_context, monkeypatch):
    """Test that Summarize skill enforces word limit."""
    # Register skills
    skill_registry = get_skill_registry()
    skill_registry.register(LLMGatewaySkill())
    skill_registry.register(SummarizeSkill())

    # Mock LLM Gateway to return long text
    long_text = " ".join([f"word{i}" for i in range(200)])

    def mock_execute(name, input_data, context):
        if name == "llm.anthropic_gateway":
            return {
                "text": long_text,
                "model": "claude-3-5-sonnet-20241022",
                "usage": {"input_tokens": 50, "output_tokens": 200},
                "cost_usd_estimate": 0.003,
            }
        raise ValueError(f"Unexpected skill: {name}")

    monkeypatch.setattr(skill_registry, "execute", mock_execute)

    # Execute with low word limit
    summarize_skill = SummarizeSkill()
    input_data = SummarizeInput(
        text="Long text...",
        max_words=20,
    )

    result = summarize_skill.execute(input_data.model_dump(), execution_context)

    # Check that summary is truncated
    summary_words = result["summary"].rstrip("...").split()
    assert len(summary_words) <= 20


def test_summarize_input_validation():
    """Test Summarize input validation."""
    # Valid input
    input_data = SummarizeInput(
        text="Test text",
        max_words=100,
    )
    assert input_data.text == "Test text"
    assert input_data.max_words == 100

    # Default max_words
    input_data = SummarizeInput(text="Test text")
    assert input_data.max_words == 100
