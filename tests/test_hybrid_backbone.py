#!/usr/bin/env python3
"""
Tests for Hybrid Backbone Architecture

Tests the core behaviors of the deterministic backbone + bounded AI advisor pattern:
1. Skill execution mode classification (DETERMINISTIC, HYBRID, ADVISOR_ONLY)
2. Trace map evidence requirements
3. Fix loop stops at max iterations (3) with escalation artifact
4. Sync-celery enforcement on generated code
5. PR prepare does NOT auto-merge by default

These tests verify the safety-critical controls of bounded autonomy.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from contracts import (
    SkillExecutionMode,
    SKILL_EXECUTION_MODES,
    get_skill_execution_mode,
    AutonomyLevel,
    ExecutionStatus,
)
from runtime.executor import (
    SkillExecutor,
    SkillRegistry,
    RuntimeConfig,
    DEFAULT_RUNTIME_CONFIG,
    AdvisorOutputValidator,
    GateResult,
    SyncCeleryGate,
    BoundedFixLoop,
    ExecutionResult,
    create_executor,
)


@pytest.fixture
def repo_root():
    """Get repository root."""
    return Path(__file__).parent.parent


@pytest.fixture
def skills_dir(repo_root):
    """Get skills directory."""
    return repo_root / "skills"


@pytest.fixture
def scripts_dir(repo_root):
    """Get scripts directory."""
    return repo_root / "scripts"


@pytest.fixture
def temp_artifacts():
    """Create temporary artifacts directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def executor(skills_dir, scripts_dir, temp_artifacts):
    """Create skill executor with temp artifacts."""
    return SkillExecutor(
        skills_dir=skills_dir,
        scripts_dir=scripts_dir,
        artifacts_dir=temp_artifacts,
    )


class TestSkillExecutionModeClassification:
    """Tests for skill execution mode classification."""
    
    def test_all_skills_have_execution_mode(self, skills_dir):
        """All 12 skills should have an explicit execution mode."""
        registry = SkillRegistry(skills_dir)
        skills = registry.list_skills()
        
        assert len(skills) == 12, f"Expected 12 skills, got {len(skills)}"
        
        for skill_name in skills:
            mode = get_skill_execution_mode(skill_name)
            assert mode is not None, f"Skill {skill_name} has no execution mode"
            assert mode in SkillExecutionMode, f"Invalid mode for {skill_name}"
    
    def test_deterministic_skills_correct(self):
        """Verify deterministic skills are classified correctly."""
        deterministic_skills = [
            "node-normalize",
            "source-classify",
            "source-ingest",
            "schema-build",
            "node-scaffold",
            "code-validate",
            "pr-prepare",
        ]
        
        for skill_name in deterministic_skills:
            mode = get_skill_execution_mode(skill_name)
            assert mode == SkillExecutionMode.DETERMINISTIC, \
                f"{skill_name} should be DETERMINISTIC, got {mode}"
    
    def test_hybrid_skills_correct(self):
        """Verify hybrid skills are classified correctly."""
        hybrid_skills = ["schema-infer", "test-generate"]
        
        for skill_name in hybrid_skills:
            mode = get_skill_execution_mode(skill_name)
            assert mode == SkillExecutionMode.HYBRID, \
                f"{skill_name} should be HYBRID, got {mode}"
    
    def test_advisor_only_skills_correct(self):
        """Verify advisor-only skills are classified correctly."""
        advisor_skills = ["code-convert", "code-implement", "code-fix"]
        
        for skill_name in advisor_skills:
            mode = get_skill_execution_mode(skill_name)
            assert mode == SkillExecutionMode.ADVISOR_ONLY, \
                f"{skill_name} should be ADVISOR_ONLY, got {mode}"
    
    def test_unknown_skill_defaults_to_deterministic(self):
        """Unknown skills should default to DETERMINISTIC (safe fallback)."""
        mode = get_skill_execution_mode("unknown-skill-xyz")
        assert mode == SkillExecutionMode.DETERMINISTIC


class TestTraceMapEvidence:
    """Tests for trace map evidence requirements."""
    
    def test_trace_map_assumption_ratio_under_30_percent(self, temp_artifacts):
        """Trace map with <30% assumptions should pass."""
        trace_map = {
            "correlation_id": "TEST123",
            "node_type": "test-node",
            "trace_entries": [
                {"field_path": "field1", "source": "API_DOCS", "evidence": "Found in API docs", "confidence": "high"},
                {"field_path": "field2", "source": "SOURCE_CODE", "evidence": "Found in source", "confidence": "high"},
                {"field_path": "field3", "source": "SOURCE_CODE", "evidence": "Found in source", "confidence": "high"},
                {"field_path": "field4", "source": "ASSUMPTION", "evidence": "Assumed pattern", "confidence": "low"},
            ],
        }
        
        # 1/4 = 25% assumptions - should pass
        validator = AdvisorOutputValidator(temp_artifacts, temp_artifacts)
        result = validator.validate_schema_output({"type": "test"}, trace_map, "TEST123")
        assert result.passed, f"Should pass with 25% assumptions: {result.message}"
    
    def test_trace_map_assumption_ratio_over_30_percent(self, temp_artifacts):
        """Trace map with >30% assumptions should fail."""
        trace_map = {
            "correlation_id": "TEST123",
            "node_type": "test-node",
            "trace_entries": [
                {"field_path": "field1", "source": "API_DOCS", "evidence": "Found in docs", "confidence": "high"},
                {"field_path": "field2", "source": "ASSUMPTION", "evidence": "Assumed", "confidence": "low"},
                {"field_path": "field3", "source": "ASSUMPTION", "evidence": "Assumed", "confidence": "low"},
            ],
        }
        
        # 2/3 = 66% assumptions - should fail
        validator = AdvisorOutputValidator(temp_artifacts, temp_artifacts)
        result = validator.validate_schema_output({"type": "test"}, trace_map, "TEST123")
        assert not result.passed, "Should fail with 66% assumptions"
        assert "30%" in result.message or "assumption" in result.message.lower()


class TestFixLoopEscalation:
    """Tests for bounded fix loop escalation."""
    
    def test_fix_loop_max_is_3(self, executor):
        """Fix loop max iterations should be 3 (hard limit)."""
        assert executor.FIX_LOOP_MAX == 3
    
    def test_bounded_fix_loop_escalates_after_3(self, executor, temp_artifacts):
        """Fix loop should escalate after 3 iterations.
        
        This test verifies the BoundedFixLoop escalation logic by mocking
        the executor.execute method directly to avoid gate enforcement issues
        in the test environment.
        """
        correlation_id = "FIX_LOOP_TEST"
        session_dir = temp_artifacts / correlation_id
        session_dir.mkdir(parents=True)
        
        # Track iterations
        iterations_run = {"count": 0}
        
        # Mock execute directly to bypass gate checks
        original_execute = executor.execute
        
        def mock_execute(skill_name, inputs, corr_id):
            if skill_name == "code-fix":
                iterations_run["count"] += 1
                # Return SUCCESS so loop continues
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    outputs={"fixed": False, "changes_made": ["attempted fix"]},
                    artifacts=[],
                    errors=[],
                    trace=[],
                    duration_ms=10,
                    agent_metadata=None,
                    is_terminal=True,
                    agent_state=None,
                )
            elif skill_name == "code-validate":
                # Always return errors to trigger another fix iteration
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    outputs={"errors": [{"error": "persistent test error"}], "passed": False},
                    artifacts=[],
                    errors=[],
                    trace=[],
                    duration_ms=10,
                    agent_metadata=None,
                    is_terminal=True,
                    agent_state=None,
                )
            return original_execute(skill_name, inputs, corr_id)
        
        executor.execute = mock_execute
        
        try:
            # Run bounded fix loop
            fix_loop = BoundedFixLoop(executor, max_iterations=3)
            result = fix_loop.run(
                correlation_id=correlation_id,
                initial_errors=[{"error": "initial test error"}],
            )
            
            # Should escalate after 3 iterations
            assert result.status == ExecutionStatus.ESCALATED
            # The fix was called 3 times
            assert iterations_run["count"] == 3
            assert result.outputs.get("iterations") == 3
            assert "remaining_errors" in result.outputs
            assert any("escalat" in e.lower() for e in result.errors)
        finally:
            # Restore original execute
            executor.execute = original_execute


class TestSyncCeleryEnforcement:
    """Tests for sync-celery compatibility enforcement."""
    
    def test_async_code_fails_validation(self, temp_artifacts):
        """Code with async/await should fail sync-celery gate."""
        gate = SyncCeleryGate(temp_artifacts)
        
        async_code = '''
async def execute(self):
    result = await self.fetch_data()
    return result
'''
        
        result = gate.check_code(async_code)
        assert not result.passed
        assert "async" in result.message.lower() or len(result.details.get("violations", [])) > 0
    
    def test_asyncio_import_fails_validation(self, temp_artifacts):
        """Code importing asyncio should fail sync-celery gate."""
        gate = SyncCeleryGate(temp_artifacts)
        
        asyncio_code = '''
import asyncio
from aiohttp import ClientSession

def execute(self):
    pass
'''
        
        result = gate.check_code(asyncio_code)
        assert not result.passed
        violations = result.details.get("violations", [])
        assert any("asyncio" in v.get("pattern", "").lower() or "aiohttp" in v.get("pattern", "").lower() 
                   for v in violations)
    
    def test_sync_code_passes_validation(self, temp_artifacts):
        """Normal synchronous code should pass sync-celery gate."""
        gate = SyncCeleryGate(temp_artifacts)
        
        sync_code = '''
import requests

def execute(self):
    response = requests.get("https://api.example.com", timeout=30)
    return response.json()
'''
        
        result = gate.check_code(sync_code)
        assert result.passed, f"Sync code should pass: {result.message}"


class TestPRAutoMergePrevention:
    """Tests for PR auto-merge prevention (human-in-the-loop)."""
    
    def test_default_config_disables_auto_merge(self):
        """Default runtime config should disable auto-merge."""
        config = DEFAULT_RUNTIME_CONFIG
        assert config.auto_merge_enabled is False
        assert config.require_human_review is True
    
    def test_runtime_config_auto_merge_default_false(self):
        """RuntimeConfig should default to auto_merge_enabled=False."""
        config = RuntimeConfig()
        assert config.auto_merge_enabled is False
    
    def test_executor_uses_config(self, skills_dir, scripts_dir, temp_artifacts):
        """Executor should use runtime config."""
        custom_config = RuntimeConfig(
            auto_merge_enabled=False,
            require_human_review=True,
        )
        
        executor = SkillExecutor(
            skills_dir=skills_dir,
            scripts_dir=scripts_dir,
            artifacts_dir=temp_artifacts,
            config=custom_config,
        )
        
        assert executor.config.auto_merge_enabled is False
        assert executor.config.require_human_review is True
    
    def test_pr_prepare_outputs_human_review_required(self, executor, temp_artifacts):
        """pr-prepare skill outputs should indicate human review required."""
        # Set up required artifacts
        correlation_id = "PR_PREPARE_TEST"
        session_dir = temp_artifacts / correlation_id
        session_dir.mkdir(parents=True)
        
        # Create required artifacts for pr-prepare
        repo_facts = {
            "basenode_contract_path": "contracts/BASENODE_CONTRACT.md",
            "node_loader_paths": ["runtime/executor.py"],
            "golden_node_paths": ["skills/node-scaffold/SKILL.md"],
            "test_command": "pytest",
        }
        (session_dir / "repo_facts.json").write_text(json.dumps(repo_facts))
        (session_dir / "allowlist.json").write_text(json.dumps({"allowed_paths": ["**"], "forbidden_paths": []}))
        (session_dir / "request_snapshot.json").write_text("{}")
        (session_dir / "inferred_schema.json").write_text("{}")
        (session_dir / "trace_map.json").write_text('{"correlation_id": "test", "node_type": "test", "trace_entries": []}')
        (session_dir / "validation_logs.txt").write_text("tests passed")
        (session_dir / "diff.patch").write_text("")
        (session_dir / "source_bundle").mkdir()
        
        def mock_pr_prepare(ctx):
            return {
                "pr_artifacts": {"title": "Test PR", "description": "Test"},
                "node_definitions_entry": "# test",
                "merge_requested": False,  # Not requesting merge
            }
        
        executor.register_implementation("pr-prepare", mock_pr_prepare)
        
        result = executor.execute(
            skill_name="pr-prepare",
            inputs={
                "correlation_id": correlation_id,
                "node_schema": {},
                "validation_report": {"passed": True},
                "files_modified": [],
            },
            correlation_id=correlation_id,
        )
        
        # Outputs should indicate merge was NOT executed and human review is required
        assert result.outputs.get("merge_executed") is False
        assert result.outputs.get("human_review_required") is True


class TestAdvisorOutputValidation:
    """Tests for advisor output validation."""
    
    def test_validate_json_output(self, temp_artifacts):
        """JSON-serializable outputs should validate."""
        validator = AdvisorOutputValidator(temp_artifacts, temp_artifacts)
        
        # Valid JSON output
        result = validator.validate_json_output({"key": "value", "count": 42})
        assert result.passed
        
        # Invalid (non-serializable) output
        class NonSerializable:
            pass
        
        result = validator.validate_json_output({"obj": NonSerializable()})
        assert not result.passed
    
    def test_validate_code_output_syntax_error(self, temp_artifacts):
        """Code with syntax errors should fail validation."""
        validator = AdvisorOutputValidator(temp_artifacts, temp_artifacts)
        
        bad_code = '''
def broken_function(
    # Missing closing paren and body
'''
        
        result = validator.validate_code_output(bad_code, "TEST123")
        assert not result.passed
        assert "syntax" in result.message.lower()
    
    def test_validate_patch_output_scope(self, temp_artifacts):
        """Patch outputs outside scope should fail validation."""
        validator = AdvisorOutputValidator(temp_artifacts, temp_artifacts)
        
        # Trying to modify forbidden file
        result = validator.validate_patch_output(
            files_to_modify=["nodes/base.py"],
            allowed_patterns=["nodes/**/*.py"],
            forbidden_patterns=["**/base.py"],
        )
        
        assert not result.passed
        assert "scope" in result.message.lower() or "violation" in result.message.lower()


class TestExecutionModeLogging:
    """Tests for execution mode logging in traces."""
    
    def test_execution_mode_logged(self, executor, temp_artifacts):
        """Execution mode should be logged in trace."""
        correlation_id = "MODE_LOG_TEST"
        session_dir = temp_artifacts / correlation_id
        session_dir.mkdir(parents=True)
        
        # node-normalize is DETERMINISTIC
        result = executor.execute(
            skill_name="node-normalize",
            inputs={"raw_node_name": "Test Node"},
            correlation_id=correlation_id,
        )
        
        # Check trace for execution_mode event
        mode_events = [e for e in result.trace if e["event"] == "execution_mode"]
        assert len(mode_events) == 1
        assert mode_events[0]["data"]["mode"] == "DETERMINISTIC"
        assert mode_events[0]["data"]["is_advisor"] is False
    
    def test_advisor_skill_logs_mode(self, executor, temp_artifacts):
        """Advisor skills should log their mode correctly."""
        correlation_id = "ADVISOR_LOG_TEST"
        session_dir = temp_artifacts / correlation_id
        session_dir.mkdir(parents=True)
        
        # Create required artifacts
        repo_facts = {
            "basenode_contract_path": "contracts/BASENODE_CONTRACT.md",
            "node_loader_paths": ["runtime/executor.py"],
            "golden_node_paths": ["skills/node-scaffold/SKILL.md"],
            "test_command": "pytest",
        }
        (session_dir / "repo_facts.json").write_text(json.dumps(repo_facts))
        (session_dir / "allowlist.json").write_text(json.dumps({"allowed_paths": ["**"], "forbidden_paths": []}))
        
        def mock_code_fix(ctx):
            return {"fixed": True, "changes_made": []}
        
        executor.register_implementation("code-fix", mock_code_fix)
        
        result = executor.execute(
            skill_name="code-fix",
            inputs={
                "correlation_id": correlation_id,
                "validation_report": {},
                "files_modified": [],
                "allowlist": {},
                "iteration": 1,
            },
            correlation_id=correlation_id,
        )
        
        # Check trace for execution_mode event
        mode_events = [e for e in result.trace if e["event"] == "execution_mode"]
        assert len(mode_events) == 1
        assert mode_events[0]["data"]["mode"] == "ADVISOR_ONLY"
        assert mode_events[0]["data"]["is_advisor"] is True
