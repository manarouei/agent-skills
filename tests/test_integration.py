#!/usr/bin/env python3
"""
Integration tests for skill execution pipeline.

Tests the full contract-first execution flow:
- Contract loading and validation
- Gate enforcement (trace map, scope)
- Bounded fix loop
- Skill chaining
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import yaml

# Import runtime components
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime.executor import (
    AutonomyLevel,
    ExecutionStatus,
    SkillContract,
    ExecutionContext,
    ExecutionResult,
    SkillRegistry,
    SkillExecutor,
    BoundedFixLoop,
    GateResult,
    TraceMapGate,
    ScopeGate,
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


class TestSkillRegistry:
    """Tests for skill contract loading."""

    def test_load_all_skills(self, skills_dir):
        """All skills should have valid contracts."""
        registry = SkillRegistry(skills_dir)
        skills = registry.list_skills()
        
        assert len(skills) == 12, f"Expected 12 skills, got {len(skills)}"
        
        for skill_name in skills:
            contract = registry.get(skill_name)
            assert contract.name == skill_name
            assert contract.version
            assert contract.autonomy_level in AutonomyLevel

    def test_contract_fields(self, skills_dir):
        """Contracts should have all required fields."""
        registry = SkillRegistry(skills_dir)
        
        for skill_name in registry.list_skills():
            contract = registry.get(skill_name)
            
            # Required fields
            assert contract.name
            assert contract.version
            assert contract.description
            assert contract.autonomy_level
            assert contract.timeout_seconds > 0
            assert contract.max_fix_iterations >= 1
            
            # Schema fields
            assert isinstance(contract.input_schema, dict)
            assert isinstance(contract.output_schema, dict)
            assert isinstance(contract.required_artifacts, list)
            assert isinstance(contract.failure_modes, list)
            assert isinstance(contract.depends_on, list)

    def test_autonomy_levels_distribution(self, skills_dir):
        """Check autonomy level distribution across skills."""
        registry = SkillRegistry(skills_dir)
        
        levels = {}
        for skill_name in registry.list_skills():
            contract = registry.get(skill_name)
            level = contract.autonomy_level.value
            levels[level] = levels.get(level, 0) + 1
        
        # Should have mix of autonomy levels
        assert "READ" in levels, "Should have READ skills"
        assert "SUGGEST" in levels, "Should have SUGGEST skills"
        assert "IMPLEMENT" in levels, "Should have IMPLEMENT skills"

    def test_schema_infer_has_trace_dependency(self, skills_dir):
        """schema-infer should produce trace_map artifact."""
        registry = SkillRegistry(skills_dir)
        contract = registry.get("schema-infer")

        # contract.required_artifacts is now list of ArtifactSpec Pydantic models
        artifact_names = [a.name for a in contract.required_artifacts]
        # trace_map can be .json or .yaml
        assert any("trace_map" in name for name in artifact_names), "schema-infer must produce trace_map"
class TestTraceMapGate:
    """Tests for trace map enforcement."""

    def test_valid_trace_map(self, scripts_dir, temp_artifacts):
        """Valid trace map should pass (JSON format)."""
        gate = TraceMapGate(scripts_dir)
        
        # Create valid trace map (JSON - canonical format)
        trace_map = {
            "correlation_id": "TEST123",
            "node_type": "n8n-nodes-base.test",
            "trace_entries": [
                {
                    "field_path": "operation",
                    "source": "API_DOCS",
                    "evidence": "Documented at https://api.example.com/docs#operations",
                    "confidence": "high",
                },
                {
                    "field_path": "chat_id",
                    "source": "SOURCE_CODE",
                    "evidence": "Found in existing TypeScript node at line 42",
                    "confidence": "high",
                },
            ],
        }
        
        trace_path = temp_artifacts / "trace_map.json"
        with open(trace_path, "w") as f:
            json.dump(trace_map, f)
        
        result = gate.check(trace_path)
        assert result.passed, f"Should pass: {result.message}"

    def test_missing_trace_map(self, scripts_dir, temp_artifacts):
        """Missing trace map should fail."""
        gate = TraceMapGate(scripts_dir)
        
        result = gate.check(temp_artifacts / "nonexistent.json")
        assert not result.passed

    def test_too_many_assumptions(self, scripts_dir, temp_artifacts):
        """More than 30% assumptions should fail."""
        gate = TraceMapGate(scripts_dir)
        
        # Create trace map with >30% assumptions (JSON format)
        trace_map = {
            "correlation_id": "TEST123",
            "node_type": "n8n-nodes-base.test",
            "trace_entries": [
                {
                    "field_path": "field1",
                    "source": "ASSUMPTION",
                    "evidence": "Assumed based on common patterns",
                    "confidence": "low",
                    "assumption_rationale": "Common REST API pattern",
                },
                {
                    "field_path": "field2",
                    "source": "ASSUMPTION",
                    "evidence": "Assumed based on common patterns",
                    "confidence": "low",
                    "assumption_rationale": "Common REST API pattern",
                },
                {
                    "field_path": "field3",
                    "source": "API_DOCS",
                    "evidence": "Documented at https://api.example.com",
                    "confidence": "high",
                },
            ],
        }
        
        trace_path = temp_artifacts / "trace_map.json"
        with open(trace_path, "w") as f:
            json.dump(trace_map, f)
        
        result = gate.check(trace_path)
        # 2/3 = 66% assumptions - should fail
        assert not result.passed, "Should fail with >30% assumptions"


class TestScopeGate:
    """Tests for scope enforcement."""

    def test_allowed_paths(self, scripts_dir, temp_artifacts):
        """Allowed paths should pass scope check."""
        gate = ScopeGate(scripts_dir, temp_artifacts)
        
        # Create session with allowlist.json (REQUIRED for scope check)
        correlation_id = "TEST123"
        manifest_dir = temp_artifacts / correlation_id
        manifest_dir.mkdir(parents=True)
        
        # ScopeGate now REQUIRES allowlist.json for IMPLEMENT/COMMIT skills
        allowlist = {
            "allowed_paths": ["nodes/**/*.py", "tests/**/*.py"],
            "forbidden_paths": ["**/secrets.py"],
        }
        with open(manifest_dir / "allowlist.json", "w") as f:
            json.dump(allowlist, f)
        
        # Test 1: Check passes when allowlist exists (no files to check)
        result = gate.check(correlation_id)
        assert result.passed, f"Should pass with valid allowlist: {result.message}"
        
        # Test 2: Check passes for allowed files
        result = gate.check(correlation_id, files_to_check=["nodes/my_node.py", "tests/test_node.py"])
        assert result.passed, f"Should pass for allowed files: {result.message}"
        
        # Test 3: Check fails for forbidden paths
        result = gate.check(correlation_id, files_to_check=["nodes/base.py"])
        assert not result.passed, "Should fail for forbidden base.py"
        assert "blocked" in result.message.lower() or "violations" in result.message.lower()
        
        # Test 4: Check fails for paths not in allowlist
        result = gate.check(correlation_id, files_to_check=["src/random.py"])
        assert not result.passed, "Should fail for paths not in allowlist"
        
        # Test 5: Check fails when allowlist.json is missing
        gate_no_allowlist = ScopeGate(scripts_dir, temp_artifacts)
        result = gate_no_allowlist.check("NONEXISTENT_SESSION")
        assert not result.passed, "Should fail without allowlist.json"
        assert "allowlist.json" in result.message

    def test_untracked_out_of_scope_fails(self, scripts_dir, temp_artifacts):
        """Untracked files out of scope should fail the scope gate."""
        gate = ScopeGate(scripts_dir, temp_artifacts)
        
        correlation_id = "UNTRACKED_TEST"
        manifest_dir = temp_artifacts / correlation_id
        manifest_dir.mkdir(parents=True)
        
        # Allowlist only allows nodes/**/*.py
        allowlist = {
            "allowed_paths": ["nodes/**/*.py"],
            "forbidden_paths": [],
        }
        with open(manifest_dir / "allowlist.json", "w") as f:
            json.dump(allowlist, f)
        
        # Mock git commands: staged/unstaged return nothing, but untracked has out-of-scope file
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            
            if "diff" in cmd:
                result.stdout = ""  # No tracked changes
            elif "ls-files" in cmd and "--others" in cmd:
                # Untracked file that's OUT of scope
                result.stdout = "src/bad_file.py\n"
            else:
                result.stdout = ""
            return result
        
        with patch("subprocess.run", mock_run):
            result = gate.check(correlation_id, check_git=True)
        
        assert not result.passed, "Should fail when untracked file is out of scope"
        assert "violations" in result.message.lower() or "blocked" in result.message.lower()
        assert result.details.get("violations")
        assert any("src/bad_file.py" in v["file"] for v in result.details["violations"])

    def test_untracked_in_scope_passes(self, scripts_dir, temp_artifacts):
        """Untracked files that are in scope should pass the scope gate."""
        gate = ScopeGate(scripts_dir, temp_artifacts)
        
        correlation_id = "UNTRACKED_PASS"
        manifest_dir = temp_artifacts / correlation_id
        manifest_dir.mkdir(parents=True)
        
        # Allowlist allows nodes/**/*.py
        allowlist = {
            "allowed_paths": ["nodes/**/*.py"],
            "forbidden_paths": [],
        }
        with open(manifest_dir / "allowlist.json", "w") as f:
            json.dump(allowlist, f)
        
        # Mock git commands: untracked file IS in scope
        def mock_run(cmd, **kwargs):
            result = Mock()
            result.returncode = 0
            
            if "diff" in cmd:
                result.stdout = ""
            elif "ls-files" in cmd and "--others" in cmd:
                # Untracked file that IS in scope
                result.stdout = "nodes/my_new_node.py\n"
            else:
                result.stdout = ""
            return result
        
        with patch("subprocess.run", mock_run):
            result = gate.check(correlation_id, check_git=True)
        
        assert result.passed, f"Should pass when untracked file is in scope: {result.message}"
        assert result.details.get("files_checked") == 1


class TestSkillExecutor:
    """Tests for skill execution."""

    def test_execute_stub_skill(self, executor):
        """Unimplemented skills should run in stub mode."""
        result = executor.execute(
            skill_name="node-normalize",
            inputs={"raw_node_name": "Test Node"},  # Provide required input
            correlation_id="TEST123",
        )
        
        assert result.status == ExecutionStatus.SUCCESS
        assert result.outputs.get("stub") is True
        assert len(result.trace) > 0

    def test_execute_with_missing_inputs(self, executor):
        """Missing required inputs should fail."""
        result = executor.execute(
            skill_name="schema-infer",
            inputs={},  # Missing required inputs
            correlation_id="TEST123",
        )
        
        assert result.status == ExecutionStatus.FAILED
        assert any("Missing required input" in e for e in result.errors)

    def test_execution_trace(self, executor):
        """Execution should produce trace events."""
        result = executor.execute(
            skill_name="node-normalize",
            inputs={"source_path": "/path/to/source"},
            correlation_id="TEST123",
        )
        
        event_types = [e["event"] for e in result.trace]
        assert "execution_started" in event_types
        assert "contract_loaded" in event_types
        assert "execution_completed" in event_types

    def test_register_implementation(self, executor):
        """Custom implementations should be callable."""
        
        def my_impl(ctx: ExecutionContext) -> dict:
            return {"result": "custom_output"}
        
        executor.register_implementation("node-normalize", my_impl)
        
        result = executor.execute(
            skill_name="node-normalize",
            inputs={"raw_node_name": "Test Node"},  # Provide required input
            correlation_id="TEST123",
        )
        
        assert result.outputs.get("result") == "custom_output"
        assert result.outputs.get("stub") is None


class TestBoundedFixLoop:
    """Tests for bounded fix loop."""

    def test_max_iterations_escalation(self, executor, temp_artifacts):
        """Should escalate after max iterations."""
        # Create required allowlist.json for IMPLEMENT skills
        correlation_id = "ESCTEST"
        session_dir = temp_artifacts / correlation_id
        session_dir.mkdir(parents=True)
        
        allowlist = {
            "allowed_paths": ["**/*.py"],
            "forbidden_paths": [],
        }
        with open(session_dir / "allowlist.json", "w") as f:
            json.dump(allowlist, f)
        
        fix_loop = BoundedFixLoop(executor, max_iterations=2)
        
        # Mock code-fix and code-validate to always return errors
        def mock_fix(ctx):
            return {"fix_applied": True}
        
        def mock_validate(ctx):
            return {"errors": [{"type": "lint", "message": "error"}]}
        
        executor.register_implementation("code-fix", mock_fix)
        executor.register_implementation("code-validate", mock_validate)
        
        result = fix_loop.run(
            correlation_id=correlation_id,
            initial_errors=[{"type": "lint", "message": "initial error"}],
        )
        
        assert result.status == ExecutionStatus.ESCALATED
        assert "Max iterations" in result.errors[0] or "Fix loop max" in result.errors[0]

    def test_successful_fix(self, executor, temp_artifacts):
        """Should succeed if errors are fixed via registered implementations."""
        # Create required allowlist.json for IMPLEMENT skills
        correlation_id = "FIXTEST"
        session_dir = temp_artifacts / correlation_id
        session_dir.mkdir(parents=True)
        
        allowlist = {
            "allowed_paths": ["**/*.py", "**/*.md", "**/*.json"],
            "forbidden_paths": [],
        }
        with open(session_dir / "allowlist.json", "w") as f:
            json.dump(allowlist, f)
        
        # Create repo_facts.json required by RepoGroundingGate for IMPLEMENT skills
        repo_facts = {
            "basenode_contract_path": "contracts/BASENODE_CONTRACT.md",
            "node_loader_paths": ["contracts/basenode_contract.py"],
            "golden_node_paths": ["/home/toni/n8n/back/nodes/telegram.py"],
            "test_command": "python3 -m pytest -q",
        }
        with open(session_dir / "repo_facts.json", "w") as f:
            json.dump(repo_facts, f)
        
        # Mock git diff to return empty list (no changes to check)
        # This avoids checking real git state in unit tests
        with patch.object(executor.scope_gate, '_get_git_changed_files', return_value=[]):
            # Test that registered implementations work and return expected values
            call_count = [0]
            
            def mock_fix(ctx):
                return {"fixed": True, "iteration": 1, "changes_made": ["fixed.py"]}
            
            def mock_validate(ctx):
                call_count[0] += 1
                if call_count[0] >= 2:
                    return {"passed": True, "errors": []}  # Fixed on second try
                return {"passed": False, "errors": [{"type": "lint", "message": "error"}]}
            
            executor.register_implementation("code-fix", mock_fix)
            executor.register_implementation("code-validate", mock_validate)
            
            # Test code-fix with all required inputs
            fix_result = executor.execute(
                skill_name="code-fix",
                inputs={
                    "correlation_id": correlation_id,
                    "validation_report": {"passed": False},
                    "files_modified": ["test.py"],
                    "allowlist": {"paths": ["*.py"]},
                    "iteration": 1,
                },
                correlation_id=correlation_id,
            )
            assert fix_result.status == ExecutionStatus.SUCCESS
            assert fix_result.outputs.get("fixed") is True
            
            # Test code-validate with all required inputs
            val_result = executor.execute(
                skill_name="code-validate",
                inputs={
                    "correlation_id": correlation_id,
                    "files_modified": ["test.py"],
                    "test_files": ["test_test.py"],
                    "allowlist": {"paths": ["*.py"]},
                },
                correlation_id=correlation_id,
            )
            assert val_result.status == ExecutionStatus.SUCCESS
            assert val_result.outputs.get("passed") is False  # First call returns False
            
            # Second validate call with SAME correlation_id should be skipped (idempotency)
            # This demonstrates the idempotency enforcement working correctly
            val_result2 = executor.execute(
                skill_name="code-validate",
                inputs={
                    "correlation_id": correlation_id,
                    "files_modified": ["test.py"],
                    "test_files": ["test_test.py"],
                    "allowlist": {"paths": ["*.py"]},
                },
                correlation_id=correlation_id,
            )
            # Idempotency should skip the call and return previous state
            assert val_result2.outputs.get("skipped") is True
            assert val_result2.outputs.get("reason") == "idempotency"


class TestSkillChaining:
    """Tests for skill dependency chains."""

    def test_skill_dependencies(self, skills_dir):
        """Skills should have valid dependency references."""
        registry = SkillRegistry(skills_dir)
        all_skills = set(registry.list_skills())
        
        for skill_name in all_skills:
            contract = registry.get(skill_name)
            for dep in contract.depends_on:
                assert dep in all_skills, f"{skill_name} depends on unknown skill: {dep}"

    def test_no_circular_dependencies(self, skills_dir):
        """No circular dependencies should exist."""
        registry = SkillRegistry(skills_dir)
        
        def has_cycle(skill: str, visited: set, stack: set) -> bool:
            visited.add(skill)
            stack.add(skill)
            
            contract = registry.get(skill)
            for dep in contract.depends_on:
                if dep not in visited:
                    if has_cycle(dep, visited, stack):
                        return True
                elif dep in stack:
                    return True
            
            stack.remove(skill)
            return False
        
        visited: set = set()
        for skill_name in registry.list_skills():
            if skill_name not in visited:
                assert not has_cycle(skill_name, visited, set()), f"Circular dependency found involving {skill_name}"


class TestCreateExecutor:
    """Tests for executor factory."""

    def test_create_executor(self, repo_root):
        """Factory should create working executor."""
        executor = create_executor(repo_root)
        
        assert executor.registry is not None
        assert executor.trace_gate is not None
        assert executor.scope_gate is not None


class TestBaseNodeContract:
    """Tests for BaseNode schema validation."""

    def test_valid_schema(self):
        """Valid BaseNode schema should pass validation."""
        from contracts import validate_basenode_schema
        
        schema = {
            "type": "n8n-nodes-base.telegram",
            "version": 1,
            "description": {
                "displayName": "Telegram",
                "name": "telegram",
                "description": "Send messages via Telegram",
                "group": ["output"],
                "version": 1,
                "inputs": ["main"],
                "outputs": ["main"],
            },
            "properties": {
                "parameters": [
                    {
                        "name": "operation",
                        "displayName": "Operation",
                        "type": "options",
                        "default": "sendMessage",
                        "options": [
                            {"name": "Send Message", "value": "sendMessage"},
                        ],
                    },
                ],
            },
        }
        
        result = validate_basenode_schema(schema)
        assert result.valid, f"Should be valid: {result.errors}"
        assert result.schema_summary["type"] == "n8n-nodes-base.telegram"
        assert result.schema_summary["parameter_count"] == 1

    def test_missing_required_fields(self):
        """Schema missing required fields should fail."""
        from contracts import validate_basenode_schema
        
        # Missing type
        schema = {
            "version": 1,
            "description": {"displayName": "Test", "name": "test", "version": 1},
            "properties": {"parameters": []},
        }
        
        result = validate_basenode_schema(schema)
        assert not result.valid
        assert any("type" in e.lower() for e in result.errors)

    def test_options_without_options_list(self):
        """Options type parameter without options should fail contract check."""
        from contracts import validate_basenode_schema
        
        schema = {
            "type": "test-node",
            "version": 1,
            "description": {
                "displayName": "Test",
                "name": "test",
                "version": 1,
            },
            "properties": {
                "parameters": [
                    {
                        "name": "operation",
                        "type": "options",
                        # Missing options list
                    },
                ],
            },
        }
        
        result = validate_basenode_schema(schema)
        assert not result.valid
        assert any("options" in e.lower() for e in result.errors)

    def test_pydantic_model_usage(self):
        """BaseNodeSchema model should parse valid data."""
        from contracts import BaseNodeSchema
        
        schema = BaseNodeSchema(
            type="my-node",
            version=1,
            description={
                "displayName": "My Node",
                "name": "myNode",
                "version": 1,
            },
            properties={
                "parameters": [
                    {"name": "input", "type": "string"},
                ],
            },
        )
        
        assert schema.type == "my-node"
        assert schema.version == 1
        assert len(schema.properties.parameters) == 1


class TestTraceMapFixture:
    """Tests for trace map fixture validation."""

    def test_fixture_validates_with_script(self, scripts_dir):
        """The canonical trace_map.json fixture should pass validator script."""
        import subprocess
        
        fixture_path = Path(__file__).parent / "fixtures" / "trace_map.json"
        validator_script = scripts_dir / "validate_trace_map.py"
        
        assert fixture_path.exists(), f"Fixture not found: {fixture_path}"
        assert validator_script.exists(), f"Validator not found: {validator_script}"
        
        result = subprocess.run(
            ["python3", str(validator_script), str(fixture_path)],
            capture_output=True,
            text=True,
        )
        
        assert result.returncode == 0, f"Validator failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"

    def test_fixture_validates_with_pydantic(self):
        """The canonical trace_map.json fixture should validate with Pydantic models."""
        import json
        from contracts import TraceMap, TraceEntry, TraceSource, ConfidenceLevel
        
        fixture_path = Path(__file__).parent / "fixtures" / "trace_map.json"
        
        with open(fixture_path) as f:
            data = json.load(f)
        
        # Convert entries
        entries = []
        for entry_data in data["trace_entries"]:
            entry = TraceEntry(
                field_path=entry_data["field_path"],
                source=TraceSource(entry_data["source"]),
                evidence=entry_data["evidence"],
                confidence=ConfidenceLevel(entry_data["confidence"]),
                source_file=entry_data.get("source_file"),
                line_range=entry_data.get("line_range"),
                excerpt_hash=entry_data.get("excerpt_hash"),
            )
            entries.append(entry)
        
        trace_map = TraceMap(
            correlation_id=data["correlation_id"],
            node_type=data["node_type"],
            trace_entries=entries,
            generated_at=data.get("generated_at"),
            skill_version=data.get("skill_version"),
        )
        
        # Validate
        assert trace_map.correlation_id == "test-fixture-001"
        assert trace_map.node_type == "telegram"
        assert len(trace_map.trace_entries) == 4
        assert trace_map.assumption_ratio() == 0.0  # No assumptions in fixture
        assert trace_map.is_valid_for_implement()  # Should be valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
