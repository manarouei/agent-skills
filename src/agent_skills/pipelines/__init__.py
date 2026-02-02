"""
Pipelines Package - Pipeline DAG execution through SkillExecutor.

This package provides:
- PipelineDefinition, PipelineStep, PipelineResult models
- YAML pipeline loader
- PipelineRunner that executes through SkillExecutor (no bypass)

Key guarantee: All skill calls go through SkillExecutor for contract enforcement.
"""

from .models import (
    PipelineDefinition,
    PipelineResult,
    PipelineStep,
    StepCondition,
    StepResult,
    StepStatus,
)
from .loader import (
    load_pipeline_from_file,
    load_pipeline_from_dict,
    load_pipelines_from_dir,
    get_type1_pipeline,
    get_type2_pipeline,
    get_convert_node_v1_pipeline,
    get_builtin_pipelines,
    PipelineLoadError,
)
from .runner import (
    PipelineRunner,
    PipelineExecutionError,
    ArtifactPreconditionError,
    create_runner,
    CANONICAL_ARTIFACT_DIRS,
)

__all__ = [
    # Models
    "PipelineDefinition",
    "PipelineResult", 
    "PipelineStep",
    "StepCondition",
    "StepResult",
    "StepStatus",
    # Loader
    "load_pipeline_from_file",
    "load_pipeline_from_dict",
    "load_pipelines_from_dir",
    "get_type1_pipeline",
    "get_type2_pipeline",
    "get_convert_node_v1_pipeline",
    "get_builtin_pipelines",
    "PipelineLoadError",
    # Runner
    "PipelineRunner",
    "PipelineExecutionError",
    "ArtifactPreconditionError",
    "create_runner",
    # Constants
    "CANONICAL_ARTIFACT_DIRS",
]
