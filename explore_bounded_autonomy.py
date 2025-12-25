#!/usr/bin/env python3
"""
Explore Bounded Autonomy Agent Internals

This script demonstrates how the bounded autonomy system works with different inputs
and scenarios, showcasing the agent's decision-making process.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agentic_system.skills.context_gate import ContextGateSkill, ContextGateInput
from agentic_system.skills.code_review import CodeReviewSkill, CodeReviewInput
from agentic_system.agents.bounded_autonomy import BoundedAutonomyAgent, BoundedAutonomyInput
from agentic_system.runtime import ExecutionContext


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


def explore_context_gate():
    """Explore ContextGateSkill with different scenarios."""
    print_section("EXPLORING CONTEXT GATE SKILL")
    
    skill = ContextGateSkill()
    context = ExecutionContext(
        trace_id="explore-1",
        job_id="exploration",
        agent_id="explorer"
    )
    
    # Scenario 1: Task without any context
    print("\n📋 Scenario 1: Task with NO context (will ask questions)")
    print("-" * 80)
    input1 = ContextGateInput(
        task_description="Add Redis caching to the summarize skill",
        visible_files=[],
        available_context={},
        max_questions=5
    )
    result1 = skill._execute(input1, context)
    print(f"Status: {result1.status}")
    print(f"Can Proceed: {result1.can_proceed}")
    print(f"Questions ({len(result1.questions)}):")
    for i, q in enumerate(result1.questions, 1):
        print(f"  {i}. [{q.priority}] {q.question}")
        print(f"     Reason: {q.reason}")
    print(f"Missing Context: {result1.missing_context}")
    
    # Scenario 2: Task with file allowlist
    print("\n\n📋 Scenario 2: Task WITH file allowlist (should proceed)")
    print("-" * 80)
    input2 = ContextGateInput(
        task_description="Add Redis caching to the summarize skill",
        visible_files=["src/agentic_system/skills/summarize.py"],
        available_context={
            "file_allowlist": ["src/agentic_system/skills/summarize.py"]
        },
        max_questions=5
    )
    result2 = skill._execute(input2, context)
    print(f"Status: {result2.status}")
    print(f"Can Proceed: {result2.can_proceed}")
    print(f"Questions: {len(result2.questions)}")
    print(f"Assumptions ({len(result2.assumptions)}):")
    for i, assumption in enumerate(result2.assumptions, 1):
        print(f"  {i}. {assumption}")
    
    # Scenario 3: Security-related task (critical questions)
    print("\n\n📋 Scenario 3: Security task (will ask critical questions)")
    print("-" * 80)
    input3 = ContextGateInput(
        task_description="Add authentication to the API endpoints",
        visible_files=[],
        available_context={},
        max_questions=5
    )
    result3 = skill._execute(input3, context)
    print(f"Status: {result3.status}")
    print(f"Can Proceed: {result3.can_proceed}")
    print(f"Questions ({len(result3.questions)}):")
    for i, q in enumerate(result3.questions, 1):
        print(f"  {i}. [{q.priority}] {q.question}")
    print(f"Missing Context: {result3.missing_context}")
    
    # Scenario 4: Database migration task
    print("\n\n📋 Scenario 4: Database migration task (will ask critical questions)")
    print("-" * 80)
    input4 = ContextGateInput(
        task_description="Add a new user_preferences table to the database",
        visible_files=[],
        available_context={},
        max_questions=5
    )
    result4 = skill._execute(input4, context)
    print(f"Status: {result4.status}")
    print(f"Can Proceed: {result4.can_proceed}")
    print(f"Questions ({len(result4.questions)}):")
    for i, q in enumerate(result4.questions, 1):
        print(f"  {i}. [{q.priority}] {q.question}")


def explore_code_review():
    """Explore CodeReviewSkill with different scenarios."""
    print_section("EXPLORING CODE REVIEW SKILL")
    
    skill = CodeReviewSkill()
    context = ExecutionContext(
        trace_id="explore-2",
        job_id="exploration",
        agent_id="explorer"
    )
    
    # Scenario 1: Code change without tests
    print("\n📋 Scenario 1: Code change WITHOUT tests (P0 violation)")
    print("-" * 80)
    input1 = CodeReviewInput(
        modified_files=["src/agentic_system/skills/new_feature.py"],
        file_diffs={
            "src/agentic_system/skills/new_feature.py": """
+def new_feature():
+    '''Add a new feature.'''
+    return "feature"
"""
        },
        planned_files=None,
        pr_description="Add new feature",
        check_imports=True
    )
    result1 = skill._execute(input1, context)
    print(f"Compliance Status: {result1.compliance_status}")
    print(f"P0 Violations: {len(result1.p0_violations)}")
    for v in result1.p0_violations:
        print(f"  - [{v.rule_id}] {v.message}")
    print(f"Recommendations:")
    for r in result1.recommendations:
        print(f"  - {r}")
    
    # Scenario 2: Code change WITH tests
    print("\n\n📋 Scenario 2: Code change WITH tests (compliant)")
    print("-" * 80)
    input2 = CodeReviewInput(
        modified_files=[
            "src/agentic_system/skills/new_feature.py",
            "tests/unit/test_new_feature.py"
        ],
        file_diffs={
            "src/agentic_system/skills/new_feature.py": """
+def new_feature():
+    '''Add a new feature.'''
+    return "feature"
""",
            "tests/unit/test_new_feature.py": """
+def test_new_feature():
+    assert new_feature() == "feature"
"""
        },
        planned_files=None,
        pr_description="Add new feature with tests",
        check_imports=True
    )
    result2 = skill._execute(input2, context)
    print(f"Compliance Status: {result2.compliance_status}")
    print(f"P0 Violations: {len(result2.p0_violations)}")
    print(f"P1 Violations: {len(result2.p1_violations)}")
    print(f"P2 Suggestions: {len(result2.p2_suggestions)}")
    if result2.compliance_status == "compliant":
        print("✓ All P0/P1/P2 checks passed!")
    else:
        print(f"Recommendations:")
        for r in result2.recommendations[:3]:
            print(f"  - {r}")
    
    # Scenario 3: Breaking change detected
    print("\n\n📋 Scenario 3: Breaking change detected (P1 violation)")
    print("-" * 80)
    input3 = CodeReviewInput(
        modified_files=["src/agentic_system/skills/existing.py"],
        file_diffs={
            "src/agentic_system/skills/existing.py": """
-def old_method(param1, param2):
+def old_method(param1):  # BREAKING: removed param2
     '''Old method.'''
-    return param1 + param2
+    return param1
"""
        },
        planned_files=None,
        pr_description="Refactor old_method",
        check_imports=True
    )
    result3 = skill._execute(input3, context)
    print(f"Compliance Status: {result3.compliance_status}")
    print(f"P0 Violations: {len(result3.p0_violations)}")
    print(f"P1 Violations: {len(result3.p1_violations)}")
    for v in result3.p1_violations:
        print(f"  - [{v.rule_id}] {v.message}")
    
    # Scenario 4: Potential hallucination (fake API call)
    print("\n\n📋 Scenario 4: Potential hallucination detected")
    print("-" * 80)
    input4 = CodeReviewInput(
        modified_files=["src/agentic_system/skills/llm_caller.py"],
        file_diffs={
            "src/agentic_system/skills/llm_caller.py": """
+import anthropic
+
+def call_llm_directly():
+    client = anthropic.Anthropic(api_key="sk-xxx")
+    response = client.messages.create(
+        model="claude-3",
+        messages=[{"role": "user", "content": "test"}]
+    )
+    return response
"""
        },
        planned_files=None,
        pr_description="Add direct LLM call",
        check_imports=True
    )
    result4 = skill._execute(input4, context)
    print(f"Compliance Status: {result4.compliance_status}")
    print(f"P1 Violations: {len(result4.p1_violations)}")
    for v in result4.p1_violations:
        print(f"  - [{v.rule_id}] {v.message}")


def explore_bounded_autonomy_agent():
    """Explore BoundedAutonomyAgent in different modes."""
    print_section("EXPLORING BOUNDED AUTONOMY AGENT")
    
    from agentic_system.runtime.registry import get_skill_registry
    
    # Register skills
    registry = get_skill_registry()
    registry.register(ContextGateSkill())
    registry.register(CodeReviewSkill())
    
    agent = BoundedAutonomyAgent()
    
    # Scenario 1: Plan mode
    print("\n📋 Scenario 1: PLAN mode (context gating)")
    print("-" * 80)
    context1 = ExecutionContext(
        trace_id="explore-agent-1",
        job_id="exploration",
        agent_id="bounded_autonomy"
    )
    input1 = BoundedAutonomyInput(
        mode="plan",
        task_description="Add monitoring to all skills",
        files=["src/agentic_system/skills/"],
        available_context={
            "file_allowlist": ["src/agentic_system/skills/*.py"]
        }
    )
    result1 = agent._run(input1, context1)
    print(f"Mode: {result1['mode']}")
    print(f"Status: {result1['status']}")
    print(f"Summary: {result1['summary']}")
    print(f"Next Steps:")
    for step in result1['next_steps'][:3]:
        print(f"  - {step}")
    
    # Scenario 2: Review mode
    print("\n\n📋 Scenario 2: REVIEW mode (code compliance)")
    print("-" * 80)
    context2 = ExecutionContext(
        trace_id="explore-agent-2",
        job_id="exploration",
        agent_id="bounded_autonomy"
    )
    input2 = BoundedAutonomyInput(
        mode="review",
        task_description="Review changes",
        modified_files=["src/test.py"],
        file_diffs={"src/test.py": "+def test(): pass"}
    )
    result2 = agent._run(input2, context2)
    print(f"Mode: {result2['mode']}")
    print(f"Status: {result2['status']}")
    print(f"Summary: {result2['summary']}")
    print(f"Next Steps:")
    for step in result2['next_steps'][:5]:
        print(f"  - {step}")
    
    # Scenario 3: Validate mode
    print("\n\n📋 Scenario 3: VALIDATE mode (both plan + review)")
    print("-" * 80)
    context3 = ExecutionContext(
        trace_id="explore-agent-3",
        job_id="exploration",
        agent_id="bounded_autonomy"
    )
    input3 = BoundedAutonomyInput(
        mode="validate",
        task_description="Add feature X",
        files=["src/feature.py"],
        modified_files=["src/feature.py", "tests/test_feature.py"],
        file_diffs={
            "src/feature.py": "+def feature_x(): return 'x'",
            "tests/test_feature.py": "+def test_feature_x(): assert feature_x() == 'x'"
        },
        available_context={
            "file_allowlist": ["src/feature.py"]
        }
    )
    result3 = agent._run(input3, context3)
    print(f"Mode: {result3['mode']}")
    print(f"Status: {result3['status']}")
    print(f"Summary: {result3['summary'][:200]}...")
    print(f"Has Plan Result: {'plan' in result3['result']}")
    print(f"Has Review Result: {'review' in result3['result']}")


def main():
    """Run all explorations."""
    print("\n" + "🔍" * 40)
    print("BOUNDED AUTONOMY SYSTEM - INTERNAL WORKINGS EXPLORATION")
    print("🔍" * 40)
    
    try:
        explore_context_gate()
        explore_code_review()
        explore_bounded_autonomy_agent()
        
        print("\n" + "=" * 80)
        print("✅ EXPLORATION COMPLETE!")
        print("=" * 80)
        print("\nKey Takeaways:")
        print("1. Context Gate enforces P0-1: Always ask for required context")
        print("2. Context Gate adapts questions based on task type (cache, security, database)")
        print("3. Code Review enforces P0-5: All code changes require tests")
        print("4. Code Review detects breaking changes, direct API calls, and hallucinations")
        print("5. Bounded Autonomy Agent orchestrates both skills in plan/review/validate modes")
        print("6. System provides clear guidance and next steps at each stage")
        print("\n")
        
    except Exception as e:
        print(f"\n❌ Error during exploration: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
