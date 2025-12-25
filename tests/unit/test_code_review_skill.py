"""Tests for CodeReviewSkill."""
import pytest

from agentic_system.runtime import ExecutionContext
from agentic_system.skills.code_review import CodeReviewSkill


@pytest.fixture
def code_review_skill():
    """Create a CodeReviewSkill instance."""
    return CodeReviewSkill()


@pytest.fixture
def sample_diff():
    """Sample diff content."""
    return """
+from new_module import something
+
+class NewClass:
+    def __init__(self):
+        pass
"""


def test_code_review_detects_missing_tests(code_review_skill, execution_context, sample_diff):
    """Test that code review detects missing test files."""
    result = code_review_skill.execute(
        input_data={
            "modified_files": ["src/agentic_system/skills/new_skill.py"],
            "file_diffs": {"src/agentic_system/skills/new_skill.py": sample_diff},
            "check_imports": False
        },
        context=execution_context
    )
    
    assert result["compliance_status"] in ["warnings", "violations"]
    assert result["total_files_modified"] == 1
    
    # Should have P0 violation for missing tests
    p0_violations = result["p0_violations"]
    assert any("test" in v["message"].lower() for v in p0_violations)


def test_code_review_scope_control(code_review_skill, execution_context):
    """Test that code review detects scope violations."""
    result = code_review_skill.execute(
        input_data={
            "modified_files": ["src/file1.py", "src/file2.py", "src/file3.py"],
            "file_diffs": {
                "src/file1.py": "+# change",
                "src/file2.py": "+# change",
                "src/file3.py": "+# change"
            },
            "planned_files": ["src/file1.py", "src/file2.py"],
            "check_imports": False
        },
        context=execution_context
    )
    
    assert result["compliance_status"] == "violations"
    
    # Should have P0 violation for scope creep
    p0_violations = result["p0_violations"]
    assert any("scope" in v["message"].lower() or "unplanned" in v["message"].lower() 
               for v in p0_violations)


def test_code_review_compliant_changes(code_review_skill, execution_context):
    """Test that compliant changes pass review."""
    result = code_review_skill.execute(
        input_data={
            "modified_files": [
                "src/agentic_system/skills/test_skill.py",
                "tests/unit/test_test_skill_skill.py"
            ],
            "file_diffs": {
                "src/agentic_system/skills/test_skill.py": "+# simple change",
                "tests/unit/test_test_skill_skill.py": "+# test update"
            },
            "planned_files": [
                "src/agentic_system/skills/test_skill.py",
                "tests/unit/test_test_skill_skill.py"
            ],
            "pr_description": "Modified `TestSkill._execute()` in src/agentic_system/skills/test_skill.py",
            "check_imports": False
        },
        context=execution_context
    )
    
    # Should be compliant (has tests, scope correct, symbols cited)
    assert result["compliance_status"] in ["compliant", "warnings"]
    assert result["total_files_modified"] == 2


def test_code_review_detects_direct_llm_calls(code_review_skill, execution_context):
    """Test that code review detects direct LLM API usage."""
    diff_with_api_call = """
+import httpx
+response = httpx.post("https://api.anthropic.com/v1/messages", ...)
"""
    
    result = code_review_skill.execute(
        input_data={
            "modified_files": ["src/agentic_system/skills/bad_skill.py"],
            "file_diffs": {"src/agentic_system/skills/bad_skill.py": diff_with_api_call},
            "check_imports": False
        },
        context=execution_context
    )
    
    # Should have P1 violation for direct API usage
    p1_violations = result["p1_violations"]
    assert any("llm" in v["message"].lower() or "gateway" in v["message"].lower() 
               for v in p1_violations)
