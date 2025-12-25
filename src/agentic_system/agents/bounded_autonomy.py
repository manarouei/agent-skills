"""
Bounded Autonomy Agent

Orchestrates bounded autonomy enforcement: context gating, code review, compliance checking.
"""

from typing import Any
from pydantic import BaseModel, Field

from agentic_system.runtime import Agent, AgentSpec, ExecutionContext, get_skill_registry


class BoundedAutonomyInput(BaseModel):
    """Input for bounded autonomy agent."""
    
    mode: str = Field(
        ...,
        description="Mode: 'plan', 'review', 'validate'"
    )
    task_description: str | None = Field(
        None,
        description="Task description (for plan mode)"
    )
    visible_files: list[str] = Field(
        default_factory=list,
        description="Files currently visible"
    )
    modified_files: list[str] = Field(
        default_factory=list,
        description="Files modified (for review mode)"
    )
    file_diffs: dict[str, str] = Field(
        default_factory=dict,
        description="File diffs (for review mode)"
    )
    planned_files: list[str] | None = Field(
        None,
        description="Files that were planned to be modified"
    )
    pr_description: str | None = Field(
        None,
        description="PR description text"
    )
    available_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context available"
    )


class BoundedAutonomyOutput(BaseModel):
    """Output from bounded autonomy agent."""
    
    status: str = Field(..., description="Overall status")
    mode: str = Field(..., description="Mode that was executed")
    result: dict[str, Any] = Field(..., description="Mode-specific result")
    summary: str = Field(..., description="Human-readable summary")
    next_steps: list[str] = Field(default_factory=list, description="Recommended next steps")


class BoundedAutonomyAgent(Agent):
    """
    Bounded Autonomy Agent.
    
    Context: Enforces P0/P1/P2 rules through context gating and code review.
    Contract: Input specifies mode (plan/review/validate), output is status + recommendations.
    Workflow:
        - plan mode: Use context_gate skill to validate requirements
        - review mode: Use code_review skill to check compliance
        - validate mode: Both context gating and code review
    
    Example:
        >>> result = agent.run({
        ...     "mode": "plan",
        ...     "task_description": "Add caching to summarize skill"
        ... }, context)
        >>> assert result["status"] in ["ready", "needs_clarification", "blocked", "violations"]
    """
    
    def spec(self) -> AgentSpec:
        """Return agent specification."""
        return AgentSpec(
            agent_id="bounded_autonomy",
            version="1.0.0",
            step_limit=10,
            description="Bounded autonomy enforcement agent",
        )
    
    def input_model(self) -> type[BaseModel]:
        """Return input model for validation."""
        return BoundedAutonomyInput
    
    def output_model(self) -> type[BaseModel]:
        """Return output model for validation."""
        return BoundedAutonomyOutput
    
    def _run(self, input_data: BoundedAutonomyInput, context: ExecutionContext) -> dict[str, Any]:
        """Run bounded autonomy checks based on mode."""
        skill_registry = get_skill_registry()
        
        if input_data.mode == "plan":
            return self._plan_mode(input_data, skill_registry, context)
        elif input_data.mode == "review":
            return self._review_mode(input_data, skill_registry, context)
        elif input_data.mode == "validate":
            return self._validate_mode(input_data, skill_registry, context)
        else:
            raise ValueError(f"Unknown mode: {input_data.mode}")
    
    def _plan_mode(
        self,
        input_data: BoundedAutonomyInput,
        skill_registry: Any,
        context: ExecutionContext
    ) -> dict[str, Any]:
        """Execute planning mode with context gating."""
        self._check_step_limit()
        
        # Call context_gate skill
        gate_result = skill_registry.execute(
            name="context_gate",
            input_data={
                "task_description": input_data.task_description or "",
                "visible_files": input_data.visible_files,
                "available_context": input_data.available_context,
                "max_questions": 5
            },
            context=context
        )
        
        self._check_step_limit()
        
        status = gate_result["status"]
        summary_parts = [f"Context gate status: {status}"]
        next_steps = []
        
        if status == "ready":
            summary = "✅ All required context available. Ready to proceed with implementation."
            next_steps.append("Proceed with A1 (implementation) phase")
            next_steps.append(f"Use file allowlist: {', '.join(gate_result.get('required_files', []))}")
        elif status == "needs_clarification":
            questions = gate_result.get("questions", [])
            summary = f"❓ Need clarification: {len(questions)} questions"
            next_steps.append("Answer these questions:")
            for q in questions:
                next_steps.append(f"  [{q['priority']}] {q['question']}")
            next_steps.append("Then re-run plan mode")
        else:  # blocked
            summary = "🚫 BLOCKED: Cannot proceed without critical context"
            missing = gate_result.get("missing_context", [])
            next_steps.append(f"Missing critical context: {', '.join(missing)}")
            next_steps.append("Provide context or simplify task scope")
        
        output = BoundedAutonomyOutput(
            status=status,
            mode="plan",
            result=gate_result,
            summary=summary,
            next_steps=next_steps
        )
        
        return output.model_dump()
    
    def _review_mode(
        self,
        input_data: BoundedAutonomyInput,
        skill_registry: Any,
        context: ExecutionContext
    ) -> dict[str, Any]:
        """Execute review mode with code review."""
        self._check_step_limit()
        
        # Call code_review skill
        review_result = skill_registry.execute(
            name="code_review",
            input_data={
                "modified_files": input_data.modified_files,
                "file_diffs": input_data.file_diffs,
                "planned_files": input_data.planned_files,
                "pr_description": input_data.pr_description,
                "check_imports": True
            },
            context=context
        )
        
        self._check_step_limit()
        
        compliance_status = review_result["compliance_status"]
        p0_violations = review_result.get("p0_violations", [])
        p1_violations = review_result.get("p1_violations", [])
        
        if compliance_status == "violations":
            status = "violations"
            summary = f"❌ {len(p0_violations)} P0 violations (BLOCKING)"
        elif compliance_status == "warnings":
            status = "warnings"
            summary = f"⚠️  {len(p1_violations)} P1 warnings"
        else:
            status = "compliant"
            summary = "✅ All checks passed"
        
        next_steps = []
        
        # Add P0 violations to next steps
        if p0_violations:
            next_steps.append("FIX P0 VIOLATIONS (blocking):")
            for v in p0_violations:
                next_steps.append(f"  - [{v['rule_id']}] {v['message']}")
        
        # Add P1 violations as warnings
        if p1_violations:
            next_steps.append("ADDRESS P1 WARNINGS (recommended):")
            for v in p1_violations[:5]:  # Limit to 5
                next_steps.append(f"  - [{v['rule_id']}] {v['message']}")
        
        # Add recommendations
        recommendations = review_result.get("recommendations", [])
        if recommendations:
            next_steps.append("Recommendations:")
            for rec in recommendations[:5]:
                next_steps.append(f"  - {rec}")
        
        if compliance_status == "compliant":
            next_steps.append("Ready to merge (all checks passed)")
        
        output = BoundedAutonomyOutput(
            status=status,
            mode="review",
            result=review_result,
            summary=summary,
            next_steps=next_steps
        )
        
        return output.model_dump()
    
    def _validate_mode(
        self,
        input_data: BoundedAutonomyInput,
        skill_registry: Any,
        context: ExecutionContext
    ) -> dict[str, Any]:
        """Execute both plan and review modes."""
        # Run plan mode first
        plan_result = self._plan_mode(input_data, skill_registry, context)
        
        # If we have modified files, also run review
        if input_data.modified_files:
            review_result = self._review_mode(input_data, skill_registry, context)
            
            # Combine results
            combined_status = "violations" if review_result["status"] == "violations" else plan_result["status"]
            combined_summary = f"{plan_result['summary']}\n{review_result['summary']}"
            combined_next_steps = plan_result["next_steps"] + review_result["next_steps"]
            
            output = BoundedAutonomyOutput(
                status=combined_status,
                mode="validate",
                result={
                    "plan": plan_result["result"],
                    "review": review_result["result"]
                },
                summary=combined_summary,
                next_steps=combined_next_steps
            )
        else:
            # Only plan mode
            output = BoundedAutonomyOutput(
                status=plan_result["status"],
                mode="validate",
                result={"plan": plan_result["result"]},
                summary=plan_result["summary"],
                next_steps=plan_result["next_steps"]
            )
        
        return output.model_dump()
