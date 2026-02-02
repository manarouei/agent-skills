#!/usr/bin/env python3
"""
Tests for NoTargetRepoMutationGuard

Validates the authoritative git-based enforcement that artifact-scope skills
cannot mutate TARGET_REPO_ROOT (/home/toni/n8n/back or any external repo).

This guard is AUTHORITATIVE - it uses git status rather than output inspection
to detect unauthorized changes.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from runtime.executor import (
    NoTargetRepoMutationGuard,
    GateResult,
)
from contracts import FSScope


class TestNoTargetRepoMutationGuard:
    """Tests for NoTargetRepoMutationGuard."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            # Initialize git repo
            subprocess.run(
                ["git", "init"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            # Configure git user for commits
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            # Create initial file and commit
            (repo_path / "existing.ts").write_text("// existing file")
            subprocess.run(
                ["git", "add", "."],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial commit"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            yield repo_path

    @pytest.fixture
    def guard(self, temp_git_repo):
        """Create guard instance with temp repo."""
        return NoTargetRepoMutationGuard(target_repo_root=temp_git_repo)

    def test_no_target_repo_root_always_passes(self):
        """Guard with no target_repo_root should always pass."""
        guard = NoTargetRepoMutationGuard(target_repo_root=None)
        
        # snapshot_before should return pass (disabled guard)
        result = guard.snapshot_before()
        assert result.passed is True
        assert "disabled" in result.message.lower() or "no target" in result.message.lower()
        
        # check_after should also pass
        result = guard.check_after("test-123")
        assert result.passed is True

    def test_clean_repo_passes(self, guard, temp_git_repo):
        """No changes to target repo should pass."""
        snapshot_result = guard.snapshot_before()
        assert snapshot_result.passed is True
        
        # No changes made
        result = guard.check_after("test-123")
        assert result.passed is True
        assert "no" in result.message.lower() and "mutation" in result.message.lower()

    def test_detects_new_file(self, guard, temp_git_repo):
        """Guard should detect new untracked files."""
        snapshot_result = guard.snapshot_before()
        assert snapshot_result.passed is True
        
        # Create a new file (simulating unauthorized mutation)
        (temp_git_repo / "unauthorized.ts").write_text("// bad file")
        
        result = guard.check_after("test-123")
        assert result.passed is False
        assert "unauthorized.ts" in str(result.details.get("modified_files", [])) or "mutation" in result.message.lower()

    def test_detects_modified_file(self, guard, temp_git_repo):
        """Guard should detect modifications to tracked files."""
        snapshot_result = guard.snapshot_before()
        assert snapshot_result.passed is True
        
        # Modify existing file
        (temp_git_repo / "existing.ts").write_text("// modified!")
        
        result = guard.check_after("test-123")
        assert result.passed is False
        assert "existing.ts" in str(result.details.get("modified_files", [])) or "mutation" in result.message.lower()

    def test_detects_deleted_file(self, guard, temp_git_repo):
        """Guard should detect file deletions."""
        snapshot_result = guard.snapshot_before()
        assert snapshot_result.passed is True
        
        # Delete existing file
        (temp_git_repo / "existing.ts").unlink()
        
        result = guard.check_after("test-123")
        assert result.passed is False
        assert "existing.ts" in str(result.details.get("modified_files", [])) or "mutation" in result.message.lower()

    def test_check_without_snapshot_fails(self, temp_git_repo):
        """Check without prior snapshot should fail (no baseline)."""
        guard = NoTargetRepoMutationGuard(target_repo_root=temp_git_repo)
        # Don't call snapshot_before
        
        result = guard.check_after("no-snapshot-123")
        assert result.passed is False
        assert "snapshot" in result.message.lower()

    def test_non_git_directory_fails_closed(self):
        """Guard on non-git directory should fail closed (safe default)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            guard = NoTargetRepoMutationGuard(target_repo_root=Path(tmpdir))
            
            # snapshot_before should fail (not a git repo)
            result = guard.snapshot_before()
            assert result.passed is False
            assert "not a git repo" in result.message.lower() or "git" in result.message.lower()

    def test_reset_clears_snapshot(self, guard, temp_git_repo):
        """Reset should clear the snapshot state."""
        guard.snapshot_before()
        assert guard._snapshot is not None
        
        guard.reset()
        assert guard._snapshot is None

    def test_snapshot_captures_existing_changes(self, temp_git_repo):
        """Snapshot should capture existing uncommitted changes."""
        # Create a change BEFORE taking snapshot
        (temp_git_repo / "pre_existing.ts").write_text("// pre-existing change")
        
        guard = NoTargetRepoMutationGuard(target_repo_root=temp_git_repo)
        snapshot_result = guard.snapshot_before()
        assert snapshot_result.passed is True
        
        # The pre-existing change should be in the snapshot
        assert "pre_existing.ts" in guard._snapshot
        
        # No NEW changes
        result = guard.check_after("test-123")
        assert result.passed is True


class TestNoTargetRepoMutationGuardIntegration:
    """Integration tests for the guard in executor context."""

    @pytest.fixture
    def temp_git_repo(self):
        """Create a temporary git repository for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir)
            subprocess.run(
                ["git", "init"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            (repo_path / "init.ts").write_text("// init")
            subprocess.run(
                ["git", "add", "."],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            subprocess.run(
                ["git", "commit", "-m", "Initial"],
                cwd=repo_path,
                capture_output=True,
                check=True,
            )
            yield repo_path

    def test_guard_exports_from_runtime(self):
        """NoTargetRepoMutationGuard should be exported from runtime."""
        from runtime import NoTargetRepoMutationGuard as ImportedGuard
        assert ImportedGuard is not None
        assert callable(ImportedGuard)

    def test_guard_result_has_changed_files(self, temp_git_repo):
        """Failed result should include list of changed files."""
        guard = NoTargetRepoMutationGuard(target_repo_root=temp_git_repo)
        snapshot_result = guard.snapshot_before()
        assert snapshot_result.passed is True
        
        # Create multiple files
        (temp_git_repo / "a.ts").write_text("// a")
        (temp_git_repo / "b.ts").write_text("// b")
        
        result = guard.check_after("test-123")
        assert result.passed is False
        # Result details should contain modified files
        assert result.details is not None
        modified = result.details.get("modified_files", [])
        assert "a.ts" in modified or "a.ts" in str(modified)
        assert "b.ts" in modified or "b.ts" in str(modified)

    def test_guard_with_executor_factory(self, temp_git_repo):
        """Guard should work when created via create_executor."""
        from runtime.executor import create_executor
        
        repo_root = Path(__file__).parent.parent
        
        with tempfile.TemporaryDirectory() as artifacts_dir:
            executor = create_executor(
                skills_dir=repo_root / "skills",
                scripts_dir=repo_root / "scripts",
                artifacts_dir=Path(artifacts_dir),
                target_repo_root=temp_git_repo,
                register_implementations=False,
            )
            
            # Executor should have the guard configured
            assert executor.target_repo_mutation_guard is not None
            assert executor.target_repo_mutation_guard.target_repo_root == temp_git_repo
