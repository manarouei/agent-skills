"""
Pipeline Runner - Execute pipelines through SkillExecutor.

Key behaviors:
- Resolves dependencies (topological sort)
- Enforces artifact preconditions
- Calls skills ONLY through SkillExecutor (no bypass)
- Records structured results for reporting
- Supports dry-run mode
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .models import (
    PipelineDefinition,
    PipelineResult,
    PipelineStep,
    StepResult,
    StepStatus,
)

if TYPE_CHECKING:
    from runtime.executor import SkillExecutor, ExecutionResult


# Canonical artifact directory structure
# Created at pipeline start to establish consistent layout
CANONICAL_ARTIFACT_DIRS = [
    "source",      # Ingested source materials
    "schema",      # Inferred/built schemas
    "scaffold",    # Generated scaffold files  
    "converted",   # Converted code (before copy to target)
    "tests",       # Generated tests
    "reports",     # Validation reports, pipeline summaries
    "logs",        # Execution logs
]


class PipelineExecutionError(Exception):
    """Raised when pipeline execution fails."""
    pass


class ArtifactPreconditionError(Exception):
    """Raised when artifact preconditions are not met."""
    pass


class PipelineRunner:
    """
    Execute pipelines through SkillExecutor.
    
    All skill calls go through SkillExecutor - no direct skill invocation.
    This ensures contract enforcement, gates, and bounded autonomy.
    """
    
    def __init__(
        self,
        executor: "SkillExecutor",
        artifacts_dir: Path,
        dry_run: bool = False,
        keep_going: bool = False,
    ):
        """
        Initialize runner.
        
        Args:
            executor: SkillExecutor instance for skill invocation
            artifacts_dir: Base directory for pipeline artifacts
            dry_run: If True, validate but don't execute
            keep_going: If True, continue on step failures
        """
        self.executor = executor
        self.artifacts_dir = artifacts_dir
        self.dry_run = dry_run
        self.keep_going = keep_going
        
        # Callbacks for progress reporting
        self._on_step_start: Optional[Callable[[str, str], None]] = None
        self._on_step_complete: Optional[Callable[[str, StepResult], None]] = None
    
    def on_step_start(self, callback: Callable[[str, str], None]) -> None:
        """Register callback for step start (step_name, skill_name)."""
        self._on_step_start = callback
    
    def on_step_complete(self, callback: Callable[[str, StepResult], None]) -> None:
        """Register callback for step completion (step_name, result)."""
        self._on_step_complete = callback
    
    def run(
        self,
        pipeline: PipelineDefinition,
        correlation_id: str,
        initial_inputs: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        Execute a pipeline.
        
        Args:
            pipeline: Pipeline definition to execute
            correlation_id: Correlation ID for this run
            initial_inputs: Initial inputs (merged with pipeline defaults)
            
        Returns:
            PipelineResult with all step results
        """
        started_at = datetime.utcnow()
        start_time = time.time()
        
        # Merge inputs (explicit overrides pipeline defaults)
        inputs = {**pipeline.initial_inputs, **(initial_inputs or {})}
        
        # Create artifacts directory with canonical structure
        run_artifacts = self.artifacts_dir / correlation_id
        run_artifacts.mkdir(parents=True, exist_ok=True)
        
        # Create canonical subdirectories
        for subdir in CANONICAL_ARTIFACT_DIRS:
            (run_artifacts / subdir).mkdir(exist_ok=True)
        
        # Track execution
        step_results: List[StepResult] = []
        step_outputs: Dict[str, Dict[str, Any]] = {}  # step_name -> outputs
        overall_status = StepStatus.COMPLETED
        errors: List[str] = []
        
        # Get execution order (topological sort)
        try:
            execution_order = pipeline.get_execution_order()
        except ValueError as e:
            return PipelineResult(
                pipeline_name=pipeline.name,
                correlation_id=correlation_id,
                status=StepStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration_ms=int((time.time() - start_time) * 1000),
                steps=[],
                outputs={},
                artifacts_dir=str(run_artifacts),
                errors=[f"Pipeline dependency error: {e}"],
            )
        
        # Build step lookup
        steps_by_name = {s.name: s for s in pipeline.steps}
        
        # Execute steps in order
        for step_name in execution_order:
            step = steps_by_name[step_name]
            
            # Check if we should skip due to earlier failure
            if overall_status == StepStatus.FAILED and not self.keep_going:
                step_result = StepResult(
                    step_name=step_name,
                    skill_name=step.skill,
                    status=StepStatus.SKIPPED,
                    started_at=datetime.utcnow(),
                    skipped_reason="Previous step failed",
                )
                step_results.append(step_result)
                continue
            
            # Execute step
            step_result = self._execute_step(
                step=step,
                correlation_id=correlation_id,
                inputs=inputs,
                step_outputs=step_outputs,
                artifacts_dir=run_artifacts,
            )
            step_results.append(step_result)
            
            # Store outputs for downstream steps
            step_outputs[step_name] = step_result.outputs
            
            # Update overall status
            if step_result.status == StepStatus.FAILED:
                if not step.continue_on_fail and not self.keep_going:
                    overall_status = StepStatus.FAILED
                    errors.append(f"Step '{step_name}' failed")
            elif step_result.status == StepStatus.BLOCKED:
                overall_status = StepStatus.BLOCKED
                errors.append(f"Step '{step_name}' blocked by gate")
            
            # Report progress
            if self._on_step_complete:
                self._on_step_complete(step_name, step_result)
        
        # Aggregate outputs from all steps
        aggregated_outputs = {}
        for step_name, outputs in step_outputs.items():
            aggregated_outputs[step_name] = outputs
        
        # Save pipeline result
        completed_at = datetime.utcnow()
        duration_ms = int((time.time() - start_time) * 1000)
        
        result = PipelineResult(
            pipeline_name=pipeline.name,
            correlation_id=correlation_id,
            status=overall_status,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            steps=step_results,
            outputs=aggregated_outputs,
            artifacts_dir=str(run_artifacts),
            errors=errors,
        )
        
        # Save result to artifacts
        result_path = run_artifacts / "pipeline_result.json"
        result_path.write_text(result.model_dump_json(indent=2))
        
        return result
    
    def _execute_step(
        self,
        step: PipelineStep,
        correlation_id: str,
        inputs: Dict[str, Any],
        step_outputs: Dict[str, Dict[str, Any]],
        artifacts_dir: Path,
    ) -> StepResult:
        """Execute a single pipeline step."""
        started_at = datetime.utcnow()
        start_time = time.time()
        
        # Notify start
        if self._on_step_start:
            self._on_step_start(step.name, step.skill)
        
        # Check condition
        if step.condition:
            should_run, skip_reason = self._evaluate_condition(
                step.condition, artifacts_dir, inputs
            )
            if not should_run:
                return StepResult(
                    step_name=step.name,
                    skill_name=step.skill,
                    status=StepStatus.SKIPPED,
                    started_at=started_at,
                    completed_at=datetime.utcnow(),
                    skipped_reason=skip_reason,
                )
        
        # Check artifact preconditions
        missing_artifacts = self._check_artifact_preconditions(
            step.requires_artifacts, artifacts_dir
        )
        if missing_artifacts:
            return StepResult(
                step_name=step.name,
                skill_name=step.skill,
                status=StepStatus.BLOCKED,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                errors=[f"Missing required artifacts: {missing_artifacts}"],
            )
        
        # Build step inputs
        step_inputs = self._build_step_inputs(step, inputs, step_outputs)
        
        # Add correlation_id to inputs
        step_inputs["correlation_id"] = correlation_id
        
        # Dry run - just validate
        if self.dry_run:
            return StepResult(
                step_name=step.name,
                skill_name=step.skill,
                status=StepStatus.COMPLETED,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                outputs={"dry_run": True},
                skipped_reason="Dry run mode",
            )
        
        # Execute through SkillExecutor (CRITICAL: no bypass)
        try:
            result: "ExecutionResult" = self.executor.execute(
                skill_name=step.skill,
                inputs=step_inputs,
                correlation_id=correlation_id,
            )
            
            # Map ExecutionStatus to StepStatus
            status = self._map_status(result.status)
            
            return StepResult(
                step_name=step.name,
                skill_name=step.skill,
                status=status,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration_ms=result.duration_ms,
                outputs=result.outputs,
                artifacts_produced=[str(a) for a in result.artifacts],
                errors=result.errors,
            )
            
        except Exception as e:
            return StepResult(
                step_name=step.name,
                skill_name=step.skill,
                status=StepStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                duration_ms=int((time.time() - start_time) * 1000),
                errors=[str(e)],
            )
    
    def _evaluate_condition(
        self,
        condition: Any,  # StepCondition
        artifacts_dir: Path,
        inputs: Dict[str, Any],
    ) -> tuple[bool, Optional[str]]:
        """
        Evaluate step condition.
        
        Returns (should_run, skip_reason).
        """
        # Check artifact_exists
        if condition.artifact_exists:
            artifact_path = artifacts_dir / condition.artifact_exists
            if not artifact_path.exists():
                return False, f"Artifact '{condition.artifact_exists}' does not exist"
        
        # Check artifact_missing
        if condition.artifact_missing:
            artifact_path = artifacts_dir / condition.artifact_missing
            if artifact_path.exists():
                return False, f"Artifact '{condition.artifact_missing}' already exists"
        
        # Check expression (simple equality check)
        if condition.expression:
            # Parse simple expressions like "source_type == TYPE1"
            if "==" in condition.expression:
                key, value = condition.expression.split("==")
                key = key.strip()
                value = value.strip().strip("'\"")
                if inputs.get(key) != value:
                    return False, f"Condition '{condition.expression}' not met"
        
        return True, None
    
    def _check_artifact_preconditions(
        self,
        required: List[str],
        artifacts_dir: Path,
    ) -> List[str]:
        """Check which required artifacts are missing."""
        missing = []
        for artifact in required:
            # Handle glob patterns
            if "*" in artifact:
                matches = list(artifacts_dir.glob(artifact))
                if not matches:
                    missing.append(artifact)
            else:
                path = artifacts_dir / artifact
                if not path.exists():
                    missing.append(artifact)
        return missing
    
    def _build_step_inputs(
        self,
        step: PipelineStep,
        pipeline_inputs: Dict[str, Any],
        step_outputs: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Build inputs for a step from pipeline inputs and mappings."""
        # Start with pipeline inputs
        inputs = dict(pipeline_inputs)
        
        # Add static step inputs
        inputs.update(step.inputs)
        
        # Apply input mappings (step_name.output_key -> input_key)
        for input_key, mapping in step.input_mappings.items():
            if "." in mapping:
                source_step, output_key = mapping.split(".", 1)
                if source_step in step_outputs:
                    source_outputs = step_outputs[source_step]
                    if output_key in source_outputs:
                        inputs[input_key] = source_outputs[output_key]
        
        return inputs
    
    def _map_status(self, exec_status: Any) -> StepStatus:
        """Map ExecutionStatus to StepStatus."""
        # Import here to avoid circular import
        from runtime.executor import ExecutionStatus
        
        mapping = {
            ExecutionStatus.SUCCESS: StepStatus.COMPLETED,
            ExecutionStatus.FAILED: StepStatus.FAILED,
            ExecutionStatus.BLOCKED: StepStatus.BLOCKED,
            ExecutionStatus.ESCALATED: StepStatus.FAILED,
            ExecutionStatus.TIMEOUT: StepStatus.FAILED,
        }
        return mapping.get(exec_status, StepStatus.FAILED)


def create_runner(
    skills_dir: Path,
    scripts_dir: Path,
    artifacts_dir: Path,
    dry_run: bool = False,
    keep_going: bool = False,
) -> PipelineRunner:
    """
    Factory function to create a PipelineRunner with configured SkillExecutor.
    
    Args:
        skills_dir: Path to skills/ directory
        scripts_dir: Path to scripts/ directory  
        artifacts_dir: Path to artifacts/ directory
        dry_run: If True, validate but don't execute
        keep_going: If True, continue on failures
        
    Returns:
        Configured PipelineRunner
    """
    # Import here to avoid circular import at module level
    from runtime.executor import SkillExecutor
    
    executor = SkillExecutor(
        skills_dir=skills_dir,
        scripts_dir=scripts_dir,
        artifacts_dir=artifacts_dir,
    )
    
    return PipelineRunner(
        executor=executor,
        artifacts_dir=artifacts_dir,
        dry_run=dry_run,
        keep_going=keep_going,
    )
