"""
Context Gate Skill

Validates that required context is available before code generation.
Asks up to 5 clarifying questions if context is missing.
"""

from typing import Any
from pydantic import BaseModel, Field

from agentic_system.runtime import Skill, SkillSpec, SideEffect, ExecutionContext


class ContextGateInput(BaseModel):
    """Input for context gate skill."""
    
    task_description: str = Field(..., description="What the user wants to accomplish")
    visible_files: list[str] = Field(
        default_factory=list,
        description="List of files currently visible/open"
    )
    available_context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context provided (e.g., schemas, configs)"
    )
    max_questions: int = Field(5, description="Maximum questions to ask")


class Question(BaseModel):
    """A clarifying question."""
    
    priority: str = Field(..., description="critical, high, medium, low")
    question: str = Field(..., description="The question text")
    reason: str = Field(..., description="Why this question is blocking")


class ContextGateOutput(BaseModel):
    """Output from context gate skill."""
    
    status: str = Field(
        ...,
        description="'ready' if context sufficient, 'needs_clarification' if questions, 'blocked' if cannot proceed"
    )
    questions: list[Question] = Field(
        default_factory=list,
        description="Clarifying questions (max 5)"
    )
    missing_context: list[str] = Field(
        default_factory=list,
        description="List of specific missing context items"
    )
    assumptions: list[str] = Field(
        default_factory=list,
        description="Explicit assumptions made to proceed"
    )
    required_files: list[str] = Field(
        default_factory=list,
        description="Files that need to be visible/provided"
    )
    can_proceed: bool = Field(..., description="Whether work can start with current context")


class ContextGateSkill(Skill):
    """
    Context Gate Skill for bounded autonomy.
    
    Context: Validates required context before code generation to prevent hallucinations.
    Contract: Input is task + visible context, output is readiness status + questions.
    Invariants: Max 5 questions; BLOCKED status if context cannot be obtained.
    Side Effects: Read-only analysis of available context.
    
    Example:
        >>> result = skill.execute({
        ...     "task_description": "Add caching to summarize skill",
        ...     "visible_files": ["src/skills/summarize.py"]
        ... }, context)
        >>> assert result["status"] in ["ready", "needs_clarification", "blocked"]
    """
    
    def spec(self) -> SkillSpec:
        """Return skill specification."""
        return SkillSpec(
            name="context_gate",
            version="1.0.0",
            side_effect=SideEffect.NONE,
            timeout_s=30,
            idempotent=True,
        )
    
    def input_model(self) -> type[BaseModel]:
        """Return input model for validation."""
        return ContextGateInput
    
    def output_model(self) -> type[BaseModel]:
        """Return output model for validation."""
        return ContextGateOutput
    
    def _execute(self, input_data: ContextGateInput, context: ExecutionContext) -> ContextGateOutput:
        """Execute context validation."""
        questions: list[Question] = []
        missing_context: list[str] = []
        assumptions: list[str] = []
        required_files: list[str] = []
        
        # Analyze task description for required context
        task = input_data.task_description.lower()
        
        # Check for file allowlist
        if "modify" in task or "change" in task or "update" in task or "add" in task:
            if not input_data.available_context.get("file_allowlist"):
                questions.append(Question(
                    priority="critical",
                    question="Which files am I allowed to modify for this task?",
                    reason="P0-2 Scope Control: Need explicit file allowlist"
                ))
                missing_context.append("file_allowlist")
        
        # Check for API/function existence
        api_patterns = ["call", "use", "invoke", "execute"]
        if any(pattern in task for pattern in api_patterns):
            if not input_data.available_context.get("api_signatures"):
                questions.append(Question(
                    priority="high",
                    question="What are the exact signatures of the APIs/functions I need to use?",
                    reason="P0-3 No Hallucination: Need to verify APIs exist"
                ))
                missing_context.append("api_signatures")
        
        # Check for schema/contract information
        if any(word in task for word in ["model", "schema", "field", "contract", "api"]):
            if not input_data.available_context.get("schemas"):
                questions.append(Question(
                    priority="high",
                    question="What are the current schemas/contracts I need to preserve?",
                    reason="P1-6 Preserve Contracts: Need to know existing contracts"
                ))
                missing_context.append("schemas")
        
        # Check for specific implementation details
        if "cache" in task:
            if not input_data.available_context.get("cache_implementation"):
                questions.append(Question(
                    priority="high",
                    question="Where should the cache be stored (Redis, in-memory, filesystem)? What is the TTL?",
                    reason="Implementation details needed"
                ))
                missing_context.append("cache_implementation")
        
        # Check for database changes
        if any(word in task for word in ["database", "migration", "schema", "table", "sql"]):
            if not input_data.available_context.get("database_schema"):
                questions.append(Question(
                    priority="critical",
                    question="What is the current database schema? Are there existing migrations?",
                    reason="Database changes require schema knowledge"
                ))
                missing_context.append("database_schema")
        
        # Check for security context
        if any(word in task for word in ["security", "auth", "permission", "access"]):
            if not input_data.available_context.get("security_model"):
                questions.append(Question(
                    priority="critical",
                    question="What is the current security model (authentication, authorization)?",
                    reason="Security changes require understanding current posture"
                ))
                missing_context.append("security_model")
        
        # Identify required files
        if "skill" in task:
            required_files.append("src/agentic_system/skills/*.py")
        if "agent" in task:
            required_files.append("src/agentic_system/agents/*.py")
        if "api" in task or "endpoint" in task:
            required_files.append("src/agentic_system/api/routes/*.py")
        
        # Check if we have enough visible files (before truncating to max_questions)
        if required_files and not input_data.visible_files and len(questions) < input_data.max_questions:
            questions.append(Question(
                priority="high",
                question=f"Can you open these files for context: {', '.join(required_files)}?",
                reason="Need to see relevant code files"
            ))
        
        # Limit to max_questions
        questions = questions[:input_data.max_questions]
        
        # Make explicit assumptions
        if not questions or len(questions) < input_data.max_questions:
            if input_data.visible_files:
                assumptions.append(f"Working with files: {', '.join(input_data.visible_files)}")
            if not input_data.available_context.get("breaking_changes_allowed"):
                assumptions.append("No breaking changes allowed (P1-6)")
            assumptions.append("Tests will be added/updated (P0-5)")
            assumptions.append("All LLM calls will go through LLMGatewaySkill (P1-8)")
        
        # Determine status
        if not questions:
            status = "ready"
            can_proceed = True
        elif len(questions) <= input_data.max_questions:
            status = "needs_clarification"
            can_proceed = False
        else:
            status = "blocked"
            can_proceed = False
        
        # If we've asked max questions and still missing critical context
        critical_questions = [q for q in questions if q.priority == "critical"]
        if len(questions) >= input_data.max_questions and critical_questions:
            status = "blocked"
            can_proceed = False
        
        return ContextGateOutput(
            status=status,
            questions=questions,
            missing_context=missing_context,
            assumptions=assumptions,
            required_files=required_files,
            can_proceed=can_proceed
        )
