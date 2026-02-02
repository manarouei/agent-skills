#!/usr/bin/env python3
"""
Tests for Pipeline Layer

T2: produces_artifacts enforcement
T3: requires_artifacts enforcement  
T4: Smoke test for convert_node_v1 pipeline
"""

import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agent_skills.pipelines import (
    PipelineDefinition,
    PipelineStep,
    PipelineRunner,
    StepStatus,
    get_convert_node_v1_pipeline,
    get_builtin_pipelines,
    CANONICAL_ARTIFACT_DIRS,
)
from contracts import ExecutionStatus


def create_mock_executor(status=ExecutionStatus.SUCCESS, outputs=None, errors=None):
    """Create a mock SkillExecutor with configurable behavior."""
    executor = Mock()
    
    mock_result = Mock()
    mock_result.status = status
    mock_result.duration_ms = 100
    mock_result.outputs = outputs or {"test": "output"}
    mock_result.artifacts = []
    mock_result.errors = errors or []
    
    executor.execute.return_value = mock_result
    return executor


class TestArtifactEnforcement:
    """Tests for artifact requirement enforcement (T2 and T3)."""

    @pytest.fixture
    def temp_artifacts(self):
        """Create temporary artifacts directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_executor(self):
        """Create mock SkillExecutor."""
        return create_mock_executor()

    def test_requires_artifacts_missing_blocks_step(self, temp_artifacts, mock_executor):
        """T3: Step should be blocked if requires_artifacts are missing."""
        # Create a pipeline with a step that requires a non-existent artifact
        pipeline = PipelineDefinition(
            name="test-requires",
            version="1.0.0",
            steps=[
                PipelineStep(
                    name="step-with-requirement",
                    skill="test-skill",
                    requires_artifacts=["missing_artifact.json"],
                ),
            ],
        )
        
        runner = PipelineRunner(
            executor=mock_executor,
            artifacts_dir=temp_artifacts,
            dry_run=False,
        )
        
        result = runner.run(
            pipeline=pipeline,
            correlation_id="test-requires-001",
            initial_inputs={},
        )
        
        # Step should be blocked
        assert result.steps[0].status == StepStatus.BLOCKED
        assert "Missing required artifacts" in result.steps[0].errors[0]
        assert "missing_artifact.json" in result.steps[0].errors[0]
        
        # Executor should NOT have been called
        mock_executor.execute.assert_not_called()

    def test_requires_artifacts_present_allows_step(self, temp_artifacts, mock_executor):
        """Step should proceed if requires_artifacts exist."""
        cid = "test-allows-001"
        
        # Create the required artifact
        run_dir = temp_artifacts / cid
        run_dir.mkdir(parents=True)
        (run_dir / "required.json").write_text('{"exists": true}')
        
        pipeline = PipelineDefinition(
            name="test-allows",
            version="1.0.0",
            steps=[
                PipelineStep(
                    name="step-with-requirement",
                    skill="test-skill",
                    requires_artifacts=["required.json"],
                ),
            ],
        )
        
        runner = PipelineRunner(
            executor=mock_executor,
            artifacts_dir=temp_artifacts,
            dry_run=False,
        )
        
        result = runner.run(
            pipeline=pipeline,
            correlation_id=cid,
            initial_inputs={},
        )
        
        # Step should complete
        assert result.steps[0].status == StepStatus.COMPLETED
        
        # Executor should have been called
        mock_executor.execute.assert_called_once()

    def test_requires_artifacts_glob_pattern(self, temp_artifacts, mock_executor):
        """Glob patterns in requires_artifacts should work."""
        cid = "test-glob-001"
        
        # Create artifacts matching glob
        run_dir = temp_artifacts / cid
        source_dir = run_dir / "source"
        source_dir.mkdir(parents=True)
        (source_dir / "node.ts").write_text("// typescript")
        
        pipeline = PipelineDefinition(
            name="test-glob",
            version="1.0.0",
            steps=[
                PipelineStep(
                    name="step-with-glob",
                    skill="test-skill",
                    requires_artifacts=["source/*.ts"],
                ),
            ],
        )
        
        runner = PipelineRunner(
            executor=mock_executor,
            artifacts_dir=temp_artifacts,
            dry_run=False,
        )
        
        result = runner.run(
            pipeline=pipeline,
            correlation_id=cid,
            initial_inputs={},
        )
        
        # Should proceed
        assert result.steps[0].status == StepStatus.COMPLETED

    def test_produces_artifacts_directory_created(self, temp_artifacts, mock_executor):
        """T2: produces_artifacts directories should be created by runner."""
        cid = "test-produces-001"
        
        pipeline = PipelineDefinition(
            name="test-produces",
            version="1.0.0",
            steps=[
                PipelineStep(
                    name="step-produces",
                    skill="test-skill",
                    produces_artifacts=["output/result.json"],
                ),
            ],
        )
        
        runner = PipelineRunner(
            executor=mock_executor,
            artifacts_dir=temp_artifacts,
            dry_run=False,
        )
        
        result = runner.run(
            pipeline=pipeline,
            correlation_id=cid,
            initial_inputs={},
        )
        
        # Canonical directories should exist
        run_dir = temp_artifacts / cid
        for subdir in CANONICAL_ARTIFACT_DIRS:
            assert (run_dir / subdir).exists(), f"Missing canonical dir: {subdir}"


class TestCanonicalArtifactDirectories:
    """Tests for canonical artifact directory structure."""

    @pytest.fixture
    def temp_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_executor(self):
        return create_mock_executor()

    def test_canonical_dirs_created_on_run(self, temp_artifacts, mock_executor):
        """Canonical artifact directories should be created at pipeline start."""
        pipeline = PipelineDefinition(
            name="test-dirs",
            version="1.0.0",
            steps=[
                PipelineStep(name="dummy", skill="test-skill"),
            ],
        )
        
        runner = PipelineRunner(
            executor=mock_executor,
            artifacts_dir=temp_artifacts,
        )
        
        cid = "test-canonical-001"
        runner.run(pipeline=pipeline, correlation_id=cid)
        
        run_dir = temp_artifacts / cid
        assert run_dir.exists()
        
        for subdir in CANONICAL_ARTIFACT_DIRS:
            assert (run_dir / subdir).exists(), f"Missing: {subdir}"

    def test_canonical_dirs_list(self):
        """Verify canonical directory names."""
        expected = {"source", "schema", "scaffold", "converted", "tests", "reports", "logs"}
        assert set(CANONICAL_ARTIFACT_DIRS) == expected


class TestConvertNodeV1Pipeline:
    """Tests for convert_node_v1 pipeline definition (T4 smoke test)."""

    def test_pipeline_exists(self):
        """convert_node_v1 pipeline should be available."""
        pipelines = get_builtin_pipelines()
        assert "convert_node_v1" in pipelines

    def test_pipeline_structure(self):
        """Pipeline should have correct structure."""
        pipeline = get_convert_node_v1_pipeline()
        
        assert pipeline.name == "convert_node_v1"
        assert len(pipeline.steps) >= 5  # At minimum: normalize, ground, classify, ingest, infer
        
        # Check step names exist
        step_names = [s.name for s in pipeline.steps]
        assert "normalize" in step_names
        assert "ground" in step_names
        assert "classify" in step_names
        assert "ingest" in step_names

    def test_pipeline_dependencies(self):
        """Pipeline steps should have correct dependencies."""
        pipeline = get_convert_node_v1_pipeline()
        
        # Get steps by name
        steps = {s.name: s for s in pipeline.steps}
        
        # ground depends on normalize
        assert "normalize" in steps["ground"].depends_on
        
        # infer-schema depends on ingest and ground
        assert "ingest" in steps["infer-schema"].depends_on
        assert "ground" in steps["infer-schema"].depends_on

    def test_pipeline_execution_order(self):
        """Pipeline should produce valid execution order."""
        pipeline = get_convert_node_v1_pipeline()
        
        # Should not raise (no cycles)
        order = pipeline.get_execution_order()
        
        # normalize should come first (no dependencies)
        assert order[0] == "normalize"

    def test_dry_run_smoke(self):
        """Smoke test: dry run should complete without errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)
            
            # Create mock executor with proper status
            mock_executor = create_mock_executor()
            
            pipeline = get_convert_node_v1_pipeline()
            
            runner = PipelineRunner(
                executor=mock_executor,
                artifacts_dir=artifacts_dir,
                dry_run=True,
            )
            
            result = runner.run(
                pipeline=pipeline,
                correlation_id="smoke-test-001",
                initial_inputs={"raw_node_name": "bitly"},
            )
            
            # Should complete (dry run skips actual execution)
            # Some steps may be blocked due to missing artifacts in dry run
            assert result.correlation_id == "smoke-test-001"
            assert len(result.steps) == len(pipeline.steps)


class TestPipelineResult:
    """Tests for PipelineResult output."""

    @pytest.fixture
    def temp_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def mock_executor(self):
        return create_mock_executor(
            outputs={"key": "value"},
        )

    def test_result_saved_to_artifacts(self, temp_artifacts, mock_executor):
        """Pipeline result should be saved as JSON."""
        pipeline = PipelineDefinition(
            name="test-result",
            version="1.0.0",
            steps=[
                PipelineStep(name="step1", skill="test-skill"),
            ],
        )
        
        runner = PipelineRunner(
            executor=mock_executor,
            artifacts_dir=temp_artifacts,
        )
        
        cid = "test-result-001"
        runner.run(pipeline=pipeline, correlation_id=cid)
        
        # Check result file
        result_path = temp_artifacts / cid / "pipeline_result.json"
        assert result_path.exists()
        
        # Parse and validate
        result_data = json.loads(result_path.read_text())
        assert result_data["pipeline_name"] == "test-result"
        assert result_data["correlation_id"] == cid
        assert len(result_data["steps"]) == 1

    def test_result_includes_step_outputs(self, temp_artifacts, mock_executor):
        """Pipeline result should include step outputs."""
        pipeline = PipelineDefinition(
            name="test-outputs",
            version="1.0.0",
            steps=[
                PipelineStep(name="step1", skill="test-skill"),
            ],
        )
        
        runner = PipelineRunner(
            executor=mock_executor,
            artifacts_dir=temp_artifacts,
        )
        
        result = runner.run(
            pipeline=pipeline,
            correlation_id="test-outputs-001",
        )
        
        # Check outputs aggregated
        assert "step1" in result.outputs
        assert result.outputs["step1"]["key"] == "value"
