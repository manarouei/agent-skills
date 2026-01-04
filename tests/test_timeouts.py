import time
from pathlib import Path

import pytest

from runtime.executor import (
    SkillExecutor,
    SkillRegistry,
    ExecutionResult,
    ExecutionStatus,
    DeadlineExceeded,
)


@pytest.fixture
def test_skill_dir(tmp_path):
    """Create a temporary test skill with short timeout."""
    skill_dir = tmp_path / "skills" / "test-timeout"
    skill_dir.mkdir(parents=True)
    
    skill_md = """---
name: test-timeout
version: "1.0.0"
description: Test skill for cooperative timeout testing
autonomy_level: READ
side_effects: []
timeout_seconds: 10
input_schema:
  type: object
  properties: {}
  required: []
output_schema:
  type: object
  properties:
    result:
      type: string
  required: []
required_artifacts: []
failure_modes: [timeout]
depends_on: []
sync_celery:
  requires_sync_execution: true
  forbids_async_dependencies: true
---

# test-timeout

A test skill for cooperative timeout testing. Timeout is 10 seconds.
"""
    (skill_dir / "SKILL.md").write_text(skill_md)
    return tmp_path


def test_cooperative_deadline_prevents_side_effects(test_skill_dir):
    """A skill that cooperatively checks deadline should be interrupted and must not
    produce side-effects after the deadline."""
    repo_root = Path(__file__).parent.parent
    artifacts_dir = test_skill_dir / "artifacts"
    artifacts_dir.mkdir()
    scripts_dir = repo_root / "scripts"

    executor = SkillExecutor(
        skills_dir=test_skill_dir / "skills",
        scripts_dir=scripts_dir,
        artifacts_dir=artifacts_dir,
        max_steps=10,
        repo_root=repo_root,
    )

    marker_file = test_skill_dir / "marker.txt"

    # Define a skill implementation that loops, checks deadline, and would write a marker
    def long_running_skill(ctx):
        # Simulate work in small chunks, checking deadline cooperatively
        for i in range(1000):
            # Periodically check cooperative deadline
            ctx.check_deadline()
            time.sleep(0.01)
        # If completed, write marker (should not happen if deadline enforced)
        marker_file.write_text("done")
        return {"result": "ok"}

    # Use test-timeout skill (10 second timeout)
    executor.register_implementation("test-timeout", long_running_skill)

    # Execute with a short timeout
    result = executor.execute("test-timeout", {}, "CTX-TIMEOUT")

    # Should be TIMEOUT
    assert result.status == ExecutionStatus.TIMEOUT or result.status == ExecutionStatus.ESCALATED
    # Marker file should not exist
    assert not marker_file.exists()


def test_deadline_allows_completion_if_within_time(test_skill_dir):
    """A skill that completes quickly should succeed."""
    repo_root = Path(__file__).parent.parent
    artifacts_dir = test_skill_dir / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    scripts_dir = repo_root / "scripts"

    executor = SkillExecutor(
        skills_dir=test_skill_dir / "skills",
        scripts_dir=scripts_dir,
        artifacts_dir=artifacts_dir,
        max_steps=10,
        repo_root=repo_root,
    )

    def quick_skill(ctx):
        ctx.check_deadline()
        return {"result": "ok"}

    # Use test-timeout skill (10 second timeout)
    executor.register_implementation("test-timeout", quick_skill)

    result = executor.execute("test-timeout", {}, "CTX-OK")
    assert result.status == ExecutionStatus.SUCCESS