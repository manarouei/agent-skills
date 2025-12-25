#!/usr/bin/env python3
"""Quick test for REAL translation with LLM"""

from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.integrations.tasks import register_skills_and_agents
import uuid

def main():
    print("\n" + "=" * 70)
    print("🌍  REAL TRANSLATION TEST - Using LLM Gateway")
    print("=" * 70 + "\n")
    
    # Register skills
    print("🔧 Initializing...")
    register_skills_and_agents()
    registry = get_skill_registry()
    print("✅ Ready!\n")
    
    # Create context
    context = ExecutionContext(
        trace_id=f"real-translate-{uuid.uuid4().hex[:8]}",
        job_id="test-job",
        agent_id="toni"
    )
    
    # Test cases with different languages
    test_cases = [
        {
            "text": "خرسهای کثیف به تو می اندیشند",
            "target": "en",
            "description": "Persian to English"
        },
        {
            "text": "Hello, how are you today?",
            "target": "es",
            "description": "English to Spanish"
        },
        {
            "text": "The quick brown fox jumps over the lazy dog",
            "target": "fa",
            "description": "English to Persian"
        },
        {
            "text": "Python is an amazing programming language",
            "target": "ar",
            "description": "English to Arabic"
        },
    ]
    
    for i, test in enumerate(test_cases, 1):
        print(f"{'='*70}")
        print(f"Test {i}: {test['description']}")
        print(f"{'='*70}")
        print(f"Original:  {test['text']}")
        print(f"Target:    {test['target']}")
        print("\n⏳ Translating with LLM...\n")
        
        try:
            result = registry.execute(
                name='translate',
                input_data={
                    'text': test['text'],
                    'target_language': test['target']
                },
                context=context
            )
            
            print(f"✅ Translation successful!")
            print(f"Translated: {result['translated_text']}")
            print(f"Target:     {result['target_language']}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        print()
    
    print("=" * 70)
    print("🎉 All translation tests completed!")
    print("=" * 70)

if __name__ == "__main__":
    main()
