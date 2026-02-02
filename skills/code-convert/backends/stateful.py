#!/usr/bin/env python3
"""
Stateful Backend Converter

Converts stateful/control flow nodes (Wait, Loop, SplitInBatches, SubWorkflow, Memory)
to Python BaseNode implementations.

These nodes maintain state across executions or control workflow execution flow.
"""

from __future__ import annotations
from typing import Any, Dict, List


# Stateful node configurations
STATEFUL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "wait": {
        "state_type": "timer",
        "blocking": True,
    },
    "loop": {
        "state_type": "iteration",
        "multi_output": True,
        "output_names": ["loop", "done"],
    },
    "splitinbatches": {
        "state_type": "batch",
        "multi_output": True,
        "output_names": ["batch", "done"],
    },
    "subworkflow": {
        "state_type": "nested",
        "blocking": True,
    },
    "executeworkflow": {
        "state_type": "nested",
        "blocking": True,
    },
    "buffer_memory": {
        "state_type": "session",
        "cross_execution": True,
    },
    "redis_memory": {
        "state_type": "session",
        "cross_execution": True,
        "external_storage": True,
    },
    "ai_agent": {
        "state_type": "orchestration",
        "complex": True,
    },
}


def convert_stateful_node(
    node_name: str,
    node_schema: Dict[str, Any],
    ts_code: str,
    properties: List[Dict[str, Any]],
    execution_contract: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Convert a stateful/control flow node to Python.
    
    Args:
        node_name: Node type name
        node_schema: Complete inferred schema
        ts_code: Raw TypeScript source code
        properties: Node parameters
        execution_contract: The node's execution contract
    
    Returns:
        Dict with python_code, imports, helpers, conversion_notes
    """
    node_name_lower = node_name.lower().replace("-", "").replace("_", "")
    io_cardinality = execution_contract.get("io_cardinality", {})
    state = execution_contract.get("state", {})
    
    # Get stateful configuration
    config = STATEFUL_CONFIGS.get(node_name_lower, {})
    state_type = config.get("state_type", "generic")
    multi_output = config.get("multi_output", False)
    output_names = io_cardinality.get("output_names", ["main"])
    cross_execution = config.get("cross_execution", False)
    
    # Generate helper methods based on state type
    if node_name_lower == "wait":
        helpers = _generate_wait_helpers()
    elif node_name_lower == "loop":
        helpers = _generate_loop_helpers()
    elif node_name_lower in ("splitinbatches", "split_in_batches"):
        helpers = _generate_batch_helpers()
    elif node_name_lower in ("subworkflow", "executeworkflow"):
        helpers = _generate_subworkflow_helpers()
    elif node_name_lower == "buffer_memory":
        helpers = _generate_buffer_memory_helpers()
    elif node_name_lower == "redis_memory":
        helpers = _generate_redis_memory_helpers()
    else:
        helpers = _generate_generic_stateful_helpers(node_name_lower)
    
    # Generate imports
    imports = [
        "import logging",
        "import time",
        "from typing import Any, Dict, List, Optional",
    ]
    
    # Add specific imports based on node type
    if node_name_lower == "wait":
        # time already imported
        pass
    elif node_name_lower in ("subworkflow", "executeworkflow"):
        imports.append("import uuid")
    elif cross_execution:
        imports.append("from datetime import datetime")
    
    conversion_notes = [
        f"Using stateful backend for {node_name}",
        f"State type: {state_type}",
        f"Multi-output: {multi_output}",
        f"Output names: {output_names}",
        f"Cross-execution state: {cross_execution}",
    ]
    
    return {
        "python_code": "",  # Execute method generated based on config
        "imports": imports,
        "helpers": helpers,
        "conversion_notes": conversion_notes,
        "state_type": state_type,
        "multi_output": multi_output,
        "output_names": output_names,
        "cross_execution": cross_execution,
    }


def _generate_wait_helpers() -> str:
    """Generate Wait node helper methods."""
    return '''
    def _wait(self, seconds: float) -> None:
        """
        Wait for the specified duration.
        
        SYNC-CELERY SAFE: Uses time.sleep() which is blocking but acceptable
        for short waits. For long waits (> 60s), consider using Celery's
        countdown/eta features instead.
        
        Args:
            seconds: Number of seconds to wait (max 60 for safety)
        """
        # Cap wait time to prevent blocking worker too long
        max_wait = 60
        actual_wait = min(seconds, max_wait)
        
        if seconds > max_wait:
            logger.warning(
                f"Wait time {seconds}s exceeds max {max_wait}s, capping to {max_wait}s"
            )
        
        time.sleep(actual_wait)
'''


def _generate_loop_helpers() -> str:
    """Generate Loop node helper methods."""
    return '''
    def _get_loop_state(self) -> Dict[str, Any]:
        """
        Get current loop state from context.
        
        Returns:
            Dict with current_iteration, max_iterations, completed
        """
        # Loop state is stored in node context
        state = getattr(self, "_loop_state", None)
        if state is None:
            state = {
                "current_iteration": 0,
                "max_iterations": 100,
                "completed": False,
                "items_per_iteration": [],
            }
            self._loop_state = state
        return state
    
    def _increment_iteration(self) -> int:
        """
        Increment iteration counter and return new value.
        """
        state = self._get_loop_state()
        state["current_iteration"] += 1
        return state["current_iteration"]
    
    def _is_loop_complete(self, mode: str, iterations: int = 10, condition_met: bool = False) -> bool:
        """
        Check if loop should complete.
        
        Args:
            mode: "count" or "condition"
            iterations: Max iterations for count mode
            condition_met: Whether exit condition is met for condition mode
        
        Returns:
            True if loop is complete
        """
        state = self._get_loop_state()
        
        if mode == "count":
            return state["current_iteration"] >= iterations
        elif mode == "condition":
            return condition_met
        else:
            # Safety: always complete after max iterations
            return state["current_iteration"] >= state["max_iterations"]
    
    def _prepare_loop_output(
        self,
        items: List["NodeExecutionData"],
        is_complete: bool,
    ) -> List[List["NodeExecutionData"]]:
        """
        Prepare output for loop node (2 outputs: loop, done).
        
        Args:
            items: Current items
            is_complete: Whether loop is complete
        
        Returns:
            [loop_output, done_output] - one will be empty
        """
        if is_complete:
            # Send to "done" output
            return [[], items]
        else:
            # Send to "loop" output for next iteration
            return [items, []]
'''


def _generate_batch_helpers() -> str:
    """Generate SplitInBatches node helper methods."""
    return '''
    def _get_batch_state(self) -> Dict[str, Any]:
        """
        Get current batch state from context.
        """
        state = getattr(self, "_batch_state", None)
        if state is None:
            state = {
                "current_batch": 0,
                "total_batches": 0,
                "all_items": [],
                "completed": False,
            }
            self._batch_state = state
        return state
    
    def _initialize_batches(
        self,
        items: List["NodeExecutionData"],
        batch_size: int,
    ) -> None:
        """
        Initialize batch processing state.
        
        Args:
            items: All items to process
            batch_size: Items per batch
        """
        state = self._get_batch_state()
        state["all_items"] = items
        state["current_batch"] = 0
        state["total_batches"] = (len(items) + batch_size - 1) // batch_size
        state["batch_size"] = batch_size
        state["completed"] = False
    
    def _get_next_batch(self) -> List["NodeExecutionData"]:
        """
        Get the next batch of items.
        
        Returns:
            Items in current batch
        """
        state = self._get_batch_state()
        
        if state["completed"]:
            return []
        
        batch_size = state.get("batch_size", 10)
        start = state["current_batch"] * batch_size
        end = start + batch_size
        
        batch = state["all_items"][start:end]
        state["current_batch"] += 1
        
        if state["current_batch"] >= state["total_batches"]:
            state["completed"] = True
        
        return batch
    
    def _prepare_batch_output(
        self,
        batch_items: List["NodeExecutionData"],
    ) -> List[List["NodeExecutionData"]]:
        """
        Prepare output for batch node (2 outputs: batch, done).
        
        Returns:
            [batch_output, done_output]
        """
        state = self._get_batch_state()
        
        if state["completed"]:
            # Last batch - send to both outputs
            return [batch_items, batch_items]
        else:
            # More batches - send to batch output only
            return [batch_items, []]
'''


def _generate_subworkflow_helpers() -> str:
    """Generate SubWorkflow/ExecuteWorkflow node helper methods."""
    return '''
    def _load_workflow(self, workflow_id: str) -> "WorkflowModel":
        """
        Load a workflow by ID.
        
        Args:
            workflow_id: The workflow ID to load
        
        Returns:
            WorkflowModel instance
        
        Raises:
            ValueError: If workflow not found
        """
        from database.config import get_sync_session_manual
        from database.crud import WorkflowCRUD
        from models import WorkflowModel
        
        with get_sync_session_manual() as session:
            workflow_db = WorkflowCRUD.get_workflow_sync(session, workflow_id)
            if not workflow_db:
                raise ValueError(f"Workflow not found: {workflow_id}")
            return WorkflowModel.model_validate(workflow_db)
    
    def _execute_subworkflow(
        self,
        workflow: "WorkflowModel",
        input_items: List["NodeExecutionData"],
    ) -> List["NodeExecutionData"]:
        """
        Execute a subworkflow synchronously.
        
        SYNC-CELERY SAFE: Uses synchronous execution.
        
        Args:
            workflow: The workflow to execute
            input_items: Items to pass to the workflow
        
        Returns:
            Output items from the workflow
        """
        from engine.execution import (
            ExecutionPlanBuilder,
            WorkflowExecutionContext,
            WorkflowExecutor,
        )
        
        # Build execution context
        primary_result = {
            "items": [
                {"json": item.json_data or {}, "binary": item.binary_data or {}, "index": i}
                for i, item in enumerate(input_items or [])
            ]
        }
        
        builder = ExecutionPlanBuilder(workflow)
        sorted_nodes = builder.topological_sort()
        
        context = WorkflowExecutionContext(
            workflow=workflow,
            execution_id=str(uuid.uuid4()),
            pub_sub=False,
            primary_result=primary_result,
        )
        
        executor = WorkflowExecutor(context)
        result = executor.execute(sorted_nodes)
        
        # Extract output items
        if result and isinstance(result, list):
            return result
        return []
'''


def _generate_buffer_memory_helpers() -> str:
    """Generate BufferMemory node helper methods."""
    return '''
    def _get_memory_key(self, session_id: str) -> str:
        """Generate memory storage key."""
        return f"buffer_memory:{session_id}"
    
    def _get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation messages from memory.
        
        Args:
            session_id: Session identifier
        
        Returns:
            List of message dicts with role and content
        """
        # Use in-memory storage (MemoryManager)
        from nodes.memory.buffer_memory import MemoryManager
        
        key = self._get_memory_key(session_id)
        return MemoryManager.get_messages(key)
    
    def _add_message(
        self,
        session_id: str,
        role: str,
        content: str,
    ) -> None:
        """
        Add a message to memory.
        
        Args:
            session_id: Session identifier
            role: Message role (user, assistant, system)
            content: Message content
        """
        from nodes.memory.buffer_memory import MemoryManager
        
        key = self._get_memory_key(session_id)
        MemoryManager.add_message(key, {"role": role, "content": content})
    
    def _clear_memory(self, session_id: str) -> None:
        """Clear all messages for a session."""
        from nodes.memory.buffer_memory import MemoryManager
        
        key = self._get_memory_key(session_id)
        MemoryManager.clear(key)
'''


def _generate_redis_memory_helpers() -> str:
    """Generate RedisMemory node helper methods."""
    return '''
    def _get_redis_client(self):
        """Get Redis client for memory storage."""
        import redis
        
        credentials = self.get_credentials("redisApi")
        
        if not credentials:
            raise Exception("Redis credentials not configured for memory")
        
        return redis.Redis(
            host=credentials.get("host", "localhost"),
            port=int(credentials.get("port", 6379)),
            db=int(credentials.get("database", 0)),
            password=credentials.get("password", None),
            decode_responses=True,
        )
    
    def _get_memory_key(self, session_id: str) -> str:
        """Generate Redis key for memory storage."""
        return f"avidflow:memory:{session_id}"
    
    def _get_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Get conversation messages from Redis.
        
        SYNC-CELERY SAFE: Synchronous Redis operations.
        """
        import json
        
        client = self._get_redis_client()
        key = self._get_memory_key(session_id)
        
        messages_json = client.lrange(key, 0, -1)
        return [json.loads(m) for m in messages_json]
    
    def _add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        ttl: int = 3600,
    ) -> None:
        """
        Add a message to Redis memory.
        
        Args:
            session_id: Session identifier
            role: Message role
            content: Message content
            ttl: Time to live in seconds
        """
        import json
        
        client = self._get_redis_client()
        key = self._get_memory_key(session_id)
        
        message = json.dumps({"role": role, "content": content})
        client.rpush(key, message)
        client.expire(key, ttl)
    
    def _clear_memory(self, session_id: str) -> None:
        """Clear Redis memory for a session."""
        client = self._get_redis_client()
        key = self._get_memory_key(session_id)
        client.delete(key)
'''


def _generate_generic_stateful_helpers(node_name: str) -> str:
    """Generate generic stateful helpers."""
    return f'''
    def _get_state(self) -> Dict[str, Any]:
        """
        Get current node state.
        
        Override for node-specific state management.
        """
        state = getattr(self, "_{node_name}_state", None)
        if state is None:
            state = {{}}
            self._{node_name}_state = state
        return state
    
    def _set_state(self, key: str, value: Any) -> None:
        """Set a state value."""
        state = self._get_state()
        state[key] = value
    
    def _clear_state(self) -> None:
        """Clear all state."""
        self._{node_name}_state = {{}}
'''
