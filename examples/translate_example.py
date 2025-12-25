"""
Example: Creating and using the Translate skill

This example demonstrates the full workflow:
1. Create a skill using make commands
2. Implement the logic
3. Test the skill
4. Use the skill in your code
"""

from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry


def main():
    """Demonstrate translate skill usage."""
    
    print("=" * 70)
    print("TRANSLATE SKILL EXAMPLE")
    print("=" * 70)
    
    # Get skill registry
    registry = get_skill_registry()
    
    # Create execution context
    context = ExecutionContext(
        trace_id="example-trace-001",
        job_id="example-job-001",
        agent_id="example_agent",
    )
    
    # Example 1: Translate to Spanish
    print("\n📝 Example 1: Translate to Spanish")
    print("-" * 70)
    
    result = registry.execute(
        skill_name="translate",
        input_data={
            "text": "Hello, how are you?",
            "target_language": "es",
        },
        context=context,
    )
    
    print(f"Input:  Hello, how are you?")
    print(f"Output: {result['translated_text']}")
    print(f"Lang:   {result['detected_source_language']} → {result['target_language']}")
    
    # Example 2: Translate to French
    print("\n📝 Example 2: Translate to French")
    print("-" * 70)
    
    result = registry.execute(
        skill_name="translate",
        input_data={
            "text": "The weather is beautiful today.",
            "target_language": "fr",
        },
        context=context,
    )
    
    print(f"Input:  The weather is beautiful today.")
    print(f"Output: {result['translated_text']}")
    
    # Example 3: Translate to German
    print("\n📝 Example 3: Translate to German")
    print("-" * 70)
    
    result = registry.execute(
        skill_name="translate",
        input_data={
            "text": "I love programming in Python!",
            "target_language": "de",
        },
        context=context,
    )
    
    print(f"Input:  I love programming in Python!")
    print(f"Output: {result['translated_text']}")
    
    print("\n" + "=" * 70)
    print("✅ All examples completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    # NOTE: This example assumes you've created the translate skill:
    # 1. make new-skill NAME=translate
    # 2. Implement the _execute() method in src/agentic_system/skills/translate.py
    # 3. make register-skill NAME=translate
    # 4. python examples/translate_example.py
    
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nDid you forget to create the translate skill?")
        print("Run: make new-skill NAME=translate")
