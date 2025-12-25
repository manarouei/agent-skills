"""Unit tests for LLM Gateway skill."""
import httpx
import pytest

from agentic_system.runtime import ExecutionContext
from agentic_system.skills.llm_gateway import (
    BudgetExceededError,
    LLMGatewayInput,
    LLMGatewaySkill,
    Message,
)


def test_llm_gateway_budget_pre_call_exceeded(execution_context):
    """Test that budget exceeded error is raised pre-call."""
    skill = LLMGatewaySkill()

    input_data = LLMGatewayInput(
        messages=[
            Message(role="user", content="Test message"),
        ],
        max_tokens=100,
        budget={
            "max_cost_usd": 0.00001,  # Very low budget
        },
    )

    with pytest.raises(BudgetExceededError) as exc_info:
        skill.execute(input_data.model_dump(), execution_context)

    assert "Estimated cost" in str(exc_info.value)
    assert "exceeds budget" in str(exc_info.value)


def test_llm_gateway_max_tokens_cap_exceeded(execution_context):
    """Test that max tokens cap is enforced."""
    skill = LLMGatewaySkill()

    input_data = LLMGatewayInput(
        messages=[
            Message(role="user", content="Test message"),
        ],
        max_tokens=10000,  # Exceeds cap of 4096
    )

    with pytest.raises(BudgetExceededError) as exc_info:
        skill.execute(input_data.model_dump(), execution_context)

    assert "exceeds cap" in str(exc_info.value)


def test_llm_gateway_parses_response_and_cost(
    execution_context,
    sample_anthropic_response,
):
    """Test that LLM Gateway parses response and computes cost correctly."""
    skill = LLMGatewaySkill()

    input_data = LLMGatewayInput(
        messages=[
            Message(role="user", content="Test message"),
        ],
        max_tokens=100,
    )

    # Mock httpx Client
    def mock_post(url, json, headers):
        """Mock POST request."""
        response = httpx.Response(
            status_code=200,
            json=sample_anthropic_response,
        )
        return response

    # Monkeypatch httpx.Client
    class MockClient:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, json, headers):
            return mock_post(url, json, headers)

    import agentic_system.skills.llm_gateway

    original_client = httpx.Client
    agentic_system.skills.llm_gateway.httpx.Client = MockClient

    try:
        result = skill.execute(input_data.model_dump(), execution_context)

        # Check output structure
        assert "text" in result
        assert result["text"] == "This is a test response from the LLM."
        assert result["model"] == "claude-3-5-sonnet-20241022"
        assert result["usage"]["input_tokens"] == 15
        assert result["usage"]["output_tokens"] == 25

        # Check cost calculation
        # Input: 15 tokens * 0.003/1k = 0.000045
        # Output: 25 tokens * 0.015/1k = 0.000375
        # Total: ~0.00042
        assert result["cost_usd_estimate"] is not None
        assert 0.0004 < result["cost_usd_estimate"] < 0.0005

    finally:
        # Restore original
        agentic_system.skills.llm_gateway.httpx.Client = original_client


def test_llm_gateway_input_validation():
    """Test input validation."""
    # Invalid role
    with pytest.raises(ValueError):
        Message(role="invalid", content="test")

    # Invalid temperature
    with pytest.raises(ValueError):
        LLMGatewayInput(
            messages=[Message(role="user", content="test")],
            max_tokens=100,
            temperature=1.5,  # Out of bounds
        )

    # Invalid top_p
    with pytest.raises(ValueError):
        LLMGatewayInput(
            messages=[Message(role="user", content="test")],
            max_tokens=100,
            top_p=2.0,  # Out of bounds
        )
