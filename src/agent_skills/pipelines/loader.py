"""
Pipeline Loader - Load pipeline definitions from YAML files.

Supports:
- Single pipeline file (pipeline.yaml)
- Pipeline directory (pipelines/*.yaml)
- Inline dict definitions
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from .models import PipelineDefinition, PipelineStep, StepCondition


class PipelineLoadError(Exception):
    """Raised when pipeline loading fails."""
    pass


def load_pipeline_from_file(path: Path) -> PipelineDefinition:
    """
    Load a single pipeline from a YAML file.
    
    Args:
        path: Path to YAML file
        
    Returns:
        PipelineDefinition
        
    Raises:
        PipelineLoadError: If file not found or invalid
    """
    if not path.exists():
        raise PipelineLoadError(f"Pipeline file not found: {path}")
    
    try:
        content = path.read_text()
        data = yaml.safe_load(content)
        return _parse_pipeline(data, source=str(path))
    except yaml.YAMLError as e:
        raise PipelineLoadError(f"Invalid YAML in {path}: {e}")
    except Exception as e:
        raise PipelineLoadError(f"Failed to load pipeline from {path}: {e}")


def load_pipeline_from_dict(data: Dict[str, Any]) -> PipelineDefinition:
    """
    Load a pipeline from a dictionary.
    
    Args:
        data: Pipeline definition dict
        
    Returns:
        PipelineDefinition
    """
    return _parse_pipeline(data, source="dict")


def load_pipelines_from_dir(pipelines_dir: Path) -> Dict[str, PipelineDefinition]:
    """
    Load all pipelines from a directory.
    
    Args:
        pipelines_dir: Directory containing *.yaml files
        
    Returns:
        Dict mapping pipeline name to definition
    """
    if not pipelines_dir.exists():
        return {}
    
    pipelines = {}
    for yaml_file in pipelines_dir.glob("*.yaml"):
        try:
            pipeline = load_pipeline_from_file(yaml_file)
            pipelines[pipeline.name] = pipeline
        except PipelineLoadError:
            # Skip invalid files
            continue
    
    return pipelines


def _parse_pipeline(data: Dict[str, Any], source: str = "unknown") -> PipelineDefinition:
    """
    Parse pipeline data into PipelineDefinition.
    
    Validates structure and converts to Pydantic model.
    """
    if not isinstance(data, dict):
        raise PipelineLoadError(f"Pipeline must be a dict, got {type(data).__name__}")
    
    # Required fields
    if "name" not in data:
        raise PipelineLoadError(f"Pipeline missing 'name' field (source: {source})")
    if "steps" not in data:
        raise PipelineLoadError(f"Pipeline missing 'steps' field (source: {source})")
    
    # Parse steps
    steps = []
    for i, step_data in enumerate(data["steps"]):
        try:
            step = _parse_step(step_data, index=i)
            steps.append(step)
        except Exception as e:
            raise PipelineLoadError(
                f"Invalid step {i} in pipeline '{data['name']}': {e}"
            )
    
    # Build definition
    try:
        return PipelineDefinition(
            name=data["name"],
            version=data.get("version", "1.0.0"),
            description=data.get("description"),
            steps=steps,
            initial_inputs=data.get("initial_inputs", {}),
        )
    except Exception as e:
        raise PipelineLoadError(f"Invalid pipeline '{data['name']}': {e}")


def _parse_step(data: Dict[str, Any], index: int) -> PipelineStep:
    """Parse a single step definition."""
    if not isinstance(data, dict):
        raise ValueError(f"Step must be a dict, got {type(data).__name__}")
    
    # Required fields
    if "name" not in data:
        raise ValueError("Step missing 'name' field")
    if "skill" not in data:
        raise ValueError("Step missing 'skill' field")
    
    # Parse condition if present
    condition = None
    if "condition" in data:
        condition = StepCondition(**data["condition"])
    
    return PipelineStep(
        name=data["name"],
        skill=data["skill"],
        depends_on=data.get("depends_on", []),
        requires_artifacts=data.get("requires_artifacts", []),
        produces_artifacts=data.get("produces_artifacts", []),
        inputs=data.get("inputs", {}),
        input_mappings=data.get("input_mappings", {}),
        condition=condition,
        timeout_seconds=data.get("timeout_seconds"),
        continue_on_fail=data.get("continue_on_fail", False),
    )


# =============================================================================
# BUILT-IN PIPELINE DEFINITIONS
# =============================================================================

def get_type1_pipeline() -> PipelineDefinition:
    """
    Get the TYPE1 (TypeScript conversion) pipeline definition.
    
    Pipeline: source-ingest → schema-infer → schema-build → node-scaffold → 
              code-convert → test-generate → code-validate
    """
    return PipelineDefinition(
        name="type1-convert",
        version="1.0.0",
        description="Convert TypeScript n8n node to Python",
        steps=[
            PipelineStep(
                name="ingest",
                skill="source-ingest",
                produces_artifacts=["source_bundle/"],
            ),
            PipelineStep(
                name="infer-schema",
                skill="schema-infer",
                depends_on=["ingest"],
                requires_artifacts=["source_bundle/"],
                produces_artifacts=["inferred_schema.json", "trace_map.json"],
            ),
            PipelineStep(
                name="build-schema",
                skill="schema-build",
                depends_on=["infer-schema"],
                requires_artifacts=["inferred_schema.json"],
                produces_artifacts=["node_schema.json"],
            ),
            PipelineStep(
                name="scaffold",
                skill="node-scaffold",
                depends_on=["build-schema"],
                requires_artifacts=["node_schema.json"],
                produces_artifacts=["converted_node/"],
            ),
            PipelineStep(
                name="convert",
                skill="code-convert",
                depends_on=["scaffold"],
                requires_artifacts=["source_bundle/", "node_schema.json"],
                produces_artifacts=["converted_node/*.py"],
            ),
            PipelineStep(
                name="generate-tests",
                skill="test-generate",
                depends_on=["convert"],
                requires_artifacts=["converted_node/"],
                produces_artifacts=["tests/"],
                continue_on_fail=True,
            ),
            PipelineStep(
                name="validate",
                skill="code-validate",
                depends_on=["generate-tests"],
                requires_artifacts=["converted_node/"],
                produces_artifacts=["validation_logs.txt"],
                continue_on_fail=True,
            ),
        ],
        initial_inputs={
            "source_type": "TYPE1",
        },
    )


def get_type2_pipeline() -> PipelineDefinition:
    """
    Get the TYPE2 (documentation implementation) pipeline definition.
    
    Pipeline: source-ingest → schema-infer → schema-build → node-scaffold →
              code-implement → test-generate → code-validate
    """
    return PipelineDefinition(
        name="type2-implement",
        version="1.0.0",
        description="Implement node from API documentation",
        steps=[
            PipelineStep(
                name="ingest",
                skill="source-ingest",
                produces_artifacts=["source_bundle/"],
            ),
            PipelineStep(
                name="infer-schema",
                skill="schema-infer",
                depends_on=["ingest"],
                requires_artifacts=["source_bundle/"],
                produces_artifacts=["inferred_schema.json", "trace_map.json"],
            ),
            PipelineStep(
                name="build-schema",
                skill="schema-build",
                depends_on=["infer-schema"],
                requires_artifacts=["inferred_schema.json"],
                produces_artifacts=["node_schema.json"],
            ),
            PipelineStep(
                name="scaffold",
                skill="node-scaffold",
                depends_on=["build-schema"],
                requires_artifacts=["node_schema.json"],
                produces_artifacts=["converted_node/"],
            ),
            PipelineStep(
                name="implement",
                skill="code-implement",
                depends_on=["scaffold"],
                requires_artifacts=["source_bundle/", "node_schema.json"],
                produces_artifacts=["converted_node/*.py"],
            ),
            PipelineStep(
                name="generate-tests",
                skill="test-generate",
                depends_on=["implement"],
                requires_artifacts=["converted_node/"],
                produces_artifacts=["tests/"],
                continue_on_fail=True,
            ),
            PipelineStep(
                name="validate",
                skill="code-validate",
                depends_on=["generate-tests"],
                requires_artifacts=["converted_node/"],
                produces_artifacts=["validation_logs.txt"],
                continue_on_fail=True,
            ),
        ],
        initial_inputs={
            "source_type": "TYPE2",
        },
    )


def get_convert_node_v1_pipeline() -> PipelineDefinition:
    """
    Get the convert_node_v1 pipeline definition.
    
    This is the canonical minimal pipeline for TYPE1 node conversion:
    - Includes repo-ground for target repo facts
    - Uses existing skills only (no invented steps)
    
    Pipeline: node-normalize → repo-ground → source-classify → source-ingest → 
              schema-infer → node-scaffold → code-convert →
              node-package → node-validate → [apply-changes] → [node-smoke-test]
              
    Steps 8-11 (apply pipeline) are gated:
    - node-package and node-validate always run (dry-run safe)
    - apply-changes only runs if apply=true in initial_inputs
    - node-smoke-test only runs if run_tests=true in initial_inputs
    """
    return PipelineDefinition(
        name="convert_node_v1",
        version="1.1.0",
        description="Convert TypeScript n8n node to Python (v1 minimal pipeline)",
        steps=[
            # Step 1: Normalize node name and generate correlation ID context
            PipelineStep(
                name="normalize",
                skill="node-normalize",
                produces_artifacts=[],  # Pure function, no artifacts
                inputs={},
            ),
            # Step 2: Ground in target repository (get repo_facts)
            PipelineStep(
                name="ground",
                skill="repo-ground",
                depends_on=["normalize"],
                produces_artifacts=["repo_facts.json", "target_repo_layout.json"],
                inputs={},
                # repo_root is passed via initial_inputs or input_mappings
            ),
            # Step 3: Classify source type (TYPE1 vs TYPE2)
            PipelineStep(
                name="classify",
                skill="source-classify",
                depends_on=["normalize"],
                produces_artifacts=[],
                input_mappings={
                    "normalized_name": "normalize.normalized_name",
                },
            ),
            # Step 4: Ingest source materials
            PipelineStep(
                name="ingest",
                skill="source-ingest",
                depends_on=["classify"],
                produces_artifacts=["source/"],
                input_mappings={
                    "source_type": "classify.source_type",
                    "evidence": "classify.evidence",
                },
            ),
            # Step 5: Infer schema from source
            PipelineStep(
                name="infer-schema",
                skill="schema-infer",
                depends_on=["ingest", "ground"],
                requires_artifacts=["source/", "repo_facts.json"],
                produces_artifacts=["schema/inferred_schema.json", "schema/trace_map.json"],
                input_mappings={
                    "source_type": "classify.source_type",
                    "parsed_sections": "ingest.parsed_sections",
                },
            ),
            # Step 6: Scaffold node structure
            PipelineStep(
                name="scaffold",
                skill="node-scaffold",
                depends_on=["infer-schema"],
                requires_artifacts=["schema/inferred_schema.json"],
                produces_artifacts=["scaffold/", "allowlist.json"],
                input_mappings={
                    "node_schema": "infer-schema.inferred_schema",  # Match actual output key
                    "normalized_name": "normalize.normalized_name",
                },
            ),
            # Step 7: Convert TypeScript to Python
            PipelineStep(
                name="convert",
                skill="code-convert",
                depends_on=["scaffold", "ingest", "normalize"],
                requires_artifacts=["scaffold/", "allowlist.json", "repo_facts.json"],
                produces_artifacts=["converted/"],
                input_mappings={
                    "source_type": "classify.source_type",
                    "parsed_sections": "ingest.parsed_sections",
                    "node_schema": "infer-schema.inferred_schema",  # Match actual output key
                    "allowlist": "scaffold.allowlist",
                    "normalized_name": "normalize.normalized_name",  # For proper file naming
                },
            ),
            # =========================================================
            # Apply pipeline (steps 8-11) - package and deploy to target
            # =========================================================
            # Step 8: Package converted artifacts for deployment
            PipelineStep(
                name="package",
                skill="node-package",
                depends_on=["convert", "ground"],
                requires_artifacts=["converted/", "target_repo_layout.json"],
                produces_artifacts=["package/", "package/manifest.json"],
                input_mappings={
                    "target_repo_layout": "ground.target_repo_layout",
                    "normalized_name": "normalize.normalized_name",
                },
            ),
            # Step 9: Validate package before apply
            PipelineStep(
                name="pre-validate",
                skill="node-validate",
                depends_on=["package"],
                requires_artifacts=["package/"],
                produces_artifacts=["validation_result.json"],
                input_mappings={
                    "package_dir": "package.package_dir",
                },
            ),
            # Step 10: Apply changes to target repository (GATED)
            # Only runs if apply=true in initial_inputs
            PipelineStep(
                name="apply",
                skill="apply-changes",
                depends_on=["pre-validate", "ground"],
                requires_artifacts=["package/", "target_repo_layout.json"],
                produces_artifacts=["apply_result.json"],
                input_mappings={
                    "package_dir": "package.package_dir",
                    "target_repo_layout": "ground.target_repo_layout",
                },
                condition=StepCondition(
                    expression="apply == True",
                ),
            ),
            # Step 11: Smoke test the applied node (GATED)
            # Only runs if run_tests=true in initial_inputs AND apply succeeded
            PipelineStep(
                name="smoke-test",
                skill="node-smoke-test",
                depends_on=["apply", "ground"],
                requires_artifacts=["apply_result.json", "target_repo_layout.json"],
                produces_artifacts=["smoke_test_result.json"],
                input_mappings={
                    "target_repo_layout": "ground.target_repo_layout",
                    "node_class_name": "normalize.class_name",
                },
                condition=StepCondition(
                    expression="run_tests == True",
                ),
            ),
        ],
        initial_inputs={
            "source_type": "TYPE1",  # Default to TypeScript conversion
            "apply": False,  # Default: dry-run mode (don't apply to target)
            "run_tests": False,  # Default: don't run smoke tests
        },
    )


def get_builtin_pipelines() -> Dict[str, PipelineDefinition]:
    """Get all built-in pipeline definitions."""
    return {
        "type1-convert": get_type1_pipeline(),
        "type2-implement": get_type2_pipeline(),
        "convert_node_v1": get_convert_node_v1_pipeline(),
    }


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def load_pipeline(path: Path, name: Optional[str] = None) -> PipelineDefinition:
    """
    Load a pipeline from a YAML file.
    
    If the file contains multiple pipelines (dict of pipelines),
    use `name` to select one. Otherwise loads the single pipeline.
    
    Args:
        path: Path to YAML file
        name: Optional pipeline name (for multi-pipeline files)
        
    Returns:
        PipelineDefinition
    """
    if not path.exists():
        raise PipelineLoadError(f"Pipeline file not found: {path}")
    
    content = path.read_text()
    data = yaml.safe_load(content)
    
    # Check if it's a multi-pipeline file (has 'pipelines' key)
    if isinstance(data, dict) and "pipelines" in data:
        pipelines_data = data["pipelines"]
        if name is None:
            # Return first pipeline
            first_name = next(iter(pipelines_data.keys()))
            return _parse_pipeline(pipelines_data[first_name], source=str(path))
        elif name in pipelines_data:
            return _parse_pipeline(pipelines_data[name], source=str(path))
        else:
            available = list(pipelines_data.keys())
            raise PipelineLoadError(
                f"Pipeline '{name}' not found. Available: {available}"
            )
    
    # Check if it's a multi-pipeline file with pipelines as top-level keys
    # (format: version + pipeline-name keys where each has name/steps)
    if isinstance(data, dict) and name is not None and name in data:
        pipeline_data = data[name]
        if isinstance(pipeline_data, dict) and "name" in pipeline_data and "steps" in pipeline_data:
            return _parse_pipeline(pipeline_data, source=str(path))
    
    # Check if any top-level key looks like a pipeline (has name and steps)
    if isinstance(data, dict) and name is not None:
        for key, value in data.items():
            if key == name and isinstance(value, dict) and "steps" in value:
                # Add name if missing
                if "name" not in value:
                    value["name"] = key
                return _parse_pipeline(value, source=str(path))
    
    # Single pipeline file
    return _parse_pipeline(data, source=str(path))


def load_pipelines(path: Path) -> List[PipelineDefinition]:
    """
    Load all pipelines from a YAML file or directory.
    
    Args:
        path: Path to YAML file or directory
        
    Returns:
        List of PipelineDefinition
    """
    if path.is_dir():
        pipelines_dict = load_pipelines_from_dir(path)
        return list(pipelines_dict.values())
    
    if not path.exists():
        raise PipelineLoadError(f"Path not found: {path}")
    
    content = path.read_text()
    data = yaml.safe_load(content)
    
    # Check if it's a multi-pipeline file
    if isinstance(data, dict) and "pipelines" in data:
        return [
            _parse_pipeline(pdata, source=str(path))
            for pdata in data["pipelines"].values()
        ]
    
    # Check if it's a dict with pipeline names as keys (our format)
    if isinstance(data, dict):
        # Skip non-pipeline keys like 'version'
        pipelines = []
        for key, pdata in data.items():
            if isinstance(pdata, dict) and "steps" in pdata:
                # This looks like a pipeline
                if "name" not in pdata:
                    pdata["name"] = key
                pipelines.append(_parse_pipeline(pdata, source=str(path)))
        if pipelines:
            return pipelines
    
    # Single pipeline
    return [_parse_pipeline(data, source=str(path))]

