"""Runner for executing agents."""
from typing import Any

from agentic_system.observability import get_logger, with_trace_context
from agentic_system.runtime.contracts import ExecutionContext
from agentic_system.runtime.registry import get_agent_registry

logger = get_logger(__name__)


class RunnerError(Exception):
    """Base exception for runner errors."""

    pass


def run_agent(
    agent_id: str,
    input_data: dict[str, Any],
    context: ExecutionContext,
    version: str = "latest",
) -> dict[str, Any]:
    """
    Run an agent by ID.

    Args:
        agent_id: Agent ID
        input_data: Input data
        context: Execution context
        version: Agent version (default: "latest")

    Returns:
        Agent output

    Raises:
        RunnerError: If agent not found or execution fails
    """
    extra = with_trace_context(
        logger,
        trace_id=context.trace_id,
        job_id=context.job_id,
        agent_id=agent_id,
    )

    logger.info("Running agent", extra=extra)

    agent_registry = get_agent_registry()
    agent = agent_registry.get(agent_id, version)

    if agent is None:
        raise RunnerError(f"Agent not found: {agent_id}@{version}")

    try:
        result = agent.run(input_data, context)
        logger.info("Agent completed successfully", extra=extra)
        return result
    except Exception as e:
        logger.error("Agent execution failed", extra=extra, exc_info=True)
        raise RunnerError(f"Agent execution failed: {e}") from e
