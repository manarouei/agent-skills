"""Structured JSON logging with trace context."""
import logging
import sys
from typing import Any

from pythonjsonlogger import jsonlogger

from agentic_system.config import get_settings


class TraceContextFilter(logging.Filter):
    """Add trace context to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add default trace context fields if not present."""
        if not hasattr(record, "trace_id"):
            record.trace_id = None
        if not hasattr(record, "job_id"):
            record.job_id = None
        if not hasattr(record, "agent_id"):
            record.agent_id = None
        if not hasattr(record, "skill_name"):
            record.skill_name = None
        if not hasattr(record, "skill_version"):
            record.skill_version = None
        return True


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter with standardized field names."""

    def add_fields(
        self,
        log_record: dict[str, Any],
        record: logging.LogRecord,
        message_dict: dict[str, Any],
    ) -> None:
        """Add custom fields to the log record."""
        super().add_fields(log_record, record, message_dict)

        # Ensure timestamp is present
        if "timestamp" not in log_record:
            log_record["timestamp"] = self.formatTime(record, self.datefmt)

        # Add standard fields
        log_record["level"] = record.levelname
        log_record["logger"] = record.name

        # Add trace context if present
        if hasattr(record, "trace_id") and record.trace_id:
            log_record["trace_id"] = record.trace_id
        if hasattr(record, "job_id") and record.job_id:
            log_record["job_id"] = record.job_id
        if hasattr(record, "agent_id") and record.agent_id:
            log_record["agent_id"] = record.agent_id
        if hasattr(record, "skill_name") and record.skill_name:
            log_record["skill_name"] = record.skill_name
        if hasattr(record, "skill_version") and record.skill_version:
            log_record["skill_version"] = record.skill_version


def setup_logging() -> None:
    """Configure structured JSON logging for the application."""
    settings = get_settings()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    # Create formatter
    formatter = CustomJsonFormatter(
        "%(timestamp)s %(level)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)

    # Add trace context filter
    handler.addFilter(TraceContextFilter())

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(settings.log_level)

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)


def get_logger(name: str) -> logging.LoggerAdapter:
    """
    Get a logger with trace context support.

    Args:
        name: Logger name (typically __name__)

    Returns:
        LoggerAdapter that can accept trace context in extra dict
    """
    logger = logging.getLogger(name)
    return logging.LoggerAdapter(logger, extra={})


def with_trace_context(
    logger: logging.LoggerAdapter,
    trace_id: str | None = None,
    job_id: str | None = None,
    agent_id: str | None = None,
    skill_name: str | None = None,
    skill_version: str | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Create an extra dict with trace context for logging.

    Args:
        logger: Logger adapter
        trace_id: Trace ID
        job_id: Job ID
        agent_id: Agent ID
        skill_name: Skill name
        skill_version: Skill version
        **kwargs: Additional context fields

    Returns:
        Dict to pass as extra parameter to logger methods
    """
    extra = kwargs.copy()
    if trace_id:
        extra["trace_id"] = trace_id
    if job_id:
        extra["job_id"] = job_id
    if agent_id:
        extra["agent_id"] = agent_id
    if skill_name:
        extra["skill_name"] = skill_name
    if skill_version:
        extra["skill_version"] = skill_version
    return extra
