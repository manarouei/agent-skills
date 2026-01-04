"""
Hybrid Adapter - Bridge between tool-style and agent-style execution.

This module provides adapters that let existing SkillExecutor run as
"degenerate agents" - returning AgentResponse instead of ExecutionResult.

KEY BEHAVIORS:
1. One-shot completion: ExecutionResult.SUCCESS → AgentResponse(COMPLETED)
2. Missing inputs: Detected missing required fields → AgentResponse(INPUT_REQUIRED)
3. Failures remain failures: ExecutionResult.FAILED → AgentResponse(FAILED)
4. Gates block: ExecutionResult.BLOCKED → AgentResponse(BLOCKED)

RESUMPTION:
- On INPUT_REQUIRED, state is persisted to StateStore
- Subsequent call with same context_id resumes from stored state
- State includes: turn_number, partial outputs, received inputs
- Resume token validation prevents stale state conflicts

CONTRACT ENFORCEMENT:
- Skills can only return intermediate states declared in interaction_outcomes
- DELEGATING state blocked without router (not implemented)
- Undeclared intermediate states result in BLOCKED

SYNC-CELERY SAFE:
- No async, no threads, no event loops
- All state persisted to StateStore between turns
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .protocol import (
    AgentId,
    AgentResponse,
    AgentResponseMetadata,
    ContextId,
    InputFieldSpec,
    InputRequest,
    MessageEnvelope,
    MessageType,
    TaskState,
    execution_status_to_task_state,
)
from .state_store import (
    ConversationEvent,
    ContextState,
    PocketFact,
    SQLiteStateStore,
    StateStore,
    create_state_store,
)


# Router availability flag - set to True when runtime/router.py is implemented
ROUTER_ENABLED = False


class ResumeTokenConflictError(Exception):
    """Raised when resume token validation fails."""
    def __init__(self, context_id: str, message: str = "State has changed since token was issued"):
        self.context_id = context_id
        super().__init__(f"Resume token conflict for context {context_id}: {message}")


class AgentAdapter:
    """
    Adapter wrapping SkillExecutor for agent-style execution.
    
    This is the minimal hybrid layer that enables:
    1. Trivial skills to run as one-shot tools
    2. Complex skills to pause and request input
    3. All state to persist for Celery-safe resumption
    4. Contract enforcement for intermediate states
    """
    
    def __init__(
        self,
        executor: Any,  # SkillExecutor (avoiding circular import)
        state_store: StateStore | None = None,
        max_turns: int = 8,
    ):
        """
        Initialize adapter.
        
        Args:
            executor: SkillExecutor instance
            state_store: StateStore for persistence (default: SQLiteStateStore)
            max_turns: Max turns per context before escalation
        """
        self.executor = executor
        self.state_store = state_store or create_state_store(shared=True)
        self.max_turns = max_turns
    
    def invoke(
        self,
        skill_name: str,
        inputs: Dict[str, Any],
        context_id: str,
        resume: bool = False,
        resume_token: Optional[str] = None,
    ) -> AgentResponse:
        """
        Invoke a skill with agent semantics.
        
        Args:
            skill_name: Name of skill to execute
            inputs: Input parameters
            context_id: Correlation/context ID
            resume: If True, this is a follow-up turn with additional inputs
            resume_token: Token from previous response for conflict detection
        
        Returns:
            AgentResponse with state (may be terminal or INPUT_REQUIRED)
        
        Resume Token Validation:
            When resume=True and resume_token is provided, validates that the
            state hasn't changed since the token was issued. If validation fails,
            returns BLOCKED with conflict details.
        """
        start_time = time.time()
        agent_id = AgentId(skill_name)
        ctx_id = ContextId(context_id)
        
        # Load existing state if resuming
        state = self.state_store.get_state(context_id)
        current_turn = 1
        
        if state:
            current_turn = state.current_turn + 1
            
            # Validate resume token if provided (conflict detection)
            if resume and resume_token:
                if not self.state_store.validate_resume_token(context_id, resume_token):
                    return AgentResponse(
                        state=TaskState.BLOCKED,
                        errors=[
                            f"Resume token conflict: state has changed since token was issued. "
                            f"Please refresh state and retry."
                        ],
                        turn_number=current_turn,
                        duration_ms=int((time.time() - start_time) * 1000),
                        metadata=AgentResponseMetadata(
                            agent_state="conflict",
                            detailed_reason="Resume token validation failed - concurrent modification detected",
                        ),
                    )
            
            # Check turn limit
            if current_turn > self.max_turns:
                return AgentResponse(
                    state=TaskState.ESCALATED,
                    errors=[f"Max turns ({self.max_turns}) exceeded for context {context_id}"],
                    turn_number=current_turn,
                    duration_ms=int((time.time() - start_time) * 1000),
                )
            
            # Merge stored inputs with new inputs
            stored_inputs = self.state_store.get_facts_by_bucket(context_id, "inputs")
            merged_inputs = {**stored_inputs, **inputs}
            inputs = merged_inputs
        
        # Store current inputs as facts
        for key, value in inputs.items():
            self.state_store.put_fact(
                context_id,
                PocketFact(bucket="inputs", key=key, value=value),
            )
        
        # Load contract for validation
        contract = self.executor.registry.get(skill_name)
        
        # Check for missing required inputs BEFORE execution
        missing_fields = self._check_required_inputs(inputs, contract.input_schema)
        
        if missing_fields:
            # Validate that INPUT_REQUIRED is allowed by contract
            response = self._create_input_required_response(
                skill_name, contract, missing_fields, context_id, 
                current_turn, agent_id, start_time
            )
            return response
        
        # Execute skill through executor
        result = self.executor.execute(skill_name, inputs, context_id)
        
        # Convert ExecutionStatus to TaskState
        task_state = execution_status_to_task_state(result.status.value)
        
        # Contract enforcement: validate intermediate states
        if TaskState.is_resumable(task_state):
            duration_ms = int((time.time() - start_time) * 1000)
            validation_result = self._validate_intermediate_state(
                task_state, contract, skill_name,
                turn_number=current_turn,
                duration_ms=duration_ms,
            )
            if validation_result:
                return validation_result
        
        # Record event
        self.state_store.append_event(
            context_id,
            ConversationEvent(
                event_type="execution_completed",
                payload={
                    "status": result.status.value,
                    "outputs_keys": list(result.outputs.keys()),
                    "error_count": len(result.errors),
                },
                turn_number=current_turn,
                agent_id=str(agent_id),
            ),
        )
        
        # Update state
        self.state_store.update_task_state(context_id, task_state.value, current_turn)
        
        # Store outputs as facts
        for key, value in result.outputs.items():
            self.state_store.put_fact(
                context_id,
                PocketFact(bucket="outputs", key=key, value=value),
            )
        
        # Generate resume token for non-terminal states
        new_resume_token = None
        if not TaskState.is_terminal(task_state):
            new_resume_token = self.state_store.generate_resume_token(context_id)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return AgentResponse(
            state=task_state,
            outputs=result.outputs,
            errors=result.errors,
            turn_number=current_turn,
            state_handle=context_id if not TaskState.is_terminal(task_state) else None,
            duration_ms=duration_ms,
            resume_token=new_resume_token,
        )
    
    def _create_input_required_response(
        self,
        skill_name: str,
        contract: Any,
        missing_fields: List[InputFieldSpec],
        context_id: str,
        current_turn: int,
        agent_id: AgentId,
        start_time: float,
    ) -> AgentResponse:
        """Create INPUT_REQUIRED response with contract validation."""
        # Validate that INPUT_REQUIRED is allowed by contract
        duration_ms = int((time.time() - start_time) * 1000)
        validation_result = self._validate_intermediate_state(
            TaskState.INPUT_REQUIRED, contract, skill_name,
            turn_number=current_turn,
            duration_ms=duration_ms,
        )
        if validation_result:
            return validation_result
        
        # Store state and return INPUT_REQUIRED
        self.state_store.update_task_state(
            context_id, TaskState.INPUT_REQUIRED.value, current_turn,
            agent_state_detail="input_required",
            input_request_payload={"missing_fields": [f.name for f in missing_fields]},
        )
        self.state_store.append_event(
            context_id,
            ConversationEvent(
                event_type="input_required",
                payload={"missing_fields": [f.name for f in missing_fields]},
                turn_number=current_turn,
                agent_id=str(agent_id),
            ),
        )
        
        # Generate resume token
        new_resume_token = self.state_store.generate_resume_token(context_id)
        
        return AgentResponse(
            state=TaskState.INPUT_REQUIRED,
            input_request=InputRequest(
                missing_fields=missing_fields,
                reason=f"Skill '{skill_name}' requires additional inputs",
                partial_outputs={},
            ),
            turn_number=current_turn,
            state_handle=context_id,
            duration_ms=int((time.time() - start_time) * 1000),
            resume_token=new_resume_token,
            metadata=AgentResponseMetadata(
                agent_state="input_required",
                detailed_reason=f"Missing required fields: {[f.name for f in missing_fields]}",
            ),
        )
    
    def _validate_intermediate_state(
        self,
        task_state: TaskState,
        contract: Any,
        skill_name: str,
        turn_number: int = 1,
        duration_ms: int = 0,
    ) -> Optional[AgentResponse]:
        """
        Validate that an intermediate state is allowed by the skill contract.
        
        Returns AgentResponse with BLOCKED if validation fails, None if valid.
        
        Args:
            task_state: The intermediate state being validated
            contract: SkillContract from registry
            skill_name: Name of skill for error messages
            turn_number: Current turn number (for response)
            duration_ms: Elapsed duration (for response)
        """
        # DELEGATING is always blocked without router
        if task_state == TaskState.DELEGATING:
            if not ROUTER_ENABLED:
                return AgentResponse(
                    state=TaskState.BLOCKED,
                    errors=[
                        f"Skill '{skill_name}' attempted DELEGATING but router is not enabled. "
                        f"Delegation requires runtime/router.py to be implemented."
                    ],
                    turn_number=turn_number,
                    duration_ms=duration_ms,
                    metadata=AgentResponseMetadata(
                        agent_state="blocked",
                        detailed_reason="DELEGATING state forbidden without router implementation",
                    ),
                )
        
        # Check if contract allows this intermediate state
        if not contract.interaction_outcomes:
            # No interaction_outcomes declared = tool-only skill
            return AgentResponse(
                state=TaskState.BLOCKED,
                errors=[
                    f"Skill '{skill_name}' returned intermediate state '{task_state.value}' "
                    f"but has no interaction_outcomes declared in contract. "
                    f"Add interaction_outcomes to SKILL.md or return only terminal states."
                ],
                turn_number=turn_number,
                duration_ms=duration_ms,
                metadata=AgentResponseMetadata(
                    agent_state="blocked",
                    detailed_reason="Contract violation: undeclared intermediate state",
                ),
            )
        
        # Map TaskState to IntermediateState name
        state_name_map = {
            TaskState.INPUT_REQUIRED: "input_required",
            TaskState.DELEGATING: "delegating",
            TaskState.PAUSED: "paused",
        }
        state_name = state_name_map.get(task_state)
        
        if state_name:
            allowed = [s.value for s in contract.interaction_outcomes.allowed_intermediate_states]
            if state_name not in allowed:
                return AgentResponse(
                    state=TaskState.BLOCKED,
                    errors=[
                        f"Skill '{skill_name}' returned '{task_state.value}' but contract only allows: {allowed}. "
                        f"Update interaction_outcomes.allowed_intermediate_states in SKILL.md."
                    ],
                    turn_number=turn_number,
                    duration_ms=duration_ms,
                    metadata=AgentResponseMetadata(
                        agent_state="blocked",
                        detailed_reason=f"Contract violation: {task_state.value} not in allowed_intermediate_states",
                    ),
                )
        
        return None  # Validation passed
    
    def _check_required_inputs(
        self,
        inputs: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> List[InputFieldSpec]:
        """Check for missing required inputs and return specs."""
        missing = []
        required = schema.get("required", [])
        properties = schema.get("properties", {})
        
        for field_name in required:
            if field_name not in inputs or inputs[field_name] is None:
                field_schema = properties.get(field_name, {})
                missing.append(InputFieldSpec(
                    name=field_name,
                    type=field_schema.get("type", "string"),
                    description=field_schema.get("description", ""),
                    required=True,
                ))
        
        return missing
    
    def get_context_state(self, context_id: str) -> Optional[ContextState]:
        """Get full context state for inspection."""
        return self.state_store.get_state(context_id)
    
    def close(self) -> None:
        """Close resources."""
        self.state_store.close()


class AgentSkillWrapper:
    """
    Wrapper for skill implementations that enables agent-style interaction.
    
    This wraps a skill's execute function to add:
    1. Input validation with INPUT_REQUIRED response
    2. State persistence between turns
    3. Proper AgentResponse generation
    """
    
    def __init__(
        self,
        skill_name: str,
        execute_fn: Any,  # Callable[[ExecutionContext], dict[str, Any]]
        input_schema: Dict[str, Any],
        state_store: StateStore | None = None,
    ):
        """
        Initialize wrapper.
        
        Args:
            skill_name: Name of the skill
            execute_fn: Original execute function
            input_schema: JSON schema for inputs
            state_store: StateStore for persistence
        """
        self.skill_name = skill_name
        self.execute_fn = execute_fn
        self.input_schema = input_schema
        self.state_store = state_store or create_state_store(shared=True)
    
    def __call__(
        self,
        ctx: Any,  # ExecutionContext
        resume_inputs: Dict[str, Any] | None = None,
    ) -> AgentResponse:
        """
        Execute skill with agent semantics.
        
        Args:
            ctx: ExecutionContext from executor
            resume_inputs: Additional inputs if resuming
        
        Returns:
            AgentResponse
        """
        start_time = time.time()
        context_id = ctx.correlation_id
        agent_id = AgentId(self.skill_name)
        
        # Merge inputs
        inputs = dict(ctx.inputs)
        if resume_inputs:
            inputs.update(resume_inputs)
        
        # Load turn number from state
        state = self.state_store.get_state(context_id)
        current_turn = (state.current_turn + 1) if state else 1
        
        # Check required inputs
        missing = self._get_missing_inputs(inputs)
        
        if missing:
            # Store partial state
            self.state_store.update_task_state(
                context_id, TaskState.INPUT_REQUIRED.value, current_turn
            )
            for key, value in inputs.items():
                self.state_store.put_fact(
                    context_id, PocketFact(bucket="inputs", key=key, value=value)
                )
            
            return AgentResponse(
                state=TaskState.INPUT_REQUIRED,
                input_request=InputRequest(
                    missing_fields=missing,
                    reason=f"Missing required inputs for {self.skill_name}",
                ),
                turn_number=current_turn,
                state_handle=context_id,
                duration_ms=int((time.time() - start_time) * 1000),
            )
        
        # Execute the underlying function
        try:
            outputs = self.execute_fn(ctx) or {}
            task_state = TaskState.COMPLETED
            errors = []
        except Exception as e:
            outputs = {}
            task_state = TaskState.FAILED
            errors = [str(e)]
        
        # Update state
        self.state_store.update_task_state(context_id, task_state.value, current_turn)
        self.state_store.append_event(
            context_id,
            ConversationEvent(
                event_type="skill_completed",
                payload={"state": task_state.value, "outputs_keys": list(outputs.keys())},
                turn_number=current_turn,
                agent_id=str(agent_id),
            ),
        )
        
        return AgentResponse(
            state=task_state,
            outputs=outputs,
            errors=errors,
            turn_number=current_turn,
            duration_ms=int((time.time() - start_time) * 1000),
        )
    
    def _get_missing_inputs(self, inputs: Dict[str, Any]) -> List[InputFieldSpec]:
        """Get list of missing required inputs."""
        missing = []
        required = self.input_schema.get("required", [])
        properties = self.input_schema.get("properties", {})
        
        for field_name in required:
            if field_name not in inputs or inputs[field_name] is None:
                field_schema = properties.get(field_name, {})
                missing.append(InputFieldSpec(
                    name=field_name,
                    type=field_schema.get("type", "string"),
                    description=field_schema.get("description", ""),
                    required=True,
                ))
        
        return missing


def create_agent_adapter(
    executor: Any,
    state_store: StateStore | None = None,
    max_turns: int = 8,
) -> AgentAdapter:
    """
    Factory function to create agent adapter.
    
    Args:
        executor: SkillExecutor instance
        state_store: Optional StateStore (default: SQLiteStateStore)
        max_turns: Max turns per context
    
    Returns:
        AgentAdapter instance
    """
    return AgentAdapter(
        executor=executor,
        state_store=state_store,
        max_turns=max_turns,
    )
