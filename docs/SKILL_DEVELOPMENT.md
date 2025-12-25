# 🛠️ Skill Development Guide

**Quick reference for creating and managing skills in the agentic system.**

---

## 🚀 Quick Start: Create Your First Skill

```bash
# 1. Create a new skill from template
make new-skill NAME=my_skill

# 2. Edit the implementation
vim src/agentic_system/skills/my_skill.py

# 3. Validate the implementation
make validate-skill NAME=my_skill

# 4. Run tests
make test-skill NAME=my_skill

# 5. Register in the system
make register-skill NAME=my_skill

# 6. View skill info
make skill-info NAME=my_skill
```

---

## 📋 Available Commands

### Skill Creation

```bash
make new-skill NAME=my_skill              # Create new skill from template
make register-skill NAME=my_skill         # Register skill in system
```

### Skill Development

```bash
make test-skill NAME=my_skill             # Run skill tests
make test-skill-cov NAME=my_skill         # Run tests with coverage
make validate-skill NAME=my_skill         # Validate implementation
```

### Skill Discovery

```bash
make list-skills                          # List all available skills
make skill-info NAME=my_skill             # Show detailed skill info
make skill-docs NAME=my_skill             # Show skill documentation
make all-skill-docs                       # Show all skill docs
```

### Skill Examples

```bash
make skill-example NAME=my_skill          # Run skill example (if exists)
```

---

## 🎯 Skill Template Structure

When you run `make new-skill NAME=my_skill`, it creates:

### 1. Implementation: `src/agentic_system/skills/my_skill.py`

```python
from pydantic import BaseModel, Field
from agentic_system.runtime import Skill, SkillSpec, SideEffect, ExecutionContext

class MySkillInput(BaseModel):
    """Input schema."""
    text: str = Field(..., description="Input text")

class MySkillOutput(BaseModel):
    """Output schema."""
    result: str = Field(..., description="Result")

class MySkillSkill(Skill):
    """Skill implementation."""
    
    def spec(self) -> SkillSpec:
        return SkillSpec(
            name="my_skill",
            version="1.0.0",
            side_effect=SideEffect.NONE,
            timeout_s=30,
            idempotent=True,
        )
    
    def input_model(self) -> type[BaseModel]:
        return MySkillInput
    
    def output_model(self) -> type[BaseModel]:
        return MySkillOutput
    
    def _execute(
        self,
        input_data: MySkillInput,
        context: ExecutionContext,
    ) -> MySkillOutput:
        # TODO: Implement your logic
        result = f"Processed: {input_data.text}"
        return MySkillOutput(result=result)
```

### 2. Tests: `tests/unit/test_my_skill_skill.py`

```python
import pytest
from agentic_system.skills.my_skill import MySkillSkill, MySkillInput

class TestMySkillSkill:
    @pytest.fixture
    def skill(self):
        return MySkillSkill()
    
    def test_execute_basic(self, skill, context):
        result = skill.execute({"text": "test"}, context)
        assert "result" in result
```

### 3. Documentation: `skills/my_skill/SKILL.md`

Standard documentation template with:
- Purpose
- Input/Output schemas
- Behavior description
- Usage examples
- Error handling

---

## 🔧 Skill Implementation Checklist

### Required Methods

Every skill MUST implement:

- ✅ `spec()` → Returns `SkillSpec` with metadata
- ✅ `input_model()` → Returns Pydantic `BaseModel` class
- ✅ `output_model()` → Returns Pydantic `BaseModel` class  
- ✅ `_execute(input_data, context)` → Implements logic

### Specification (`spec()`)

```python
def spec(self) -> SkillSpec:
    return SkillSpec(
        name="skill.name",           # Unique identifier (use snake_case)
        version="1.0.0",             # Semantic versioning
        side_effect=SideEffect.NONE, # NONE, NETWORK, STORAGE, BOTH
        timeout_s=30,                # Execution timeout in seconds
        idempotent=True,             # Can be safely retried?
    )
```

### Side Effects

Choose the appropriate side effect:

| Side Effect | Description | Examples |
|-------------|-------------|----------|
| `NONE` | Pure computation, no external effects | Text processing, calculations |
| `NETWORK` | Makes network calls | API calls, LLM gateway |
| `STORAGE` | Reads/writes storage | Database, file system |
| `BOTH` | Both network and storage | Complex integrations |

### Input/Output Models

```python
class MySkillInput(BaseModel):
    """Input schema with validation."""
    
    # Required field
    text: str = Field(..., description="Text to process")
    
    # Optional field with default
    max_length: int = Field(100, description="Max output length")
    
    # Optional field (None allowed)
    metadata: dict[str, Any] | None = Field(None, description="Optional metadata")
```

**Best Practices:**
- Use descriptive field names
- Always add `description` to fields
- Use type hints for validation
- Add default values for optional fields
- Document constraints in descriptions

---

## 🧪 Testing Your Skill

### Basic Test Structure

```python
class TestMySkillSkill:
    @pytest.fixture
    def skill(self):
        return MySkillSkill()
    
    @pytest.fixture
    def context(self):
        return ExecutionContext(
            trace_id="test-trace-123",
            job_id="test-job-456",
            agent_id="test-agent",
        )
    
    def test_spec(self, skill):
        """Test skill specification."""
        spec = skill.spec()
        assert spec.name == "my_skill"
        assert spec.version == "1.0.0"
    
    def test_execute_basic(self, skill, context):
        """Test basic execution."""
        result = skill.execute({"text": "test"}, context)
        assert "result" in result
    
    def test_input_validation(self, skill, context):
        """Test input validation."""
        with pytest.raises(Exception):
            skill.execute({}, context)  # Missing required field
```

### Test Categories

1. **Specification Tests**: Verify metadata
2. **Basic Execution Tests**: Happy path scenarios
3. **Input Validation Tests**: Invalid inputs
4. **Edge Cases**: Empty strings, special characters, limits
5. **Error Handling**: Expected failures
6. **Side Effects**: Mock external dependencies

### Running Tests

```bash
# Run specific skill tests
make test-skill NAME=my_skill

# Run with coverage
make test-skill-cov NAME=my_skill

# Run all tests
make test
```

---

## 📝 Documentation Guidelines

Your `skills/my_skill/SKILL.md` should include:

### 1. Metadata

```markdown
# My Skill

**Skill Name:** `my_skill`  
**Version:** `1.0.0`  
**Side Effect:** `NONE`  
**Idempotent:** Yes
```

### 2. Purpose

Clear description of what the skill does and why it exists.

### 3. Schemas

```markdown
## Input Schema

\`\`\`python
{
  "text": "Input text to process",
  "max_length": 100  # Optional, default 100
}
\`\`\`

## Output Schema

\`\`\`python
{
  "result": "Processed text"
}
\`\`\`
```

### 4. Behavior

Step-by-step description of what the skill does:
1. Input validation
2. Processing steps
3. External calls (if any)
4. Output generation

### 5. Usage Example

Complete working example showing how to use the skill.

### 6. Error Handling

Document error conditions and exceptions.

---

## 🎨 Skill Design Patterns

### Pattern 1: Simple Transformer

Pure computation, no side effects.

```python
def _execute(self, input_data: Input, context: ExecutionContext) -> Output:
    # Transform input to output
    result = process(input_data.text)
    return Output(result=result)
```

### Pattern 2: External API Caller

Makes network calls, handles retries.

```python
def _execute(self, input_data: Input, context: ExecutionContext) -> Output:
    import requests
    from tenacity import retry, stop_after_attempt
    
    @retry(stop=stop_after_attempt(3))
    def call_api():
        response = requests.post(url, json=input_data.dict())
        response.raise_for_status()
        return response.json()
    
    result = call_api()
    return Output(**result)
```

### Pattern 3: Skill Composition

Calls other skills via registry.

```python
def _execute(self, input_data: Input, context: ExecutionContext) -> Output:
    from agentic_system.runtime.registry import get_skill_registry
    
    registry = get_skill_registry()
    
    # Call first skill
    step1 = registry.execute("skill_a", input_data.dict(), context)
    
    # Call second skill
    step2 = registry.execute("skill_b", step1, context)
    
    return Output(**step2)
```

### Pattern 4: LLM-Powered Skill

Uses LLM Gateway for AI processing.

```python
def _execute(self, input_data: Input, context: ExecutionContext) -> Output:
    from agentic_system.runtime.registry import get_skill_registry
    
    registry = get_skill_registry()
    
    # Construct LLM prompt
    llm_input = {
        "messages": [{"role": "user", "content": input_data.text}],
        "max_tokens": 256,
    }
    
    # Call LLM Gateway
    result = registry.execute("llm.anthropic_gateway", llm_input, context)
    
    return Output(result=result["text"])
```

---

## ✅ Validation Checklist

Before registering a skill, ensure:

- [ ] All required methods implemented (`spec`, `input_model`, `output_model`, `_execute`)
- [ ] Input/Output models are Pydantic `BaseModel` subclasses
- [ ] All fields have descriptions
- [ ] `spec()` has correct `name`, `version`, `side_effect`, `timeout_s`, `idempotent`
- [ ] `_execute()` handles errors gracefully
- [ ] Tests cover happy path, edge cases, and errors
- [ ] Documentation exists and is complete
- [ ] Skill passes validation: `make validate-skill NAME=my_skill`
- [ ] All tests pass: `make test-skill NAME=my_skill`

---

## 🚨 Common Mistakes

### 1. Wrong Return Type

❌ **Wrong:**
```python
def _execute(self, input_data: Input, context: ExecutionContext) -> dict:
    return {"result": "value"}
```

✅ **Correct:**
```python
def _execute(self, input_data: Input, context: ExecutionContext) -> Output:
    return Output(result="value")
```

### 2. Missing Field Descriptions

❌ **Wrong:**
```python
class Input(BaseModel):
    text: str
```

✅ **Correct:**
```python
class Input(BaseModel):
    text: str = Field(..., description="Input text to process")
```

### 3. Incorrect Side Effect

❌ **Wrong:**
```python
# Skill makes API calls but marked as NONE
side_effect=SideEffect.NONE
```

✅ **Correct:**
```python
side_effect=SideEffect.NETWORK
```

### 4. Not Using Context

❌ **Wrong:**
```python
def _execute(self, input_data: Input, context: ExecutionContext) -> Output:
    # Context not used for logging
    result = process(input_data)
    return Output(result=result)
```

✅ **Correct:**
```python
def _execute(self, input_data: Input, context: ExecutionContext) -> Output:
    logger.info("Processing", extra={
        "trace_id": context.trace_id,
        "job_id": context.job_id,
    })
    result = process(input_data)
    return Output(result=result)
```

---

## 📊 Example: Complete Skill

See `src/agentic_system/skills/summarize.py` for a complete, production-ready example:

```bash
make skill-info NAME=summarize
```

---

## 🔗 Related Documentation

- **[HOW_IT_WORKS.md](HOW_IT_WORKS.md)**: Full system explanation
- **[LLM_RULES.md](LLM_RULES.md)**: P0/P1/P2 rules for bounded autonomy
- **[QUICK_START.md](QUICK_START.md)**: Quick reference guide
- **[README.md](../README.md)**: Project overview

---

## 💡 Pro Tips

1. **Start Simple**: Begin with pure computation (side_effect=NONE), add complexity later
2. **Validate Early**: Run `make validate-skill` after every change
3. **Test First**: Write tests before implementation (TDD)
4. **Copy Patterns**: Use existing skills as templates (`healthcheck`, `summarize`)
5. **Document Intent**: Explain WHY in docstrings, not just WHAT
6. **Use Context**: Always log with trace_id, job_id for debugging
7. **Handle Errors**: Catch specific exceptions, add context, re-raise as SkillError
8. **Keep Atomic**: Each skill should do ONE thing well
9. **Compose Skills**: Build complex workflows by combining simple skills
10. **Follow Bounded Autonomy**: Respect P0/P1/P2 rules when using LLM Gateway

---

## 🎯 Next Steps

1. **Create Your First Skill**: `make new-skill NAME=my_skill`
2. **Study Examples**: `make skill-info NAME=summarize`
3. **Read Source Code**: Browse `src/agentic_system/skills/`
4. **Join Development**: Check `docs/CONTRIBUTING.md` (if exists)

**Happy skill building!** 🚀
