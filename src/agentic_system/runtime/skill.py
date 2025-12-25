"""Base skill class with validation and timeout enforcement."""
import signal
from abc import ABC, abstractmethod
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from agentic_system.observability import get_logger, with_trace_context
from agentic_system.runtime.contracts import ExecutionContext, SideEffect, SkillSpec

logger = get_logger(__name__)

InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


class SkillError(Exception):
    """Base exception for skill errors."""

    pass


class SkillTimeoutError(SkillError):
    """Raised when skill execution times out."""

    pass


class SkillValidationError(SkillError):
    """Raised when skill input/output validation fails."""

    pass


class Skill(ABC):
    """
    Base class for all skills.

    Enforces input validation, timeout, and structured error handling.
    """

    def __init__(self):
        """Initialize skill."""
        self._spec = self.spec()

    @abstractmethod
    def spec(self) -> SkillSpec:
        """
        Return skill specification.

        Returns:
            SkillSpec defining the skill's metadata
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
    def _execute(self, input_data: InputT, context: ExecutionContext) -> OutputT:
        """
        Execute skill logic (implemented by subclasses).

        Args:
            input_data: Validated input data
            context: Execution context

        Returns:
            Validated output data
        """
        pass

    def execute(
        self,
        input_data: dict[str, Any] | BaseModel,
        context: ExecutionContext,
    ) -> dict[str, Any]:
        """
        Execute skill with validation and timeout enforcement.

        Args:
            input_data: Input data (dict or Pydantic model)
            context: Execution context

        Returns:
            Output data as dict

        Raises:
            SkillValidationError: If input/output validation fails
            SkillTimeoutError: If execution times out
            SkillError: For other skill-specific errors
        """
        extra = with_trace_context(
            logger,
            trace_id=context.trace_id,
            job_id=context.job_id,
            agent_id=context.agent_id,
            skill_name=self._spec.name,
            skill_version=self._spec.version,
        )

        logger.info("Skill execution started", extra=extra)

        try:
            # Validate input
            input_model_class = self.input_model()
            if isinstance(input_data, dict):
                try:
                    validated_input = input_model_class.model_validate(input_data)
                except ValidationError as e:
                    raise SkillValidationError(f"Input validation failed: {e}")
            else:
                validated_input = input_data

            # Set timeout using alarm signal (KISS approach for sync execution)
            def timeout_handler(signum, frame):
                raise SkillTimeoutError(
                    f"Skill execution timed out after {self._spec.timeout_s}s"
                )

            # Note: signal.alarm only works on Unix; for production, consider threading.Timer
            # or async timeout. Keeping simple for now.
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(self._spec.timeout_s)

            try:
                # Execute skill logic
                output = self._execute(validated_input, context)

                # Validate output
                output_model_class = self.output_model()
                if not isinstance(output, output_model_class):
                    try:
                        output = output_model_class.model_validate(output)
                    except ValidationError as e:
                        raise SkillValidationError(f"Output validation failed: {e}")

                logger.info("Skill execution completed", extra=extra)
                return output.model_dump()

            finally:
                # Cancel alarm
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

        except SkillError:
            # Re-raise skill errors
            logger.error("Skill execution failed", extra=extra, exc_info=True)
            raise
        except Exception as e:
            # Wrap unexpected errors
            logger.error(
                "Unexpected skill error",
                extra=extra,
                exc_info=True,
            )
            raise SkillError(f"Unexpected error: {e}") from e
