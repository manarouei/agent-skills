"""
Langfuse v3 client and helper functions for workflow observability.

This module provides a production-ready Langfuse integration that:
- Gracefully degrades when Langfuse credentials are not configured
- Uses the new Langfuse v3 SDK (OpenTelemetry-based)
- Provides helper functions for common tracing patterns

Usage:
    from observability.langfuse_client import create_workflow_trace, create_node_span

    with create_workflow_trace(...) as trace_ctx:
        with create_node_span(...) as span:
            # Your node logic here
            pass

Environment Variables:
    LANGFUSE_PUBLIC_KEY: Your Langfuse public key
    LANGFUSE_SECRET_KEY: Your Langfuse secret key
    LANGFUSE_BASE_URL: Optional - for self-hosted Langfuse instances
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Generator, Optional

from config import settings

logger = logging.getLogger(__name__)

# Module-level flag to track initialization status
_langfuse_enabled: bool = False
_initialization_attempted: bool = False

# TEMPORARY: Force disable Langfuse due to 502 Bad Gateway errors from OTLP exporter
# Set to False to re-enable when Langfuse service is stable
_LANGFUSE_FORCE_DISABLED: bool = True


def _initialize_langfuse() -> None:
    """
    Initialize Langfuse by setting environment variables.
    
    The Langfuse v3 SDK auto-initializes via environment variables.
    """
    global _langfuse_enabled, _initialization_attempted
    
    if _initialization_attempted:
        return
    
    _initialization_attempted = True
    
    # Skip initialization if force disabled
    if _LANGFUSE_FORCE_DISABLED:
        logger.info("[Langfuse] Disabled via _LANGFUSE_FORCE_DISABLED flag")
        _langfuse_enabled = False
        return
    
    public_key = settings.LANGFUSE_PUBLIC_KEY
    secret_key = settings.LANGFUSE_SECRET_KEY
    
    if not public_key or not secret_key:
        logger.warning(
            "[Langfuse] LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY not configured. "
            "Tracing will be disabled. Set these env vars to enable observability."
        )
        _langfuse_enabled = False
        return
    
    try:
        # Set environment variables for Langfuse v3 auto-initialization
        os.environ["LANGFUSE_PUBLIC_KEY"] = public_key
        os.environ["LANGFUSE_SECRET_KEY"] = secret_key
        if settings.LANGFUSE_BASE_URL:
            os.environ["LANGFUSE_HOST"] = settings.LANGFUSE_BASE_URL
        
        # Import to trigger initialization
        from langfuse import get_client
        
        client = get_client()
        _langfuse_enabled = True
        
        logger.info(
            "[Langfuse] Client initialized successfully. "
            f"Base URL: {settings.LANGFUSE_BASE_URL or 'cloud.langfuse.com'}"
        )
        
    except ImportError as e:
        logger.error(
            f"[Langfuse] Failed to import langfuse package: {e}. "
            "Ensure langfuse>=3.0.0 is installed"
        )
        _langfuse_enabled = False
    except Exception as e:
        logger.error(f"[Langfuse] Failed to initialize client: {e}")
        _langfuse_enabled = False


def is_langfuse_enabled() -> bool:
    """
    Check if Langfuse tracing is enabled.
    
    Returns:
        True if Langfuse is properly configured and initialized.
    """
    _initialize_langfuse()
    return _langfuse_enabled


def get_langfuse_client():
    """
    Get the Langfuse client instance (v3 API).
    
    Returns:
        Langfuse client if configured, None otherwise.
    """
    if not is_langfuse_enabled():
        return None
    
    try:
        from langfuse import get_client
        return get_client()
    except Exception as e:
        logger.error(f"[Langfuse] Failed to get client: {e}")
        return None


def get_current_trace_id() -> Optional[str]:
    """
    Get the current trace ID if a trace is active.
    
    Returns:
        The current trace ID string, or None if no trace is active.
    """
    if not is_langfuse_enabled():
        return None
    
    try:
        from langfuse import get_client
        client = get_client()
        return client.get_current_trace_id()
    except Exception:
        return None


@dataclass
class TraceContext:
    """Wrapper for trace context with helper methods."""
    trace_id: str
    _span: Any = None
    
    def update(self, **kwargs) -> None:
        """Update the trace with additional data."""
        if self._span:
            try:
                self._span.update(**kwargs)
            except Exception as e:
                logger.warning(f"[Langfuse] Error updating trace: {e}")
    
    def update_trace(self, **kwargs) -> None:
        """Update trace-level attributes."""
        if self._span:
            try:
                self._span.update_trace(**kwargs)
            except Exception as e:
                logger.warning(f"[Langfuse] Error updating trace: {e}")


@contextmanager
def create_workflow_trace(
    name: str,
    workflow_id: str,
    execution_id: str,
    user_id: Optional[str] = None,
    workflow_name: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[list] = None,
    input_data: Optional[Any] = None,
) -> Generator[Optional[TraceContext], None, None]:
    """
    Create a Langfuse trace for a workflow execution using v3 API.
    
    Args:
        name: Trace name (e.g., "workflow.execute_workflow")
        workflow_id: The workflow's unique ID
        execution_id: The execution's unique ID
        user_id: Optional user ID for the trace
        workflow_name: Optional workflow name for metadata
        metadata: Additional metadata to attach to the trace
        tags: Tags for categorizing the trace
        input_data: The workflow input data
    
    Yields:
        TraceContext wrapper with trace_id, or None if Langfuse is disabled.
    """
    if not is_langfuse_enabled():
        yield None
        return
    
    try:
        from langfuse import get_client, propagate_attributes, Langfuse
        
        client = get_client()
        
        # Build metadata
        trace_metadata = {
            "workflow_id": workflow_id,
            "execution_id": execution_id,
            "environment": getattr(settings, 'ENV', 'development'),
            **({"workflow_name": workflow_name} if workflow_name else {}),
            **(metadata or {}),
        }
        
        # Generate deterministic trace ID from execution_id
        trace_id = Langfuse.create_trace_id(seed=execution_id)
        
        # Create root span with trace context
        with client.start_as_current_observation(
            as_type="span",
            name=name,
            input=input_data,
            metadata=trace_metadata,
            trace_context={"trace_id": trace_id},
        ) as span:
            # propagate_attributes() only accepts string values for metadata
            # Convert non-string values to strings
            propagate_metadata = {
                k: str(v) if not isinstance(v, str) else v 
                for k, v in trace_metadata.items()
            }
            
            # Propagate attributes to all child spans
            with propagate_attributes(
                user_id=user_id,
                session_id=execution_id,
                tags=tags or ["workflow-engine"],
                metadata=propagate_metadata,
            ):
                ctx = TraceContext(trace_id=trace_id, _span=span)
                try:
                    yield ctx
                finally:
                    # Flush on completion
                    try:
                        client.flush()
                    except Exception as e:
                        logger.warning(f"[Langfuse] Error flushing: {e}")
                        
    except Exception as e:
        logger.warning(f"[Langfuse] Error creating trace: {e}")
        yield None


@dataclass
class SpanContext:
    """Wrapper for span context with helper methods."""
    span_id: str
    _span: Any = None
    
    def update(self, **kwargs) -> None:
        """Update the span with additional data."""
        if self._span:
            try:
                self._span.update(**kwargs)
            except Exception as e:
                logger.warning(f"[Langfuse] Error updating span: {e}")


@contextmanager
def create_node_span(
    name: str,
    node_type: str,
    node_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    execution_id: Optional[str] = None,
    parent_trace: Any = None,  # Legacy parameter, ignored in v3
    metadata: Optional[Dict[str, Any]] = None,
    input_data: Optional[Any] = None,
) -> Generator[Optional[SpanContext], None, None]:
    """
    Create a Langfuse span for a workflow node execution.
    
    Args:
        name: Node name
        node_type: The type of node (e.g., "AI Agent", "HTTP Request")
        node_id: Optional node's unique ID
        workflow_id: Optional workflow ID (added to metadata)
        execution_id: Optional execution ID (added to metadata)
        parent_trace: Legacy parameter, ignored in v3 (context is automatic)
        metadata: Additional metadata
        input_data: Input to the node
    
    Yields:
        SpanContext wrapper, or None if Langfuse is disabled.
    """
    if not is_langfuse_enabled():
        yield None
        return
    
    try:
        from langfuse import get_client
        
        client = get_client()
        
        span_metadata = {
            "node_type": node_type,
            **({"node_id": node_id} if node_id else {}),
            **({"workflow_id": workflow_id} if workflow_id else {}),
            **({"execution_id": execution_id} if execution_id else {}),
            **(metadata or {}),
        }
        
        with client.start_as_current_observation(
            as_type="span",
            name=name,
            input=input_data,
            metadata=span_metadata,
        ) as span:
            ctx = SpanContext(span_id=span.id if hasattr(span, 'id') else "", _span=span)
            try:
                yield ctx
            except Exception as e:
                # Mark span as error
                span.update(
                    level="ERROR",
                    status_message=str(e),
                )
                raise
                
    except Exception as e:
        logger.warning(f"[Langfuse] Error creating span: {e}")
        yield None


@dataclass
class GenerationContext:
    """Wrapper for generation context with helper methods."""
    generation_id: str
    _generation: Any = None
    
    def update(self, output: Any = None, usage: Any = None, metadata: Any = None, **kwargs) -> None:
        """
        Update the generation with additional data.
        
        Args:
            output: The LLM output
            usage: Token usage dict (will be converted to usage_details)
            metadata: Additional metadata
            **kwargs: Other parameters passed to the underlying update
        """
        if self._generation:
            try:
                update_kwargs = {}
                if output is not None:
                    update_kwargs["output"] = output
                if metadata is not None:
                    update_kwargs["metadata"] = metadata
                
                # Convert usage to usage_details for v3 API
                if usage is not None:
                    usage_details = {}
                    if isinstance(usage, dict):
                        if "input_tokens" in usage or "prompt_tokens" in usage:
                            usage_details["input_tokens"] = usage.get("input_tokens") or usage.get("prompt_tokens", 0)
                        if "output_tokens" in usage or "completion_tokens" in usage:
                            usage_details["output_tokens"] = usage.get("output_tokens") or usage.get("completion_tokens", 0)
                        if "total_tokens" in usage:
                            usage_details["total_tokens"] = usage.get("total_tokens", 0)
                    if usage_details:
                        update_kwargs["usage_details"] = usage_details
                
                update_kwargs.update(kwargs)
                self._generation.update(**update_kwargs)
            except Exception as e:
                logger.warning(f"[Langfuse] Error updating generation: {e}")


@contextmanager
def create_llm_generation(
    name: str,
    model: str,
    provider: Optional[str] = None,
    input_messages: Optional[Any] = None,
    model_parameters: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Generator[Optional[GenerationContext], None, None]:
    """
    Create a Langfuse generation for an LLM call.
    
    Args:
        name: Name for the generation
        model: The model being used
        provider: Optional provider name (e.g., "openai", "anthropic")
        input_messages: Input messages/prompt
        model_parameters: Model parameters (temperature, etc.)
        metadata: Additional metadata
    
    Yields:
        GenerationContext wrapper, or None if Langfuse is disabled.
    """
    if not is_langfuse_enabled():
        yield None
        return
    
    try:
        from langfuse import get_client
        
        client = get_client()
        
        gen_metadata = {
            **({"provider": provider} if provider else {}),
            **(metadata or {}),
        }
        
        with client.start_as_current_observation(
            as_type="generation",
            name=name,
            model=model,
            input=input_messages,
            model_parameters=model_parameters,
            metadata=gen_metadata,
        ) as gen:
            ctx = GenerationContext(
                generation_id=gen.id if hasattr(gen, 'id') else "",
                _generation=gen
            )
            try:
                yield ctx
            except Exception as e:
                gen.update(
                    level="ERROR",
                    status_message=str(e),
                )
                raise
                
    except Exception as e:
        logger.warning(f"[Langfuse] Error creating generation: {e}")
        yield None


def create_score(
    trace_id: str,
    name: str,
    value: float,
    comment: Optional[str] = None,
    observation_id: Optional[str] = None,
    data_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Create a score/feedback for a trace or observation using v3 API.
    
    Args:
        trace_id: The trace ID to score
        name: Name of the score (e.g., "user-feedback", "accuracy")
        value: Numeric score value (0.0 to 1.0 for most scores)
        comment: Optional comment
        observation_id: Optional specific observation to score
        data_type: Optional type: "NUMERIC", "CATEGORICAL", or "BOOLEAN"
        metadata: Optional additional metadata
    
    Returns:
        True if score was created successfully, False otherwise.
    """
    if not is_langfuse_enabled():
        return False
    
    try:
        from langfuse import get_client
        
        client = get_client()
        
        # v3 API uses create_score() instead of score()
        client.create_score(
            trace_id=trace_id,
            observation_id=observation_id,
            name=name,
            value=value,
            comment=comment,
            data_type=data_type,
            metadata=metadata,
        )
        
        # Flush to ensure the score is sent immediately
        client.flush()
        
        return True
        
    except Exception as e:
        logger.warning(f"[Langfuse] Error creating score: {e}")
        return False


def flush_langfuse() -> None:
    """Flush all pending Langfuse events."""
    if not is_langfuse_enabled():
        return
    
    try:
        from langfuse import get_client
        client = get_client()
        client.flush()
    except Exception as e:
        logger.warning(f"[Langfuse] Error flushing: {e}")


def shutdown_langfuse() -> None:
    """Gracefully shutdown Langfuse client."""
    if not is_langfuse_enabled():
        return
    
    try:
        from langfuse import get_client
        client = get_client()
        client.shutdown()
    except Exception as e:
        logger.warning(f"[Langfuse] Error shutting down: {e}")
