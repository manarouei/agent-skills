"""
Agent Event Publisher for LangChain Runnables.

Publishes structured events to RabbitMQ following the standard workflow
updates envelope format, enabling real-time UI updates via WebSocket relay.
"""
from __future__ import annotations
from typing import Any, Dict, Optional
import time
import logging

from services.queue import QueueService

logger = logging.getLogger(__name__)


class AgentEventPublisher:
    """
    Publishes agent events to RabbitMQ with standard workflow envelope.
    
    Standard envelope format (aligns with workflow_message_handler):
    {
        "workflow_id": str,
        "execution_id": str,
        "node_name": str,
        "lane": int,
        "seq": int,
        "ts": int,
        "pub_sub": bool,
        "event": {...}  # Event-specific payload
    }
    
    Structured event types (for streaming):
    - model_token: {"type": "model_token", "text": str, "ts": int}
    - agent_started: {"type": "agent_started", "ts": int, "seq": int, "model": str, "tools_count": int}
    - agent_step: {"type": "agent_step", "content": str | None, "ts": int, "seq": int, "iteration": int}
    - tool_called: {"type": "tool_called", "name": str, "tool_call_id": str, "args": dict, "ts": int, "seq": int}
    - tool_result: {"type": "tool_result", "name": str, "tool_call_id": str, "ok": bool, "data": Any | None, "error": Any | None, "ts": int, "seq": int}
    - agent_completed: {"type": "agent_completed", "ts": int, "seq": int, "final_preview": str | None, "summary": dict}
    - agent_error: {"type": "agent_error", "ts": int, "seq": int, "message": str, "context": dict}
    - model_result: {"type": "model_result", "usage": dict, "_metadata": dict, "ts": int, "seq": int}
    - memory_result: {"type": "memory_result", "ok": bool, "operation": str, "ts": int, "seq": int}
    
    Usage:
        publisher = AgentEventPublisher(
            workflow_id="wf_123",
            execution_id="exec_456",
            node_name="AI Agent",
            lane=0,
            pub_sub=True,
            queue_service=queue_instance
        )
        
        # Publish events during agent execution
        publisher.agent_started(model="gpt-4", tools_count=3)
        publisher.tool_called(name="search", tool_call_id="call_1", args={"query": "n8n"})
        publisher.tool_result(name="search", tool_call_id="call_1", ok=True, data={...})
        publisher.agent_completed(final_preview="Result text", summary={...})
    """
    
    def __init__(
        self,
        workflow_id: str,
        execution_id: str,
        node_name: str,
        lane: int = 0,
        pub_sub: bool = True,
        queue_service: Optional[QueueService] = None
    ):
        """
        Initialize Agent Event Publisher.
        
        Args:
            workflow_id: Workflow identifier
            execution_id: Execution identifier
            node_name: Node name (e.g., "AI Agent")
            lane: Execution lane (default: 0)
            pub_sub: Whether to publish events (enable/disable publishing)
            queue_service: QueueService instance (creates new if None)
        """
        self.workflow_id = workflow_id
        self.execution_id = execution_id
        self.node_name = node_name
        self.lane = lane
        self.pub_sub = pub_sub
        self.queue_service = queue_service or QueueService()
        self._seq = 0  # Event sequence number
    
    def _publish(self, event: Dict[str, Any]) -> None:
        """
        Publish event with standard envelope.
        
        Args:
            event: Event payload (must include "type" field)
        """
        if not self.pub_sub:
            return
        
        self._seq += 1
        
        envelope = {
            "workflow_id": self.workflow_id,
            "execution_id": self.execution_id,
            "node_name": self.node_name,
            "lane": self.lane,
            "seq": self._seq,
            "ts": int(time.time() * 1000),  # milliseconds
            "pub_sub": True,
            "event": event
        }
        
        try:
            self.queue_service.publish_sync(
                queue_name="workflow_updates",
                message=envelope
            )
            logger.debug(f"[AgentEvents] Published {event.get('type')} event (seq={self._seq})")
        except Exception as e:
            logger.error(f"[AgentEvents] Failed to publish event: {e}")
    
    # ============================================================================
    # Agent Lifecycle Events
    # ============================================================================
    
    def agent_started(
        self,
        model: str,
        tools_count: int = 0,
        **kwargs: Any
    ) -> None:
        """
        Publish agent_started event.
        
        Args:
            model: Model identifier (e.g., "openai/gpt-4")
            tools_count: Number of available tools
            **kwargs: Additional context
        """
        self._publish({
            "type": "agent_started",
            "model": model,
            "tools_count": tools_count,
            "ts": int(time.time() * 1000),
            "seq": self._seq + 1,
            **kwargs
        })
    
    def agent_step(
        self,
        content: Optional[str] = None,
        iteration: int = 1,
        **kwargs: Any
    ) -> None:
        """
        Publish agent_step event (iteration start).
        
        Args:
            content: Optional step description
            iteration: Current iteration number
            **kwargs: Additional context
        """
        self._publish({
            "type": "agent_step",
            "content": content,
            "iteration": iteration,
            "ts": int(time.time() * 1000),
            "seq": self._seq + 1,
            **kwargs
        })
    
    def agent_completed(
        self,
        final_preview: Optional[str] = None,
        summary: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        """
        Publish agent_completed event.
        
        Args:
            final_preview: Preview of final response (truncated)
            summary: Summary stats (iterations, tools_used, etc.)
            **kwargs: Additional context
        """
        self._publish({
            "type": "agent_completed",
            "final_preview": final_preview,
            "summary": summary or {},
            "ts": int(time.time() * 1000),
            "seq": self._seq + 1,
            **kwargs
        })
    
    def agent_error(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        fatal: bool = False,
        **kwargs: Any
    ) -> None:
        """
        Publish agent_error event.
        
        Args:
            message: Error message
            context: Error context (transient, attempts, etc.)
            fatal: Whether error is fatal
            **kwargs: Additional context
        """
        self._publish({
            "type": "agent_error",
            "message": message,
            "context": context or {},
            "fatal": fatal,
            "ts": int(time.time() * 1000),
            "seq": self._seq + 1,
            **kwargs
        })
    
    # ============================================================================
    # Tool Events
    # ============================================================================
    
    def tool_called(
        self,
        name: str,
        tool_call_id: str,
        args: Dict[str, Any],
        **kwargs: Any
    ) -> None:
        """
        Publish tool_called event.
        
        Args:
            name: Tool name
            tool_call_id: Tool call identifier
            args: Tool arguments
            **kwargs: Additional context
        """
        self._publish({
            "type": "tool_called",
            "name": name,
            "tool_call_id": tool_call_id,
            "args": args,
            "ts": int(time.time() * 1000),
            "seq": self._seq + 1,
            **kwargs
        })
    
    def tool_result(
        self,
        name: str,
        tool_call_id: str,
        ok: bool,
        data: Optional[Any] = None,
        error: Optional[Any] = None,
        **kwargs: Any
    ) -> None:
        """
        Publish tool_result event.
        
        Args:
            name: Tool name
            tool_call_id: Tool call identifier
            ok: Whether tool execution succeeded
            data: Tool result data (on success)
            error: Error information (on failure)
            **kwargs: Additional context
        """
        self._publish({
            "type": "tool_result",
            "name": name,
            "tool_call_id": tool_call_id,
            "ok": ok,
            "data": data,
            "error": error,
            "ts": int(time.time() * 1000),
            "seq": self._seq + 1,
            **kwargs
        })
    
    # ============================================================================
    # Model Events
    # ============================================================================
    
    def model_result(
        self,
        usage: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        preview: Optional[str] = None,
        **kwargs: Any
    ) -> None:
        """
        Publish model_result event.
        
        Args:
            usage: Token usage stats
            metadata: Model metadata (provider, latency, etc.)
            preview: Response preview (truncated)
            **kwargs: Additional context
        """
        self._publish({
            "type": "model_result",
            "usage": usage,
            "_metadata": metadata or {},
            "preview": preview,
            "ts": int(time.time() * 1000),
            "seq": self._seq + 1,
            **kwargs
        })
    
    def model_token(
        self,
        text: str,
        **kwargs: Any
    ) -> None:
        """
        Publish model_token event (for streaming).
        
        Args:
            text: Token/chunk text
            **kwargs: Additional context
        """
        self._publish({
            "type": "model_token",
            "text": text,
            "ts": int(time.time() * 1000),
            **kwargs
        })
    
    # ============================================================================
    # Memory Events
    # ============================================================================
    
    def memory_result(
        self,
        ok: bool,
        operation: str = "save",
        meta: Optional[Dict[str, Any]] = None,
        **kwargs: Any
    ) -> None:
        """
        Publish memory_result event.
        
        Args:
            ok: Whether memory operation succeeded
            operation: Operation type (save, load, clear)
            meta: Memory metadata (session_id, messages_count, etc.)
            **kwargs: Additional context
        """
        self._publish({
            "type": "memory_result",
            "ok": ok,
            "operation": operation,
            "meta": meta or {},
            "ts": int(time.time() * 1000),
            "seq": self._seq + 1,
            **kwargs
        })
