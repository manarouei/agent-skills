"""Tests for Learning Loop - Golden Artifacts and Promotion Candidates."""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

from runtime.learning_loop import (
    GoldenArtifactPackage,
    PromotionCandidate,
    LearningLoopEmitter,
    compute_source_hash,
    categorize_error,
)


class TestGoldenArtifactPackage:
    """Tests for GoldenArtifactPackage dataclass."""
    
    def test_create_package(self):
        """Test creating a golden artifact package."""
        package = GoldenArtifactPackage(
            correlation_id="test-123",
            node_type="TestNode",
            skill_name="code-implement",
            created_at="2025-01-15T00:00:00Z",
            generated_code={"node.py": "def execute(): pass"},
            tests_passed=True,
            validation_passed=True,
        )
        
        assert package.correlation_id == "test-123"
        assert package.node_type == "TestNode"
        assert package.tests_passed is True
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        package = GoldenArtifactPackage(
            correlation_id="test-123",
            node_type="TestNode",
            skill_name="code-implement",
            created_at="2025-01-15T00:00:00Z",
            generated_code={"node.py": "def execute(): pass"},
        )
        
        data = package.to_dict()
        
        assert data["correlation_id"] == "test-123"
        assert data["generated_code"]["node.py"] == "def execute(): pass"
    
    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "correlation_id": "test-456",
            "node_type": "AnotherNode",
            "skill_name": "code-convert",
            "created_at": "2025-01-15T12:00:00Z",
            "generated_code": {"converted.py": "class Node: pass"},
            "tests_passed": True,
            "validation_passed": True,
            "fix_iterations": 2,
        }
        
        package = GoldenArtifactPackage.from_dict(data)
        
        assert package.correlation_id == "test-456"
        assert package.fix_iterations == 2


class TestPromotionCandidate:
    """Tests for PromotionCandidate dataclass."""
    
    def test_create_candidate(self):
        """Test creating a promotion candidate."""
        candidate = PromotionCandidate(
            correlation_id="test-789",
            created_at="2025-01-15T00:00:00Z",
            error_category="async_violation",
            error_message="Found async def in sync context",
            original_code="async def fetch(): pass",
            fixed_code="def fetch(): pass",
            fix_description="Removed async keyword",
        )
        
        assert candidate.error_category == "async_violation"
        assert "async" in candidate.original_code
        assert "async" not in candidate.fixed_code
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        candidate = PromotionCandidate(
            correlation_id="test-789",
            created_at="2025-01-15T00:00:00Z",
            error_category="missing_timeout",
            error_message="HTTP call without timeout",
            original_code="requests.get(url)",
            fixed_code="requests.get(url, timeout=30)",
            fix_description="Added timeout parameter",
            fix_iteration=2,
        )
        
        data = candidate.to_dict()
        
        assert data["error_category"] == "missing_timeout"
        assert data["fix_iteration"] == 2
    
    def test_from_dict(self):
        """Test deserialization from dictionary."""
        data = {
            "correlation_id": "test-abc",
            "created_at": "2025-01-15T00:00:00Z",
            "error_category": "type_error",
            "error_message": "Expected str, got int",
            "original_code": "x: str = 123",
            "fixed_code": "x: str = str(123)",
            "fix_description": "Added str conversion",
            "validation_passed": True,
        }
        
        candidate = PromotionCandidate.from_dict(data)
        
        assert candidate.error_category == "type_error"
        assert candidate.validation_passed is True


class TestLearningLoopEmitter:
    """Tests for LearningLoopEmitter."""
    
    def test_emit_golden_artifact(self, tmp_path):
        """Test emitting a golden artifact package."""
        emitter = LearningLoopEmitter(tmp_path)
        
        package = GoldenArtifactPackage(
            correlation_id="golden-test-001",
            node_type="ExampleNode",
            skill_name="code-implement",
            created_at="2025-01-15T00:00:00Z",
            generated_code={
                "node.py": "class ExampleNode:\n    pass",
                "utils/helpers.py": "def helper(): pass",
            },
            node_schema={"type": "object", "properties": {}},
            trace_map={"entries": []},
            tests_passed=True,
            validation_passed=True,
        )
        
        artifact_dir = emitter.emit_golden_artifact(package)
        
        # Verify directory structure
        assert artifact_dir.exists()
        assert (artifact_dir / "manifest.json").exists()
        assert (artifact_dir / "code" / "node.py").exists()
        assert (artifact_dir / "code" / "utils" / "helpers.py").exists()
        assert (artifact_dir / "schema.json").exists()
        assert (artifact_dir / "trace_map.json").exists()
        
        # Verify manifest content
        manifest = json.loads((artifact_dir / "manifest.json").read_text())
        assert manifest["correlation_id"] == "golden-test-001"
        assert manifest["tests_passed"] is True
    
    def test_emit_promotion_candidate(self, tmp_path):
        """Test emitting a promotion candidate."""
        emitter = LearningLoopEmitter(tmp_path)
        
        candidate = PromotionCandidate(
            correlation_id="promo-test-001",
            created_at="2025-01-15T00:00:00Z",
            error_category="async_violation",
            error_message="Found aiohttp import",
            original_code="import aiohttp",
            fixed_code="import requests",
            fix_description="Replaced async HTTP client with sync requests",
        )
        
        candidate_path = emitter.emit_promotion_candidate(candidate)
        
        # Verify file exists
        assert candidate_path.exists()
        assert candidate_path.parent.name == "promotion_candidates"
        
        # Verify content
        data = json.loads(candidate_path.read_text())
        assert data["error_category"] == "async_violation"
        assert data["correlation_id"] == "promo-test-001"
    
    def test_list_golden_artifacts(self, tmp_path):
        """Test listing golden artifacts."""
        emitter = LearningLoopEmitter(tmp_path)
        
        # Emit two packages
        for i in range(2):
            package = GoldenArtifactPackage(
                correlation_id=f"list-test-{i}",
                node_type="TestNode",
                skill_name="code-implement",
                created_at="2025-01-15T00:00:00Z",
                generated_code={"node.py": "pass"},
            )
            emitter.emit_golden_artifact(package)
        
        artifacts = emitter.list_golden_artifacts()
        assert len(artifacts) == 2
    
    def test_list_promotion_candidates(self, tmp_path):
        """Test listing promotion candidates."""
        emitter = LearningLoopEmitter(tmp_path)
        
        # Emit three candidates
        for i in range(3):
            candidate = PromotionCandidate(
                correlation_id=f"list-promo-{i}",
                created_at="2025-01-15T00:00:00Z",
                error_category="general_error",
                error_message=f"Error {i}",
                original_code="x",
                fixed_code="y",
                fix_description="Fix",
            )
            emitter.emit_promotion_candidate(candidate)
        
        candidates = emitter.list_promotion_candidates()
        assert len(candidates) == 3
    
    def test_load_golden_artifact(self, tmp_path):
        """Test loading a golden artifact by correlation ID."""
        emitter = LearningLoopEmitter(tmp_path)
        
        package = GoldenArtifactPackage(
            correlation_id="load-test-001",
            node_type="LoadTestNode",
            skill_name="code-convert",
            created_at="2025-01-15T00:00:00Z",
            generated_code={"node.py": "class LoadTest: pass"},
            fix_iterations=1,
        )
        emitter.emit_golden_artifact(package)
        
        loaded = emitter.load_golden_artifact("load-test-001")
        
        assert loaded is not None
        assert loaded.node_type == "LoadTestNode"
        assert loaded.fix_iterations == 1
    
    def test_load_nonexistent_artifact(self, tmp_path):
        """Test loading a nonexistent artifact returns None."""
        emitter = LearningLoopEmitter(tmp_path)
        
        loaded = emitter.load_golden_artifact("nonexistent")
        
        assert loaded is None


class TestCategorizeError:
    """Tests for error categorization."""
    
    def test_async_violation(self):
        assert categorize_error("Found async def in code") == "async_violation"
        assert categorize_error("await expression not allowed") == "async_violation"
        assert categorize_error("asyncio module imported") == "async_violation"
        assert categorize_error("aiohttp client used") == "async_violation"
    
    def test_missing_timeout(self):
        assert categorize_error("HTTP call without timeout") == "missing_timeout"
        assert categorize_error("Deadline exceeded") == "missing_timeout"
    
    def test_type_error(self):
        assert categorize_error("TypeError: expected str") == "type_error"
        assert categorize_error("Missing type annotation") == "type_error"
    
    def test_import_error(self):
        assert categorize_error("ImportError: no module named x") == "import_error"
        assert categorize_error("Package not found") == "import_error"
    
    def test_syntax_error(self):
        assert categorize_error("SyntaxError at line 10") == "syntax_error"
        assert categorize_error("Parse error") == "syntax_error"
        assert categorize_error("IndentationError") == "syntax_error"
    
    def test_general_error(self):
        assert categorize_error("Something went wrong") == "general_error"
        assert categorize_error("Unknown error") == "general_error"


class TestComputeSourceHash:
    """Tests for source hash computation."""
    
    def test_compute_hash(self, tmp_path):
        """Test computing hash of source files."""
        # Create test files
        file1 = tmp_path / "a.py"
        file2 = tmp_path / "b.py"
        file1.write_text("content 1")
        file2.write_text("content 2")
        
        hash1 = compute_source_hash([file1, file2])
        
        assert hash1.startswith("sha256:")
        assert len(hash1) == 71  # "sha256:" + 64 hex chars
    
    def test_hash_is_deterministic(self, tmp_path):
        """Test that hash is deterministic."""
        file1 = tmp_path / "x.py"
        file1.write_text("test content")
        
        hash1 = compute_source_hash([file1])
        hash2 = compute_source_hash([file1])
        
        assert hash1 == hash2
    
    def test_hash_changes_with_content(self, tmp_path):
        """Test that hash changes when content changes."""
        file1 = tmp_path / "y.py"
        file1.write_text("original")
        hash1 = compute_source_hash([file1])
        
        file1.write_text("modified")
        hash2 = compute_source_hash([file1])
        
        assert hash1 != hash2
    
    def test_hash_order_independent(self, tmp_path):
        """Test that file order doesn't affect hash."""
        file1 = tmp_path / "1.py"
        file2 = tmp_path / "2.py"
        file1.write_text("first")
        file2.write_text("second")
        
        # Files sorted internally, so order shouldn't matter
        hash1 = compute_source_hash([file1, file2])
        hash2 = compute_source_hash([file2, file1])
        
        assert hash1 == hash2
