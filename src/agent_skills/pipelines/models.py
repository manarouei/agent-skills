"""
Pipeline Models - Pydantic models for pipeline DAG execution.

Defines:
- PipelineStep: Single step in a pipeline
- PipelineDefinition: Full pipeline DAG
- PipelineResult: Execution result with structured outputs
- StepResult: Per-step execution result

All models use strict Pydantic validation.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StepStatus(str, Enum):
    """Status of a pipeline step."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class StepCondition(BaseModel):
    """
    Conditional execution for a pipeline step.
    
    Supports:
    - artifact_exists: Run only if artifact exists
    - artifact_missing: Run only if artifact doesn't exist
    - previous_status: Run based on previous step status
    - expression: Simple expression evaluation (e.g., "source_type == 'TYPE1'")
    """
    model_config = ConfigDict(extra="forbid")
    
    artifact_exists: Optional[str] = Field(
        None, 
        description="Run step only if this artifact exists"
    )
    artifact_missing: Optional[str] = Field(
        None,
        description="Run step only if this artifact is missing"
    )
    previous_status: Optional[str] = Field(
        None,
        description="Run step only if previous step has this status"
    )
    expression: Optional[str] = Field(
        None,
        description="Simple expression to evaluate (e.g., 'source_type == TYPE1')"
    )


class PipelineStep(BaseModel):
    """
    A single step in a pipeline DAG.
    
    Steps are executed in dependency order (topological sort).
    Each step calls a skill through SkillExecutor.
    """
    model_config = ConfigDict(extra="forbid")
    
    name: str = Field(
        ...,
        description="Unique step name within pipeline",
        min_length=1,
        max_length=64,
    )
    skill: str = Field(
        ...,
        description="Skill name to execute (must be registered)",
        min_length=1,
    )
    depends_on: List[str] = Field(
        default_factory=list,
        description="List of step names this step depends on",
    )
    requires_artifacts: List[str] = Field(
        default_factory=list,
        description="Artifacts that must exist before step runs",
    )
    produces_artifacts: List[str] = Field(
        default_factory=list,
        description="Artifacts this step produces",
    )
    inputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Static inputs to pass to skill",
    )
    input_mappings: Dict[str, str] = Field(
        default_factory=dict,
        description="Map step outputs to inputs: {input_key: 'step_name.output_key'}",
    )
    condition: Optional[StepCondition] = Field(
        None,
        description="Conditional execution",
    )
    timeout_seconds: Optional[int] = Field(
        None,
        description="Override skill timeout (must be <= contract timeout)",
        ge=1,
        le=3600,
    )
    continue_on_fail: bool = Field(
        False,
        description="Continue pipeline if this step fails",
    )
    
    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Step name must be valid identifier."""
        if not v.replace("-", "_").replace("_", "").isalnum():
            raise ValueError(f"Invalid step name: {v}")
        return v
    
    @field_validator("depends_on")
    @classmethod
    def validate_no_self_dependency(cls, v: List[str], info) -> List[str]:
        """Step cannot depend on itself."""
        name = info.data.get("name")
        if name and name in v:
            raise ValueError(f"Step '{name}' cannot depend on itself")
        return v


class PipelineDefinition(BaseModel):
    """
    Complete pipeline definition.
    
    Pipelines are DAGs of steps that execute skills in order.
    """
    model_config = ConfigDict(extra="forbid")
    
    name: str = Field(
        ...,
        description="Pipeline name",
        min_length=1,
        max_length=64,
    )
    version: str = Field(
        "1.0.0",
        description="Pipeline version (semver)",
    )
    description: Optional[str] = Field(
        None,
        description="Human-readable description",
    )
    steps: List[PipelineStep] = Field(
        ...,
        description="Ordered list of pipeline steps",
        min_length=1,
    )
    initial_inputs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Default inputs for pipeline",
    )
    
    @field_validator("steps")
    @classmethod
    def validate_unique_names(cls, v: List[PipelineStep]) -> List[PipelineStep]:
        """All step names must be unique."""
        names = [s.name for s in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate step names: {set(duplicates)}")
        return v
    
    @field_validator("steps")
    @classmethod
    def validate_dependencies_exist(cls, v: List[PipelineStep]) -> List[PipelineStep]:
        """All dependencies must reference existing steps."""
        names = {s.name for s in v}
        for step in v:
            for dep in step.depends_on:
                if dep not in names:
                    raise ValueError(
                        f"Step '{step.name}' depends on unknown step '{dep}'"
                    )
        return v
    
    def get_execution_order(self) -> List[str]:
        """
        Return steps in topological order (dependencies first).
        
        Raises ValueError if cycle detected.
        """
        # Build adjacency list: node -> list of nodes that depend on it
        # graph[A] = [B, C] means B and C depend on A (A must run before B, C)
        dependents: Dict[str, List[str]] = {s.name: [] for s in self.steps}
        in_degree: Dict[str, int] = {s.name: len(s.depends_on) for s in self.steps}
        
        for step in self.steps:
            for dep in step.depends_on:
                if dep in dependents:
                    dependents[dep].append(step.name)
        
        # Kahn's algorithm for topological sort
        # Start with nodes that have no dependencies (in_degree = 0)
        queue = [name for name, degree in in_degree.items() if degree == 0]
        result = []
        
        while queue:
            # Sort for deterministic order
            queue.sort()
            node = queue.pop(0)
            result.append(node)
            
            # For each node that depends on this one, decrement its in_degree
            for dependent in dependents[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        
        if len(result) != len(dependents):
            # Cycle detected
            remaining = set(dependents.keys()) - set(result)
            raise ValueError(f"Cycle detected in pipeline: {remaining}")
        
        return result


class StepResult(BaseModel):
    """Result of a single pipeline step execution."""
    model_config = ConfigDict(extra="forbid")
    
    step_name: str = Field(..., description="Name of the step")
    skill_name: str = Field(..., description="Skill that was executed")
    status: StepStatus = Field(..., description="Execution status")
    started_at: datetime = Field(..., description="When step started")
    completed_at: Optional[datetime] = Field(None, description="When step completed")
    duration_ms: int = Field(0, description="Execution duration in milliseconds")
    outputs: Dict[str, Any] = Field(default_factory=dict, description="Step outputs")
    artifacts_produced: List[str] = Field(
        default_factory=list, 
        description="Artifacts created by this step"
    )
    errors: List[str] = Field(default_factory=list, description="Error messages")
    skipped_reason: Optional[str] = Field(None, description="Why step was skipped")


class PipelineResult(BaseModel):
    """Complete result of pipeline execution."""
    model_config = ConfigDict(extra="forbid")
    
    pipeline_name: str = Field(..., description="Name of the pipeline")
    correlation_id: str = Field(..., description="Correlation ID for this run")
    status: StepStatus = Field(..., description="Overall pipeline status")
    started_at: datetime = Field(..., description="When pipeline started")
    completed_at: Optional[datetime] = Field(None, description="When pipeline completed")
    duration_ms: int = Field(0, description="Total execution duration")
    steps: List[StepResult] = Field(default_factory=list, description="Per-step results")
    outputs: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Aggregated outputs from all steps"
    )
    artifacts_dir: Optional[str] = Field(None, description="Path to artifacts directory")
    errors: List[str] = Field(default_factory=list, description="Pipeline-level errors")
    
    def get_step_result(self, step_name: str) -> Optional[StepResult]:
        """Get result for a specific step."""
        for step in self.steps:
            if step.step_name == step_name:
                return step
        return None
    
    def is_success(self) -> bool:
        """Check if pipeline completed successfully."""
        return self.status == StepStatus.COMPLETED
    
    def failed_steps(self) -> List[StepResult]:
        """Get all failed steps."""
        return [s for s in self.steps if s.status == StepStatus.FAILED]
