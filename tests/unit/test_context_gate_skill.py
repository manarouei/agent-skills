"""Tests for ContextGateSkill."""
import pytest

from agentic_system.runtime import ExecutionContext
from agentic_system.skills.context_gate import ContextGateSkill


@pytest.fixture
def context_gate_skill():
    """Create a ContextGateSkill instance."""
    return ContextGateSkill()


def test_context_gate_ready_status(context_gate_skill, execution_context):
    """Test that context gate returns ready when context is sufficient."""
    result = context_gate_skill.execute(
        input_data={
            "task_description": "Update documentation",
            "visible_files": ["README.md"],
            "available_context": {"file_allowlist": ["README.md"]},
            "max_questions": 5
        },
        context=execution_context
    )
    
    assert result["status"] == "ready"
    assert result["can_proceed"] is True
    assert len(result["questions"]) == 0


def test_context_gate_needs_clarification(context_gate_skill, execution_context):
    """Test that context gate asks questions when context is missing."""
    result = context_gate_skill.execute(
        input_data={
            "task_description": "Modify the summarize skill to add caching",
            "visible_files": [],
            "available_context": {},
            "max_questions": 5
        },
        context=execution_context
    )
    
    assert result["status"] in ["needs_clarification", "blocked"]
    assert result["can_proceed"] is False
    assert len(result["questions"]) > 0
    
    # Should ask about file allowlist
    questions_text = " ".join(q["question"].lower() for q in result["questions"])
    assert "file" in questions_text or "modify" in questions_text


def test_context_gate_database_task(context_gate_skill, execution_context):
    """Test that database tasks trigger schema questions."""
    result = context_gate_skill.execute(
        input_data={
            "task_description": "Add new database migration for user table",
            "visible_files": [],
            "available_context": {},
            "max_questions": 5
        },
        context=execution_context
    )
    
    # Should ask about database schema
    questions = result["questions"]
    assert any("database" in q["question"].lower() or "schema" in q["question"].lower() 
               for q in questions)
    
    # Should be high/critical priority
    db_questions = [q for q in questions 
                    if "database" in q["question"].lower() or "schema" in q["question"].lower()]
    assert any(q["priority"] in ["critical", "high"] for q in db_questions)


def test_context_gate_max_questions_limit(context_gate_skill, execution_context):
    """Test that context gate respects max questions limit."""
    result = context_gate_skill.execute(
        input_data={
            "task_description": "Complex task requiring database, cache, API, and security changes",
            "visible_files": [],
            "available_context": {},
            "max_questions": 3
        },
        context=execution_context
    )
    
    # Should not exceed max_questions
    assert len(result["questions"]) <= 3


def test_context_gate_makes_assumptions(context_gate_skill, execution_context):
    """Test that context gate makes explicit assumptions."""
    result = context_gate_skill.execute(
        input_data={
            "task_description": "Add logging to existing function",
            "visible_files": ["src/agentic_system/skills/summarize.py"],
            "available_context": {"file_allowlist": ["src/agentic_system/skills/summarize.py"]},
            "max_questions": 5
        },
        context=execution_context
    )
    
    # Should make assumptions
    assumptions = result["assumptions"]
    assert len(assumptions) > 0
    
    # Should assume no breaking changes allowed
    assumptions_text = " ".join(assumptions).lower()
    assert "breaking" in assumptions_text or "test" in assumptions_text
