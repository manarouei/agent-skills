"""Pytest configuration and fixtures."""
import os

import pytest

# Set test environment variables
os.environ["AGENTIC_ENV"] = "test"
os.environ["AGENTIC_ANTHROPIC_API_KEY"] = "test-key"
os.environ["AGENTIC_REDIS_URL"] = "redis://localhost:6379/1"  # Test DB
os.environ["AGENTIC_RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672//"


@pytest.fixture
def execution_context():
    """Create a test execution context."""
    from agentic_system.runtime import ExecutionContext

    return ExecutionContext(
        trace_id="test-trace-123",
        job_id="test-job-456",
        agent_id="test-agent",
    )


@pytest.fixture
def sample_anthropic_response():
    """Sample Anthropic API response."""
    return {
        "id": "msg_test123",
        "type": "message",
        "role": "assistant",
        "content": [
            {
                "type": "text",
                "text": "This is a test response from the LLM.",
            }
        ],
        "model": "claude-3-5-sonnet-20241022",
        "stop_reason": "end_turn",
        "usage": {
            "input_tokens": 15,
            "output_tokens": 25,
        },
    }
