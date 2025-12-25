"""Base agent class for orchestrating skills."""
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from agentic_system.observability import get_logger, with_trace_context
from agentic_system.runtime.contracts import AgentSpec, ExecutionContext

logger = get_logger(__name__)


class AgentError(Exception):
    """Base exception for agent errors."""

    pass


class AgentStepLimitExceeded(AgentError):
    """Raised when agent exceeds step limit."""

    pass


class Agent(ABC):
    """
    Base class for agents that orchestrate skills.

    Agents execute a sequence of skills to accomplish a goal.
    """

    def __init__(self):
        """Initialize agent."""
        self._spec = self.spec()
        self._step_count = 0

    @abstractmethod
    def spec(self) -> AgentSpec:
        """
        Return agent specification.

        Returns:
            AgentSpec defining the agent's metadata
        """
        pass

    @abstractmethod
    def input_model(self) -> type[BaseModel]:
        """
        Return Pydantic model for input validation.

        Returns:
            Pydantic model class
        """
        pass

    @abstractmethod
    def output_model(self) -> type[BaseModel]:
        """
        Return Pydantic model for output validation.

        Returns:
            Pydantic model class
        """
        pass

    @abstractmethod
    def _run(self, input_data: BaseModel, context: ExecutionContext) -> BaseModel:
        """
        Execute agent logic (implemented by subclasses).

        Args:
            input_data: Validated input data
            context: Execution context

        Returns:
            Validated output data
        """
        pass

    def run(
        self,
        input_data: dict[str, Any] | BaseModel,
        context: ExecutionContext,
    ) -> dict[str, Any]:
        """
        Run agent with validation and step limit enforcement.

        Args:
            input_data: Input data (dict or Pydantic model)
            context: Execution context

        Returns:
            Output data as dict

        Raises:
            AgentError: If execution fails
        """
        extra = with_trace_context(
            logger,
            trace_id=context.trace_id,
            job_id=context.job_id,
            agent_id=context.agent_id,
        )

        logger.info("Agent execution started", extra=extra)

        try:
            # Validate input
            input_model_class = self.input_model()
            if isinstance(input_data, dict):
                validated_input = input_model_class.model_validate(input_data)
            else:
                validated_input = input_data

            # Reset step counter
            self._step_count = 0

            # Execute agent logic
            output = self._run(validated_input, context)

            # Validate output
            output_model_class = self.output_model()
            if not isinstance(output, output_model_class):
                output = output_model_class.model_validate(output)

            logger.info(
                "Agent execution completed",
                extra={**extra, "steps": self._step_count},
            )
            return output.model_dump()

        except AgentError:
            logger.error("Agent execution failed", extra=extra, exc_info=True)
            raise
        except Exception as e:
            logger.error("Unexpected agent error", extra=extra, exc_info=True)
            raise AgentError(f"Unexpected error: {e}") from e

    def _check_step_limit(self) -> None:
        """
        Check if step limit is exceeded.

        Raises:
            AgentStepLimitExceeded: If step limit is exceeded
        """
        self._step_count += 1
        if self._step_count > self._spec.step_limit:
            raise AgentStepLimitExceeded(
                f"Agent exceeded step limit of {self._spec.step_limit}"
            )
