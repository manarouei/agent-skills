#!/usr/bin/env python3
"""
Interactive Translate Skill Tester
Run this to test your translate skill interactively!

Usage:
    .venv/bin/python interactive_translate_test.py
"""

from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.integrations.tasks import register_skills_and_agents
from agentic_system.skills.translate import TranslateSkill, TranslateInput
import uuid


def print_banner():
    """Print a nice banner"""
    print("\n" + "=" * 70)
    print("🌍  INTERACTIVE TRANSLATE SKILL TESTER  🌍")
    print("=" * 70 + "\n")


def print_menu():
    """Print the menu options"""
    print("\n📋 CHOOSE A TEST METHOD:\n")
    print("  1. Quick test with sample text")
    print("  2. Enter your own text to translate")
    print("  3. Batch test multiple texts")
    print("  4. Test input validation (error handling)")
    print("  5. Test with Pydantic models directly")
    print("  6. View skill information")
    print("  7. Exit")
    print()


def quick_test(registry, context):
    """Run a quick test with sample text"""
    print("\n🚀 QUICK TEST\n")
    
    sample_texts = [
        "Hello, world!",
        "Python is an amazing programming language",
        "AI agents are the future"
    ]
    
    for i, text in enumerate(sample_texts, 1):
        print(f"Test {i}:")
        print(f"  Input:  {text}")
        
        result = registry.execute(
            name='translate',
            input_data={'text': text},
            context=context
        )
        
        # Handle both old and new output format
        if 'translated_text' in result:
            print(f"  Output: {result['translated_text']}")
            if result.get('target_language'):
                print(f"  Target: {result['target_language']}")
        else:
            print(f"  Output: {result.get('result', result)}")
        print("  ✅ Success!\n")


def custom_text_test(registry, context):
    """Test with user's custom text"""
    print("\n✏️  CUSTOM TEXT TEST\n")
    
    text = input("Enter text to translate: ").strip()
    
    if not text:
        print("❌ No text entered!")
        return
    
    print(f"\n  Input:  {text}")
    
    result = registry.execute(
        name='translate',
        input_data={'text': text},
        context=context
    )
    
    # Handle both old and new output format
    if 'translated_text' in result:
        print(f"  Output: {result['translated_text']}")
        if result.get('target_language'):
            print(f"  Target: {result['target_language']}")
    else:
        print(f"  Output: {result.get('result', result)}")
    print("  ✅ Success!")


def batch_test(registry, context):
    """Test multiple texts in batch"""
    print("\n📦 BATCH TEST\n")
    print("Enter texts to translate (one per line).")
    print("Enter empty line when done.\n")
    
    texts = []
    while True:
        text = input(f"Text {len(texts) + 1}: ").strip()
        if not text:
            break
        texts.append(text)
    
    if not texts:
        print("❌ No texts entered!")
        return
    
    print(f"\n🔄 Processing {len(texts)} texts...\n")
    
    for i, text in enumerate(texts, 1):
        print(f"Batch {i}/{len(texts)}:")
        print(f"  Input:  {text}")
        
        result = registry.execute(
            name='translate',
            input_data={'text': text},
            context=context
        )
        
        # Handle both old and new output format
        if 'translated_text' in result:
            print(f"  Output: {result['translated_text']}")
        else:
            print(f"  Output: {result.get('result', result)}")
        print("  ✅ Done!\n")
    
    print(f"🎉 Batch complete! Processed {len(texts)} texts.")


def validation_test(registry, context):
    """Test input validation and error handling"""
    print("\n🛡️  VALIDATION TEST\n")
    
    test_cases = [
        {
            "name": "Valid input",
            "data": {"text": "This should work"},
            "should_fail": False
        },
        {
            "name": "Empty text",
            "data": {"text": ""},
            "should_fail": False  # Empty string is valid, just not useful
        },
        {
            "name": "Missing 'text' field",
            "data": {},
            "should_fail": True
        },
        {
            "name": "Invalid field type",
            "data": {"text": 123},
            "should_fail": True
        }
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['name']}")
        print(f"  Input data: {test['data']}")
        
        try:
            result = registry.execute(
                name='translate',
                input_data=test['data'],
                context=context
            )
            # Handle both old and new output format
            if 'translated_text' in result:
                print(f"  Output: {result['translated_text']}")
            else:
                print(f"  Output: {result.get('result', result)}")
            
            if test['should_fail']:
                print("  ⚠️  Expected to fail but succeeded!")
            else:
                print("  ✅ Success!")
        
        except Exception as e:
            if test['should_fail']:
                print(f"  ✅ Failed as expected: {type(e).__name__}")
            else:
                print(f"  ❌ Unexpected error: {e}")
        
        print()


def pydantic_test():
    """Test using Pydantic models directly"""
    print("\n🔧 PYDANTIC MODEL TEST\n")
    
    # Create context
    context = ExecutionContext(
        trace_id=f"pydantic-test-{uuid.uuid4().hex[:8]}",
        job_id="direct-job",
        agent_id="toni"
    )
    
    # Use the skill directly
    skill = TranslateSkill()
    
    # Test 1: Create input with Pydantic
    print("Test 1: Using Pydantic model")
    input_model = TranslateInput(text="Testing with Pydantic models!")
    print(f"  Input model: {input_model}")
    print(f"  Input.text: {input_model.text}")
    
    output = skill.execute(input_model, context)
    print(f"  Output model: {output}")
    print(f"  Output.result: {output.result}")
    print("  ✅ Success!\n")
    
    # Test 2: Dict to Pydantic conversion
    print("Test 2: Dict to Pydantic conversion")
    input_dict = {"text": "Convert dict to Pydantic"}
    input_model = TranslateInput(**input_dict)
    print(f"  Input dict: {input_dict}")
    print(f"  Converted to: {input_model}")
    
    output = skill.execute(input_model, context)
    print(f"  Output: {output.result}")
    print("  ✅ Success!")


def show_skill_info(registry):
    """Show detailed skill information"""
    print("\n📊 SKILL INFORMATION\n")
    
    # Get the translate skill
    skill = registry.get('translate')
    
    if skill is None:
        print("❌ Translate skill not found!")
        return
    
    spec = skill.spec()
    
    print(f"Name:        {spec.name}")
    print(f"Version:     {spec.version}")
    print(f"Side Effect: {spec.side_effect}")
    print(f"Timeout:     {spec.timeout_seconds}s")
    print(f"Idempotent:  {spec.idempotent}")
    
    print("\n📥 Input Model:")
    input_model = skill.input_model()
    for field_name, field_info in input_model.model_fields.items():
        print(f"  - {field_name}: {field_info.annotation}")
        if field_info.description:
            print(f"    {field_info.description}")
    
    print("\n📤 Output Model:")
    output_model = skill.output_model()
    for field_name, field_info in output_model.model_fields.items():
        print(f"  - {field_name}: {field_info.annotation}")
        if field_info.description:
            print(f"    {field_info.description}")
    
    print("\n💡 All registered skills:")
    skill_keys = registry.list_skills()
    skill_names = sorted([key.split('@')[0] for key in skill_keys])
    for skill_name in skill_names:
        print(f"  - {skill_name}")


def main():
    """Main interactive loop"""
    print_banner()
    
    print("🔧 Initializing...")
    
    # Register all skills
    register_skills_and_agents()
    
    # Get registry
    registry = get_skill_registry()
    
    # Create execution context
    context = ExecutionContext(
        trace_id=f"interactive-{uuid.uuid4().hex[:8]}",
        job_id="test-job",
        agent_id="toni"
    )
    
    print("✅ Ready!\n")
    
    # Check if translate skill is available
    skill_keys = registry.list_skills()  # Returns list of "name@version" strings
    skill_names = [key.split('@')[0] for key in skill_keys]
    
    if 'translate' not in skill_names:
        print("⚠️  WARNING: Translate skill not found in registry!")
        print("Available skills:", skill_names)
        print("\nTry running: make register-skill NAME=translate")
        return
    
    # Interactive loop
    while True:
        print_menu()
        
        choice = input("Enter your choice (1-7): ").strip()
        
        if choice == '1':
            quick_test(registry, context)
        
        elif choice == '2':
            custom_text_test(registry, context)
        
        elif choice == '3':
            batch_test(registry, context)
        
        elif choice == '4':
            validation_test(registry, context)
        
        elif choice == '5':
            pydantic_test()
        
        elif choice == '6':
            show_skill_info(registry)
        
        elif choice == '7':
            print("\n👋 Goodbye!\n")
            break
        
        else:
            print("\n❌ Invalid choice! Please enter 1-7.")
        
        input("\nPress Enter to continue...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!\n")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
