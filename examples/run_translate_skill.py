"""
Demo: How to run and use the Translate skill

This shows three ways to use your skill:
1. Direct execution via skill registry
2. Via CLI (if you build one)
3. Via agent orchestration
"""

from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry


def demo_direct_execution():
    """Method 1: Direct execution via skill registry."""
    print("=" * 70)
    print("METHOD 1: DIRECT SKILL EXECUTION")
    print("=" * 70)
    
    # Import and register skills
    from agentic_system.integrations.tasks import register_skills_and_agents
    register_skills_and_agents()
    
    # Get skill registry
    registry = get_skill_registry()
    
    # Create execution context
    context = ExecutionContext(
        trace_id="demo-trace-001",
        job_id="demo-job-001",
        agent_id="demo_agent",
    )
    
    # Execute the skill
    print("\n🔹 Example 1: Simple translation")
    result = registry.execute(
        name="translate",
        input_data={
            "text": "Hello, world!",
        },
        context=context,
    )
    
    print(f"Input:  Hello, world!")
    print(f"Output: {result['result']}")
    
    # Execute with dict input
    print("\n🔹 Example 2: Longer text")
    result = registry.execute(
        name="translate",
        input_data={
            "text": "The quick brown fox jumps over the lazy dog.",
        },
        context=context,
    )
    
    print(f"Input:  The quick brown fox jumps over the lazy dog.")
    print(f"Output: {result['result']}")
    
    print("\n✅ Direct execution completed!")


def demo_programmatic_usage():
    """Method 2: Programmatic usage with imports."""
    print("\n" + "=" * 70)
    print("METHOD 2: PROGRAMMATIC USAGE")
    print("=" * 70)
    
    from agentic_system.skills.translate import TranslateSkill, TranslateInput
    
    # Create skill instance
    skill = TranslateSkill()
    
    # Create context
    context = ExecutionContext(
        trace_id="demo-trace-002",
        job_id="demo-job-002",
        agent_id="demo_agent",
    )
    
    # Create input using Pydantic model
    input_data = TranslateInput(
        text="Python is an amazing programming language!"
    )
    
    # Execute
    print("\n🔹 Using Pydantic model input")
    result = skill.execute(input_data, context)
    
    print(f"Input:  {input_data.text}")
    print(f"Output: {result['result']}")
    
    print("\n✅ Programmatic usage completed!")


def demo_skill_composition():
    """Method 3: Compose skills (e.g., summarize then translate)."""
    print("\n" + "=" * 70)
    print("METHOD 3: SKILL COMPOSITION")
    print("=" * 70)
    
    from agentic_system.integrations.tasks import register_skills_and_agents
    register_skills_and_agents()
    
    registry = get_skill_registry()
    context = ExecutionContext(
        trace_id="demo-trace-003",
        job_id="demo-job-003",
        agent_id="demo_agent",
    )
    
    # Example: Process text through multiple skills
    print("\n🔹 Pipeline: Process → Translate")
    
    # First, use translate skill
    step1 = registry.execute(
        name="translate",
        input_data={"text": "Machine learning is transforming AI."},
        context=context,
    )
    
    print(f"Step 1 (Translate): {step1['result']}")
    
    # You could chain more skills here
    # step2 = registry.execute("another_skill", step1, context)
    
    print("\n✅ Skill composition completed!")


def demo_validation():
    """Method 4: Show input validation."""
    print("\n" + "=" * 70)
    print("METHOD 4: INPUT VALIDATION")
    print("=" * 70)
    
    from agentic_system.skills.translate import TranslateSkill
    
    skill = TranslateSkill()
    context = ExecutionContext(
        trace_id="demo-trace-004",
        job_id="demo-job-004",
        agent_id="demo_agent",
    )
    
    # Valid input
    print("\n🔹 Valid input:")
    try:
        result = skill.execute({"text": "Valid text"}, context)
        print(f"✅ Success: {result['result']}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Invalid input (missing required field)
    print("\n🔹 Invalid input (missing 'text' field):")
    try:
        result = skill.execute({}, context)
        print(f"✅ Success: {result['result']}")
    except Exception as e:
        print(f"❌ Expected error: {type(e).__name__}")
        print(f"   Pydantic validation caught the error!")
    
    print("\n✅ Validation demo completed!")


if __name__ == "__main__":
    print("\n")
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║                                                              ║")
    print("║           TRANSLATE SKILL - USAGE DEMONSTRATION              ║")
    print("║                                                              ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print("\n")
    
    # Run all demos
    demo_direct_execution()
    demo_programmatic_usage()
    demo_skill_composition()
    demo_validation()
    
    print("\n" + "=" * 70)
    print("🎉 ALL DEMOS COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    print("\nNow you know how to:")
    print("  1. ✅ Execute skills directly via registry")
    print("  2. ✅ Use skills programmatically with Pydantic models")
    print("  3. ✅ Compose multiple skills in a pipeline")
    print("  4. ✅ Leverage automatic input validation")
    print("\nNext steps:")
    print("  • Implement real translation logic in _execute()")
    print("  • Add more fields to Input/Output models")
    print("  • Write more comprehensive tests")
    print("  • Create a CLI command for translation")
    print("  • Build an agent that uses this skill")
    print("\n")
