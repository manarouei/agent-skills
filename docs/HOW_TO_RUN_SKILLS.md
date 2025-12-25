# 🚀 How to Run Your Skills

**Complete guide to executing skills in the agentic system**

---

## ✅ Your Translate Skill is Now Ready!

After running `make new-skill NAME=translate` and fixing the registration, your skill is:

- ✅ **Created**: Implementation, tests, and docs generated
- ✅ **Registered**: Added to skill registry
- ✅ **Validated**: All checks pass
- ✅ **Ready to use**: Can be executed immediately

---

## 🎯 Four Ways to Run Your Skill

### Method 1: Direct Execution (Recommended for Testing)

```python
from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.integrations.tasks import register_skills_and_agents

# Register all skills
register_skills_and_agents()

# Get skill registry
registry = get_skill_registry()

# Create execution context
context = ExecutionContext(
    trace_id="my-trace-123",
    job_id="my-job-456",
    agent_id="my_agent",
)

# Execute skill
result = registry.execute(
    name="translate",          # Skill name from spec()
    input_data={
        "text": "Hello, world!",
    },
    context=context,
)

print(result['result'])  # Output: Processed: Hello, world!
```

**When to use**: Quick testing, debugging, experimentation

---

### Method 2: Programmatic Usage (Recommended for Production)

```python
from agentic_system.runtime import ExecutionContext
from agentic_system.skills.translate import TranslateSkill, TranslateInput

# Create skill instance
skill = TranslateSkill()

# Create context
context = ExecutionContext(
    trace_id="my-trace-123",
    job_id="my-job-456",
    agent_id="my_agent",
)

# Create input with Pydantic model (type-safe!)
input_data = TranslateInput(
    text="Python is awesome!"
)

# Execute
result = skill.execute(input_data, context)
print(result['result'])
```

**When to use**: Production code, type safety needed, better IDE support

---

### Method 3: Via Make Commands (Recommended for CLI)

First, create a CLI command in `src/agentic_system/cli.py`:

```python
def cmd_translate(args: argparse.Namespace) -> None:
    """Run translate skill."""
    from agentic_system.integrations.tasks import register_skills_and_agents
    register_skills_and_agents()
    
    registry = get_skill_registry()
    context = ExecutionContext(
        trace_id=f"cli-{uuid.uuid4()}",
        job_id=f"translate-{uuid.uuid4()}",
        agent_id="cli",
    )
    
    result = registry.execute(
        name="translate",
        input_data={"text": args.text},
        context=context,
    )
    
    print(result['result'])
```

Then add to Makefile:

```makefile
translate:  ## Translate text (requires TEXT)
	@if [ -z "$(TEXT)" ]; then \
		echo "Usage: make translate TEXT='your text here'"; \
		exit 1; \
	fi
	python -m agentic_system.cli translate --text "$(TEXT)"
```

**Usage**:
```bash
make translate TEXT="Hello, world!"
```

**When to use**: Command-line interface, shell scripts, automation

---

### Method 4: Via Agent Orchestration (Recommended for Workflows)

Create an agent that uses your skill:

```python
from agentic_system.runtime import Agent, AgentSpec, ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from pydantic import BaseModel, Field

class TranslatorAgentInput(BaseModel):
    text: str = Field(..., description="Text to translate")
    target_language: str = Field("es", description="Target language")

class TranslatorAgentOutput(BaseModel):
    translated: str = Field(..., description="Translated text")
    original: str = Field(..., description="Original text")

class TranslatorAgent(Agent):
    def spec(self) -> AgentSpec:
        return AgentSpec(
            agent_id="translator",
            version="1.0.0",
            step_limit=5,
            description="Translation agent",
        )
    
    def input_model(self) -> type[BaseModel]:
        return TranslatorAgentInput
    
    def output_model(self) -> type[BaseModel]:
        return TranslatorAgentOutput
    
    def _run(
        self,
        input_data: TranslatorAgentInput,
        context: ExecutionContext,
    ) -> TranslatorAgentOutput:
        self._check_step_limit()
        
        # Use translate skill
        registry = get_skill_registry()
        result = registry.execute(
            name="translate",
            input_data={"text": input_data.text},
            context=context,
        )
        
        return TranslatorAgentOutput(
            translated=result['result'],
            original=input_data.text,
        )
```

**When to use**: Complex workflows, multi-step processes, production systems

---

## 🏃 Quick Start: Run Your Translate Skill Now

```bash
# 1. Run the demo script
cd /home/toni/agent-skills
.venv/bin/python examples/run_translate_skill.py

# 2. Or create your own script
cat > test_translate.py << 'EOF'
from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.integrations.tasks import register_skills_and_agents

register_skills_and_agents()
registry = get_skill_registry()

context = ExecutionContext(
    trace_id="test-123",
    job_id="job-456",
    agent_id="test",
)

result = registry.execute(
    name="translate",
    input_data={"text": "Your text here"},
    context=context,
)

print(f"Result: {result['result']}")
EOF

.venv/bin/python test_translate.py
```

---

## 🔧 Implementing Real Translation Logic

Now that your skill template works, implement real translation:

### Option 1: Use LLM Gateway (Recommended)

```python
def _execute(
    self,
    input_data: TranslateInput,
    context: ExecutionContext,
) -> TranslateOutput:
    """Execute translate skill using LLM."""
    from agentic_system.runtime.registry import get_skill_registry
    
    registry = get_skill_registry()
    
    # Call LLM Gateway
    llm_result = registry.execute(
        name="llm.anthropic_gateway",
        input_data={
            "messages": [
                {
                    "role": "user",
                    "content": f"Translate to {input_data.target_language}: {input_data.text}"
                }
            ],
            "max_tokens": 512,
            "temperature": 0.2,
        },
        context=context,
    )
    
    return TranslateOutput(
        translated_text=llm_result['text'],
        target_language=input_data.target_language,
        detected_source_language="auto",
    )
```

### Option 2: Use External API

```python
def _execute(
    self,
    input_data: TranslateInput,
    context: ExecutionContext,
) -> TranslateOutput:
    """Execute translate skill using external API."""
    import requests
    
    # Example: Google Translate API
    response = requests.post(
        "https://translation.googleapis.com/language/translate/v2",
        json={
            "q": input_data.text,
            "target": input_data.target_language,
            "format": "text",
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )
    
    response.raise_for_status()
    data = response.json()
    
    return TranslateOutput(
        translated_text=data['translations'][0]['translatedText'],
        target_language=input_data.target_language,
        detected_source_language=data.get('detectedSourceLanguage', 'unknown'),
    )
```

### Option 3: Use Local Library

```python
def _execute(
    self,
    input_data: TranslateInput,
    context: ExecutionContext,
) -> TranslateOutput:
    """Execute translate skill using local library."""
    from transformers import pipeline
    
    # Load translation model
    translator = pipeline(
        "translation",
        model=f"Helsinki-NLP/opus-mt-en-{input_data.target_language}"
    )
    
    result = translator(input_data.text)[0]
    
    return TranslateOutput(
        translated_text=result['translation_text'],
        target_language=input_data.target_language,
        detected_source_language="en",
    )
```

---

## 📊 Update Input/Output Models

After implementing real logic, update your models:

```python
class TranslateInput(BaseModel):
    """Input schema for Translate skill."""
    
    text: str = Field(..., description="Text to translate")
    target_language: str = Field(
        "es",
        description="Target language code (ISO 639-1)",
        examples=["es", "fr", "de", "it", "pt", "ja", "zh"],
    )
    source_language: str | None = Field(
        None,
        description="Source language (auto-detect if None)",
    )


class TranslateOutput(BaseModel):
    """Output schema for Translate skill."""
    
    translated_text: str = Field(..., description="Translated text")
    target_language: str = Field(..., description="Target language code")
    detected_source_language: str = Field(
        ...,
        description="Detected or specified source language",
    )
    confidence: float | None = Field(
        None,
        description="Translation confidence score (0-1)",
        ge=0.0,
        le=1.0,
    )
```

---

## 🧪 Test Your Implementation

```bash
# Run tests
make test-skill NAME=translate

# Run with coverage
make test-skill-cov NAME=translate

# Validate implementation
make validate-skill NAME=translate
```

---

## 🎯 Integration with Bounded Autonomy

Use your skill with the bounded autonomy workflow:

```bash
# 1. Plan a feature that uses translation
make plan TASK="Add multi-language support to summarization"

# 2. Implement using the translate skill
# ... implement ...

# 3. Review compliance
make check-compliance FILES="src/skills/translate.py,tests/unit/test_translate_skill.py"

# 4. Test
make test-skill NAME=translate

# 5. Deploy
git add src/skills/translate.py tests/unit/test_translate_skill.py
git commit -m "feat: Add translate skill for multi-language support"
```

---

## 💡 Common Use Cases

### 1. Batch Translation

```python
def translate_batch(texts: list[str], target_lang: str) -> list[str]:
    """Translate multiple texts."""
    registry = get_skill_registry()
    context = ExecutionContext(...)
    
    results = []
    for text in texts:
        result = registry.execute(
            name="translate",
            input_data={"text": text, "target_language": target_lang},
            context=context,
        )
        results.append(result['translated_text'])
    
    return results
```

### 2. Auto-Detection + Translation

```python
def auto_translate(text: str) -> dict:
    """Detect language and translate to English."""
    # First detect language (you could add a detect_language skill)
    # Then translate if not English
    if detected_lang != "en":
        result = registry.execute(
            name="translate",
            input_data={"text": text, "target_language": "en"},
            context=context,
        )
        return result
    return {"translated_text": text, "original": True}
```

### 3. Skill Composition

```python
def summarize_and_translate(text: str, lang: str) -> str:
    """Summarize then translate."""
    # Step 1: Summarize
    summary_result = registry.execute(
        name="text.summarize",
        input_data={"text": text, "max_words": 100},
        context=context,
    )
    
    # Step 2: Translate
    translate_result = registry.execute(
        name="translate",
        input_data={
            "text": summary_result['summary'],
            "target_language": lang,
        },
        context=context,
    )
    
    return translate_result['translated_text']
```

---

## 🚨 Troubleshooting

### Skill Not Found

```bash
# Check if skill is registered
make list-skills

# Re-register if needed
make register-skill NAME=translate
```

### Import Errors

```python
# Make sure to register skills before use
from agentic_system.integrations.tasks import register_skills_and_agents
register_skills_and_agents()
```

### Validation Errors

```python
# Check your input matches the model
from agentic_system.skills.translate import TranslateInput

# Valid
input_data = TranslateInput(text="Hello")  # ✅

# Invalid
input_data = TranslateInput()  # ❌ Missing required 'text'
```

---

## 📚 Next Steps

1. **Implement Real Logic**: Replace `Processed: {text}` with actual translation
2. **Add More Fields**: Enhance Input/Output models with confidence scores, etc.
3. **Write More Tests**: Cover edge cases, error handling, different languages
4. **Create CLI Command**: Add `make translate TEXT="..."` command
5. **Build an Agent**: Create TranslatorAgent for complex workflows
6. **Add Caching**: Cache translations for performance
7. **Monitor Usage**: Track translation requests via LLM Gateway

---

## 🎉 Conclusion

You now have a **fully functional skill template** that:

- ✅ Executes successfully
- ✅ Validates input automatically
- ✅ Integrates with skill registry
- ✅ Works with bounded autonomy
- ✅ Has tests and documentation
- ✅ Ready for production use

**Just implement the real translation logic and you're done!** 🚀

```bash
# Quick command reference
make skill-info NAME=translate       # View details
make test-skill NAME=translate       # Run tests
make validate-skill NAME=translate   # Validate
python examples/run_translate_skill.py  # Run demo
```

Happy translating! 🌍
