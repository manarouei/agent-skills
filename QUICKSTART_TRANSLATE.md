# 🚀 Quick Start: Working with the Translate Skill

## Overview
You created a `translate` skill that's ready to use! Here's how to run and test it yourself.

---

## ✅ Method 1: Run the Demo Script (Easiest)

```bash
# Run the comprehensive demo (shows all 4 methods)
.venv/bin/python examples/run_translate_skill.py
```

**What this does:**
- Shows direct execution via registry
- Shows programmatic usage with Pydantic models
- Shows skill composition (pipelines)
- Shows input validation

---

## ✅ Method 2: Quick Python One-Liner

```bash
# Quick test from command line
.venv/bin/python -c "
from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.integrations.tasks import register_skills_and_agents

# Setup
register_skills_and_agents()
registry = get_skill_registry()
context = ExecutionContext(trace_id='test-1', job_id='job-1', agent_id='user')

# Execute
result = registry.execute(
    name='translate',
    input_data={'text': 'Hello, world!'},
    context=context
)

print('Result:', result.result)
"
```

---

## ✅ Method 3: Interactive Python Session

```bash
# Start Python with your virtual environment
.venv/bin/python
```

Then in the Python REPL:

```python
from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.integrations.tasks import register_skills_and_agents

# Register all skills
register_skills_and_agents()

# Get the registry
registry = get_skill_registry()

# Create execution context
context = ExecutionContext(
    trace_id='interactive-test',
    job_id='manual-job',
    agent_id='toni'
)

# Test 1: Simple translation
result = registry.execute(
    name='translate',
    input_data={'text': 'Python is awesome!'},
    context=context
)
print(result.result)

# Test 2: Different input
result = registry.execute(
    name='translate',
    input_data={'text': 'This is a test message'},
    context=context
)
print(result.result)

# Test 3: Use the skill class directly
from agentic_system.skills.translate import TranslateSkill, TranslateInput

skill = TranslateSkill()
input_data = TranslateInput(text="Direct skill usage!")
output = skill.execute(input_data, context)
print(output.result)
```

---

## ✅ Method 4: Create Your Own Test Script

```bash
# Create a new test script
cat > test_my_translate.py << 'EOF'
#!/usr/bin/env python3
"""My personal translate skill test"""

from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.integrations.tasks import register_skills_and_agents

def main():
    # Setup
    register_skills_and_agents()
    registry = get_skill_registry()
    context = ExecutionContext(
        trace_id='my-test',
        job_id='test-job',
        agent_id='toni'
    )
    
    # Test cases
    test_cases = [
        "Hello, how are you?",
        "Python is a great programming language",
        "I love working with AI agents",
        "This translate skill is amazing!"
    ]
    
    print("🧪 Testing Translate Skill\n")
    print("=" * 60)
    
    for i, text in enumerate(test_cases, 1):
        print(f"\nTest {i}:")
        print(f"  Input:  {text}")
        
        result = registry.execute(
            name='translate',
            input_data={'text': text},
            context=context
        )
        
        print(f"  Output: {result.result}")
        print("  ✅ Success!")
    
    print("\n" + "=" * 60)
    print("🎉 All tests completed!")

if __name__ == "__main__":
    main()
EOF

# Make it executable
chmod +x test_my_translate.py

# Run it
.venv/bin/python test_my_translate.py
```

---

## ✅ Method 5: Run Unit Tests

```bash
# Run the auto-generated tests
make test-skill NAME=translate

# Or run directly with pytest
.venv/bin/pytest tests/unit/test_translate_skill.py -v

# Run with coverage
make test-skill-cov NAME=translate
```

---

## 🔧 Customize the Skill

### Step 1: Open the skill file
```bash
vim src/agentic_system/skills/translate.py
# or
code src/agentic_system/skills/translate.py
```

### Step 2: Replace the mock implementation

Find this line in the `_execute` method:
```python
return TranslateOutput(result=f"Processed: {input_data.text}")
```

Replace with **REAL** translation logic:

#### Option A: Use LLM Gateway (Recommended)
```python
def _execute(
    self, input_data: TranslateInput, context: ExecutionContext
) -> TranslateOutput:
    # Use the LLM gateway for translation
    from agentic_system.runtime.registry import get_skill_registry
    
    registry = get_skill_registry()
    
    prompt = f"Translate the following text to Spanish: {input_data.text}"
    
    llm_result = registry.execute(
        name="llm.anthropic_gateway",
        input_data={"prompt": prompt},
        context=context
    )
    
    return TranslateOutput(result=llm_result.response)
```

#### Option B: Use Google Translate API
```python
def _execute(
    self, input_data: TranslateInput, context: ExecutionContext
) -> TranslateOutput:
    from googletrans import Translator
    
    translator = Translator()
    translation = translator.translate(
        input_data.text,
        dest='es'  # Spanish
    )
    
    return TranslateOutput(result=translation.text)
```

#### Option C: Use DeepL API
```python
def _execute(
    self, input_data: TranslateInput, context: ExecutionContext
) -> TranslateOutput:
    import deepl
    
    translator = deepl.Translator("YOUR_API_KEY")
    result = translator.translate_text(
        input_data.text,
        target_lang="ES"
    )
    
    return TranslateOutput(result=result.text)
```

### Step 3: Add target language support

Update the input model:
```python
class TranslateInput(BaseModel):
    """Input model for translate skill"""
    text: str = Field(description="The text to translate")
    target_language: str = Field(
        default="es",
        description="Target language code (e.g., 'es', 'fr', 'de')"
    )
    source_language: str | None = Field(
        default=None,
        description="Source language (auto-detect if None)"
    )
```

Update the output model:
```python
class TranslateOutput(BaseModel):
    """Output model for translate skill"""
    result: str = Field(description="The translated text")
    detected_language: str | None = Field(
        default=None,
        description="Auto-detected source language"
    )
    confidence: float | None = Field(
        default=None,
        description="Translation confidence score (0-1)"
    )
```

### Step 4: Test your changes
```bash
# Validate the implementation
make validate-skill NAME=translate

# Run the tests
make test-skill NAME=translate

# Test manually
.venv/bin/python test_my_translate.py
```

---

## 📊 Check Skill Info

```bash
# See detailed information about the skill
make skill-info NAME=translate

# Read the documentation
make skill-docs NAME=translate

# See all available skills
make list-skills
```

---

## 🐛 Troubleshooting

### Error: "Skill 'translate' not found"
```bash
# Re-register the skill
make register-skill NAME=translate

# Or manually check registration
.venv/bin/python -c "
from agentic_system.integrations.tasks import register_skills_and_agents
from agentic_system.runtime.registry import get_skill_registry

register_skills_and_agents()
registry = get_skill_registry()
print('Available skills:', list(registry.list_skills().keys()))
"
```

### Error: "Module not found"
```bash
# Make sure you're using the virtual environment
which python  # Should show .venv/bin/python

# If not, activate it
source .venv/bin/activate
```

### Error: Validation errors
```bash
# Check what's wrong
make validate-skill NAME=translate

# Read the detailed error messages
```

---

## 🎯 Next Steps

1. **Test the mock implementation** (already done! ✅)
2. **Implement real translation logic** (choose Option A, B, or C above)
3. **Add more features** (target language, auto-detect, confidence scores)
4. **Create more skills** using the same workflow
5. **Build agents** that compose multiple skills

---

## 📚 Additional Resources

- **Full Guide**: `docs/SKILL_DEVELOPMENT.md`
- **Execution Methods**: `docs/HOW_TO_RUN_SKILLS.md`
- **Advanced Patterns**: `docs/SUCCESS_SUMMARY.md`
- **Working Example**: `examples/run_translate_skill.py`

---

## 💡 Pro Tips

1. **Use the demo script** to understand all execution patterns
2. **Start with mock implementation** to validate the workflow
3. **Add real logic incrementally** (one method at a time)
4. **Test after each change** using `make test-skill`
5. **Use skill composition** to build complex workflows
6. **Check logs** for debugging (logs include trace_id, job_id, agent_id)

---

**Ready to test?** Run this now:

```bash
.venv/bin/python examples/run_translate_skill.py
```

Happy coding! 🚀
