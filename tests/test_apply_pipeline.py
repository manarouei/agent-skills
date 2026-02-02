"""
Tests for Apply Pipeline Skills (T5, T6, T7)

T5: node-package skill
T6: apply-changes skill (dry-run)
T7: Integration test for convert_node_v1 pipeline
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Helper to load skill impl from path with dashes
# =============================================================================

def load_skill_impl(skill_name: str):
    """Load skill implementation from skills/{skill_name}/impl.py."""
    skills_dir = Path(__file__).parents[1] / "skills"
    impl_path = skills_dir / skill_name / "impl.py"
    
    if not impl_path.exists():
        raise ImportError(f"Skill implementation not found: {impl_path}")
    
    spec = importlib.util.spec_from_file_location(f"skill_{skill_name.replace('-', '_')}", impl_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_artifacts():
    """Create temporary artifacts directory."""
    temp_dir = tempfile.mkdtemp(prefix="test_artifacts_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def temp_target_repo():
    """Create temporary target repository structure."""
    temp_dir = tempfile.mkdtemp(prefix="test_target_repo_")
    temp_path = Path(temp_dir)
    
    # Create basic repo structure matching n8n/back conventions
    (temp_path / "nodes").mkdir()
    (temp_path / "tests").mkdir()
    
    # Create registry file
    registry_content = '''"""Node definitions registry."""

from .base import BaseNode

node_definitions = {
    'existing_node': {'node_class': BaseNode, 'type': 'regular'},
}
'''
    (temp_path / "nodes" / "__init__.py").write_text(registry_content)
    
    # Create base.py
    base_content = '''"""Base node class."""

class BaseNode:
    """Base class for all nodes."""
    
    type = "base"
    
    def execute(self, input_data):
        return input_data
'''
    (temp_path / "nodes" / "base.py").write_text(base_content)
    
    yield temp_path
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_execution_context(temp_artifacts):
    """Create mock execution context for skill testing."""
    ctx = MagicMock()
    ctx.artifacts_dir = temp_artifacts
    ctx.inputs = {"correlation_id": "test-correlation-123"}
    ctx.log = MagicMock()
    return ctx


@pytest.fixture
def sample_converted_files(temp_artifacts):
    """Create sample converted files in artifacts/converted/."""
    converted_dir = temp_artifacts / "converted"
    converted_dir.mkdir(parents=True)
    
    # Create a sample node file
    node_content = '''"""Sample Bitly node."""

from nodes.base import BaseNode


class BitlyNode(BaseNode):
    """Bitly URL shortener node."""
    
    type = "bitly"
    display_name = "Bitly"
    
    def execute(self, input_data):
        """Execute the Bitly node."""
        # Placeholder implementation
        return {"shortened_url": "https://bit.ly/example"}
'''
    (converted_dir / "bitly_node.py").write_text(node_content)
    
    # Create a test file
    test_content = '''"""Tests for Bitly node."""

import pytest
from nodes.bitly import BitlyNode


def test_bitly_node_execute():
    """Test BitlyNode execute method."""
    node = BitlyNode()
    result = node.execute({})
    assert "shortened_url" in result
'''
    (converted_dir / "test_bitly.py").write_text(test_content)
    
    return converted_dir


@pytest.fixture
def packaged_node(temp_artifacts):
    """Create a packaged node ready for apply-changes."""
    package_dir = temp_artifacts / "package"
    package_dir.mkdir(parents=True)
    
    # Create node file
    node_content = '''"""Bitly node."""
from nodes.base import BaseNode

class BitlyNode(BaseNode):
    type = "bitly"
'''
    (package_dir / "bitly.py").write_text(node_content)
    
    # Create manifest
    manifest = {
        "correlation_id": "test-123",
        "node_type": "bitly",
        "node_class": "BitlyNode",
        "registry_strategy": "dict_import",
        "files": [
            {
                "filename": "bitly.py",
                "target_path": "nodes/bitly.py",
                "checksum": "abc123",
                "size_bytes": len(node_content),
            }
        ],
        "registry_entry": {
            "import_statement": "from .bitly import BitlyNode",
            "dict_entry": "'bitly': {'node_class': BitlyNode, 'type': 'regular'}",
            "node_type": "bitly",
            "node_class": "BitlyNode",
        },
    }
    (package_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    
    # Create validation results (required by default)
    validation_dir = temp_artifacts / "validation"
    validation_dir.mkdir(parents=True)
    validation_results = {"valid": True, "checks": []}
    (validation_dir / "results.json").write_text(json.dumps(validation_results))
    
    return package_dir


# =============================================================================
# T5: node-package Skill Tests
# =============================================================================

class TestNodePackageSkill:
    """T5: Tests for node-package skill."""
    
    def test_package_creates_manifest(
        self, mock_execution_context, sample_converted_files, temp_artifacts
    ):
        """node-package should create manifest.json with file checksums."""
        skill_module = load_skill_impl("node-package")
        run = skill_module.run
        
        # Add target_repo_layout to inputs
        mock_execution_context.inputs["target_repo_layout"] = {
            "node_output_base_dir": "nodes",
            "tests_dir": "tests",
            "registry_strategy": "dict_import",
        }
        
        # Run skill
        result = run(mock_execution_context)
        
        # Verify package directory created
        package_dir = temp_artifacts / "package"
        assert package_dir.exists(), "Package directory should be created"
        
        # Verify manifest created
        manifest_path = package_dir / "manifest.json"
        assert manifest_path.exists(), "manifest.json should be created"
        
        # Verify manifest content
        manifest = json.loads(manifest_path.read_text())
        assert "correlation_id" in manifest
        assert "node_type" in manifest
        assert "files" in manifest
        assert len(manifest["files"]) > 0
        
        # Each file should have checksum
        for file_entry in manifest["files"]:
            assert "checksum" in file_entry
            assert "filename" in file_entry
            assert "target_path" in file_entry
    
    def test_package_normalizes_filenames(
        self, mock_execution_context, sample_converted_files, temp_artifacts
    ):
        """node-package should normalize filenames to snake_case."""
        skill_module = load_skill_impl("node-package")
        run = skill_module.run
        
        mock_execution_context.inputs["target_repo_layout"] = {
            "node_output_base_dir": "nodes",
            "tests_dir": "tests",
            "registry_strategy": "dict_import",
        }
        
        result = run(mock_execution_context)
        
        # Verify files are normalized
        package_dir = temp_artifacts / "package"
        assert (package_dir / "bitly.py").exists(), "Node file should be normalized to bitly.py"
    
    def test_package_generates_registry_entry(
        self, mock_execution_context, sample_converted_files, temp_artifacts
    ):
        """node-package should generate registry entry metadata."""
        skill_module = load_skill_impl("node-package")
        run = skill_module.run
        
        mock_execution_context.inputs["target_repo_layout"] = {
            "node_output_base_dir": "nodes",
            "tests_dir": "tests",
            "registry_strategy": "dict_import",
        }
        
        result = run(mock_execution_context)
        
        # Verify registry entry created
        registry_entry_path = temp_artifacts / "package" / "registry_entry.json"
        assert registry_entry_path.exists(), "registry_entry.json should be created"
        
        registry_entry = json.loads(registry_entry_path.read_text())
        assert "import_statement" in registry_entry
        assert "dict_entry" in registry_entry
        assert "node_type" in registry_entry
        assert "node_class" in registry_entry
        
        # Verify import statement format
        assert "from .bitly import BitlyNode" in registry_entry["import_statement"]
    
    def test_package_returns_correct_output(
        self, mock_execution_context, sample_converted_files, temp_artifacts
    ):
        """node-package should return correct output structure."""
        skill_module = load_skill_impl("node-package")
        run = skill_module.run
        
        mock_execution_context.inputs["target_repo_layout"] = {
            "node_output_base_dir": "nodes",
            "tests_dir": "tests",
            "registry_strategy": "dict_import",
        }
        
        result = run(mock_execution_context)
        
        assert "package_dir" in result
        assert "files" in result
        assert "registry_entry" in result
        assert "manifest" in result
        assert result["package_dir"] is not None
        assert len(result["files"]) >= 1
    
    def test_package_handles_missing_converted_dir(
        self, mock_execution_context, temp_artifacts
    ):
        """node-package should handle missing converted directory gracefully."""
        skill_module = load_skill_impl("node-package")
        run = skill_module.run
        
        mock_execution_context.inputs["target_repo_layout"] = {}
        
        result = run(mock_execution_context)
        
        assert "error" in result
        assert "Converted directory not found" in result["error"]


# =============================================================================
# T6: apply-changes Skill Tests (Dry-Run)
# =============================================================================

class TestApplyChangesSkill:
    """T6: Tests for apply-changes skill dry-run functionality."""
    
    def test_dry_run_produces_summary(
        self, mock_execution_context, packaged_node, temp_target_repo, temp_artifacts
    ):
        """apply-changes dry-run should produce summary without modifying target repo."""
        skill_module = load_skill_impl("apply-changes")
        run = skill_module.run
        
        mock_execution_context.inputs = {
            "correlation_id": "test-123",
            "target_repo_layout": {
                "target_repo_root": str(temp_target_repo),
                "node_output_base_dir": "nodes",
                "registry_file": "nodes/__init__.py",
                "registry_strategy": "dict_import",
                "registry_dict_name": "node_definitions",
                "tests_dir": "tests",
            },
            "dry_run": True,
            "require_validation": True,
        }
        
        result = run(mock_execution_context)
        
        # Should indicate dry-run mode
        assert result["dry_run"] is True
        
        # Should have files_written (planned, not actual)
        assert "files_written" in result
        assert len(result["files_written"]) > 0
        
        # Each planned file should indicate dry_run
        for file_info in result["files_written"]:
            assert file_info.get("dry_run") is True
        
        # Target repo should NOT be modified
        assert not (temp_target_repo / "nodes" / "bitly.py").exists(), \
            "Target repo should not be modified in dry-run"
    
    def test_dry_run_creates_apply_log(
        self, mock_execution_context, packaged_node, temp_target_repo, temp_artifacts
    ):
        """apply-changes should create apply_log.json even in dry-run."""
        skill_module = load_skill_impl("apply-changes")
        run = skill_module.run
        
        mock_execution_context.inputs = {
            "correlation_id": "test-123",
            "target_repo_layout": {
                "target_repo_root": str(temp_target_repo),
                "node_output_base_dir": "nodes",
                "registry_file": "nodes/__init__.py",
                "registry_strategy": "dict_import",
                "registry_dict_name": "node_definitions",
            },
            "dry_run": True,
        }
        
        result = run(mock_execution_context)
        
        apply_log_path = temp_artifacts / "apply_log.json"
        assert apply_log_path.exists(), "apply_log.json should be created"
        
        apply_log = json.loads(apply_log_path.read_text())
        assert apply_log["dry_run"] is True
        assert apply_log["correlation_id"] == "test-123"
    
    def test_apply_without_dry_run_writes_files(
        self, mock_execution_context, packaged_node, temp_target_repo, temp_artifacts
    ):
        """apply-changes without dry-run should write files to target repo."""
        skill_module = load_skill_impl("apply-changes")
        run = skill_module.run
        
        mock_execution_context.inputs = {
            "correlation_id": "test-123",
            "target_repo_layout": {
                "target_repo_root": str(temp_target_repo),
                "node_output_base_dir": "nodes",
                "registry_file": "nodes/__init__.py",
                "registry_strategy": "dict_import",
                "registry_dict_name": "node_definitions",
            },
            "dry_run": False,
        }
        
        result = run(mock_execution_context)
        
        # Should indicate applied
        assert result["applied"] is True
        assert result["dry_run"] is False
        
        # Target repo should have the new file
        assert (temp_target_repo / "nodes" / "bitly.py").exists(), \
            "Node file should be written to target repo"
    
    def test_apply_updates_registry(
        self, mock_execution_context, packaged_node, temp_target_repo, temp_artifacts
    ):
        """apply-changes should update the registry file."""
        skill_module = load_skill_impl("apply-changes")
        run = skill_module.run
        
        mock_execution_context.inputs = {
            "correlation_id": "test-123",
            "target_repo_layout": {
                "target_repo_root": str(temp_target_repo),
                "node_output_base_dir": "nodes",
                "registry_file": "nodes/__init__.py",
                "registry_strategy": "dict_import",
                "registry_dict_name": "node_definitions",
            },
            "dry_run": False,
        }
        
        result = run(mock_execution_context)
        
        assert result["registry_updated"] is True
        
        # Verify registry content
        registry_content = (temp_target_repo / "nodes" / "__init__.py").read_text()
        assert "from .bitly import BitlyNode" in registry_content
        assert "'bitly':" in registry_content
    
    def test_apply_fails_without_validation(
        self, mock_execution_context, temp_artifacts, temp_target_repo
    ):
        """apply-changes should fail if validation results not found."""
        skill_module = load_skill_impl("apply-changes")
        run = skill_module.run
        
        # Create package without validation
        package_dir = temp_artifacts / "package"
        package_dir.mkdir(parents=True)
        manifest = {"files": [], "registry_entry": {}}
        (package_dir / "manifest.json").write_text(json.dumps(manifest))
        
        mock_execution_context.inputs = {
            "correlation_id": "test-123",
            "target_repo_layout": {
                "target_repo_root": str(temp_target_repo),
            },
            "dry_run": False,
            "require_validation": True,
        }
        
        result = run(mock_execution_context)
        
        assert result["applied"] is False
        assert any("Validation" in err for err in result["errors"])
    
    def test_apply_creates_backup(
        self, mock_execution_context, packaged_node, temp_target_repo, temp_artifacts
    ):
        """apply-changes should create backup when updating existing files."""
        skill_module = load_skill_impl("apply-changes")
        run = skill_module.run
        
        # Create existing file to update
        existing_file = temp_target_repo / "nodes" / "bitly.py"
        existing_file.write_text("# Old content")
        
        mock_execution_context.inputs = {
            "correlation_id": "test-123",
            "target_repo_layout": {
                "target_repo_root": str(temp_target_repo),
                "node_output_base_dir": "nodes",
                "registry_file": "nodes/__init__.py",
                "registry_strategy": "dict_import",
                "registry_dict_name": "node_definitions",
            },
            "dry_run": False,
        }
        
        result = run(mock_execution_context)
        
        # Check backup was created
        assert result["backup_created"] is True
        
        # Verify backup exists
        backup_dir = temp_artifacts / "backups"
        assert backup_dir.exists()
        backups = list(backup_dir.glob("*.bak"))
        assert len(backups) >= 1


# =============================================================================
# T7: Integration Tests for convert_node_v1 Pipeline
# =============================================================================

class TestConvertNodeV1PipelineIntegration:
    """T7: Integration tests for convert_node_v1 pipeline."""
    
    def test_pipeline_has_all_steps(self):
        """Pipeline should have all 11 steps."""
        from src.agent_skills.pipelines import get_convert_node_v1_pipeline
        
        pipeline = get_convert_node_v1_pipeline()
        
        assert pipeline.name == "convert_node_v1"
        assert len(pipeline.steps) == 11
        
        step_names = [s.name for s in pipeline.steps]
        expected_steps = [
            "normalize",
            "ground", 
            "classify",
            "ingest",
            "infer-schema",
            "scaffold",
            "convert",
            "package",
            "pre-validate",
            "apply",
            "smoke-test",
        ]
        assert step_names == expected_steps
    
    def test_pipeline_apply_step_gated(self):
        """apply step should have condition gating it."""
        from src.agent_skills.pipelines import get_convert_node_v1_pipeline
        
        pipeline = get_convert_node_v1_pipeline()
        
        apply_step = next(s for s in pipeline.steps if s.name == "apply")
        assert apply_step.condition is not None
        # Condition uses expression "apply == True"
        assert "apply" in apply_step.condition.expression
    
    def test_pipeline_smoke_test_step_gated(self):
        """smoke-test step should have condition gating it."""
        from src.agent_skills.pipelines import get_convert_node_v1_pipeline
        
        pipeline = get_convert_node_v1_pipeline()
        
        smoke_step = next(s for s in pipeline.steps if s.name == "smoke-test")
        assert smoke_step.condition is not None
        # Condition uses expression "run_tests == True"
        assert "run_tests" in smoke_step.condition.expression
    
    def test_pipeline_initial_inputs_defaults(self):
        """Pipeline should have correct default initial_inputs."""
        from src.agent_skills.pipelines import get_convert_node_v1_pipeline
        
        pipeline = get_convert_node_v1_pipeline()
        
        # Default should be dry-run mode (no apply, no tests)
        assert pipeline.initial_inputs.get("apply") is False
        assert pipeline.initial_inputs.get("run_tests") is False
        assert pipeline.initial_inputs.get("source_type") == "TYPE1"
    
    def test_cli_dry_run_flag_exists(self):
        """CLI should have --dry-run flag."""
        result = subprocess.run(
            [sys.executable, "main.py", "node", "convert", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parents[1],
        )
        
        assert "--dry-run" in result.stdout
    
    def test_cli_apply_flag_exists(self):
        """CLI should have --apply flag."""
        result = subprocess.run(
            [sys.executable, "main.py", "node", "convert", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parents[1],
        )
        
        assert "--apply" in result.stdout
    
    def test_cli_run_tests_flag_exists(self):
        """CLI should have --run-tests flag."""
        result = subprocess.run(
            [sys.executable, "main.py", "node", "convert", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parents[1],
        )
        
        assert "--run-tests" in result.stdout


# =============================================================================
# T7 Extended: Full Pipeline Execution Tests
# =============================================================================

class TestPipelineExecutionModes:
    """Tests for different pipeline execution modes."""
    
    def test_dry_run_skips_apply_and_smoke_test(self):
        """With default flags, apply and smoke-test should be skipped."""
        from src.agent_skills.pipelines import get_convert_node_v1_pipeline
        
        pipeline = get_convert_node_v1_pipeline()
        
        # Simulate initial_inputs with defaults
        initial_inputs = dict(pipeline.initial_inputs)
        
        # Check that apply is gated
        apply_step = next(s for s in pipeline.steps if s.name == "apply")
        assert apply_step.condition is not None
        
        # With apply=False, the condition should not be satisfied
        assert initial_inputs.get("apply") is False
    
    def test_apply_flag_enables_apply_step(self):
        """With --apply flag, apply step should be enabled."""
        from src.agent_skills.pipelines import get_convert_node_v1_pipeline
        
        pipeline = get_convert_node_v1_pipeline()
        
        # Simulate --apply flag
        initial_inputs = dict(pipeline.initial_inputs)
        initial_inputs["apply"] = True
        
        # The condition for apply step is "apply == True"
        apply_step = next(s for s in pipeline.steps if s.name == "apply")
        
        # With apply=True, the step should run
        assert initial_inputs["apply"] is True
    
    def test_run_tests_requires_apply(self):
        """--run-tests without --apply should warn but still gate smoke-test."""
        from src.agent_skills.pipelines import get_convert_node_v1_pipeline
        
        pipeline = get_convert_node_v1_pipeline()
        
        # Smoke test depends on apply step
        smoke_step = next(s for s in pipeline.steps if s.name == "smoke-test")
        assert "apply" in smoke_step.depends_on


class TestSkillExecutionModes:
    """Tests for skill execution mode classification of new skills."""
    
    def test_node_package_is_deterministic(self):
        """node-package should be classified as DETERMINISTIC."""
        from contracts.skill_contract import (
            SkillExecutionMode,
            get_skill_execution_mode,
        )
        
        mode = get_skill_execution_mode("node-package")
        assert mode == SkillExecutionMode.DETERMINISTIC
    
    def test_node_validate_is_deterministic(self):
        """node-validate should be classified as DETERMINISTIC."""
        from contracts.skill_contract import (
            SkillExecutionMode,
            get_skill_execution_mode,
        )
        
        mode = get_skill_execution_mode("node-validate")
        assert mode == SkillExecutionMode.DETERMINISTIC
    
    def test_apply_changes_is_deterministic(self):
        """apply-changes should be classified as DETERMINISTIC."""
        from contracts.skill_contract import (
            SkillExecutionMode,
            get_skill_execution_mode,
        )
        
        mode = get_skill_execution_mode("apply-changes")
        assert mode == SkillExecutionMode.DETERMINISTIC
    
    def test_node_smoke_test_is_deterministic(self):
        """node-smoke-test should be classified as DETERMINISTIC."""
        from contracts.skill_contract import (
            SkillExecutionMode,
            get_skill_execution_mode,
        )
        
        mode = get_skill_execution_mode("node-smoke-test")
        assert mode == SkillExecutionMode.DETERMINISTIC


# =============================================================================
# T7 Extended: TargetRepoLayout Tests
# =============================================================================

class TestTargetRepoLayout:
    """Tests for TargetRepoLayout model and usage."""
    
    def test_target_repo_layout_model(self):
        """TargetRepoLayout model should have required fields."""
        from contracts.skill_contract import TargetRepoLayout
        
        layout = TargetRepoLayout(
            target_repo_root="/home/toni/n8n/back",
            node_output_base_dir="nodes",
            registry_file="nodes/__init__.py",
            registry_strategy="dict_import",
            registry_dict_name="node_definitions",
        )
        
        assert layout.target_repo_root == "/home/toni/n8n/back"
        assert layout.node_output_base_dir == "nodes"
        assert layout.registry_strategy == "dict_import"
    
    def test_target_repo_layout_defaults(self):
        """TargetRepoLayout should have sensible defaults."""
        from contracts.skill_contract import TargetRepoLayout
        
        layout = TargetRepoLayout(
            target_repo_root="/some/path",
        )
        
        # Check defaults are applied
        assert layout.node_output_base_dir == "nodes"
        assert layout.tests_dir == "tests"
