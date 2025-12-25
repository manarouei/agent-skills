# 🤖 Complete Guide: Agent Skills Development with Make Commands & Bounded Autonomy

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [Development Workflow](#development-workflow)
3. [Testing & Validation](#testing--validation)
4. [Running Skills](#running-skills)
5. [Bounded Autonomy Integration](#bounded-autonomy-integration)
6. [Complete Examples](#complete-examples)
7. [Advanced Patterns](#advanced-patterns)
8. [Troubleshooting](#troubleshooting)

---

## 🚀 Quick Start

### **Prerequisites**
```bash
# Ensure you have the virtual environment activated
source .venv/bin/activate

# Set your API key (for translation skills)
export OPENAI_API_KEY="your-api-key-here"
```

### **The Complete Workflow in 5 Commands**
```bash
# 1. Create a new skill
make new-skill NAME=sentiment_analysis

# 2. Validate it
make validate-skill NAME=sentiment_analysis

# 3. Test it
make test-skill NAME=sentiment_analysis

# 4. Register it
make register-skill NAME=sentiment_analysis

# 5. Run it
make run-skill NAME=sentiment_analysis INPUT='I love this product!'
```

---

## 🛠️ Development Workflow

### **Step 1: Create a New Skill**

```bash
make new-skill NAME=my_skill
```

**What this does:**
- ✅ Creates `src/agentic_system/skills/my_skill.py` (implementation)
- ✅ Creates `tests/unit/test_my_skill_skill.py` (6 test cases)
- ✅ Creates `skills/my_skill/SKILL.md` (documentation)
- ✅ Generates Pydantic input/output models
- ✅ Includes all required methods (spec, input_model, output_model, _execute)

**Generated files:**
```
src/agentic_system/skills/my_skill.py          # Your skill implementation
tests/unit/test_my_skill_skill.py              # Auto-generated tests
skills/my_skill/SKILL.md                       # Documentation template
```

### **Step 2: Implement Your Logic**

Edit `src/agentic_system/skills/my_skill.py`:

```python
def _execute(
    self,
    input_data: MySkillInput,
    context: ExecutionContext,
) -> MySkillOutput:
    """Execute your skill logic here."""
    
    # Example: Sentiment analysis
    text = input_data.text
    
    # Simple sentiment detection (replace with real logic)
    positive_words = ['love', 'great', 'excellent', 'amazing']
    negative_words = ['hate', 'bad', 'terrible', 'awful']
    
    text_lower = text.lower()
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    if positive_count > negative_count:
        sentiment = "positive"
    elif negative_count > positive_count:
        sentiment = "negative"
    else:
        sentiment = "neutral"
    
    return MySkillOutput(
        sentiment=sentiment,
        confidence=0.85
    )
```

### **Step 3: Update Input/Output Models**

Customize your Pydantic models:

```python
class MySkillInput(BaseModel):
    """Input schema for sentiment analysis."""
    text: str = Field(..., description="Text to analyze")
    language: str = Field(default="en", description="Language code")

class MySkillOutput(BaseModel):
    """Output schema for sentiment analysis."""
    sentiment: str = Field(..., description="Sentiment: positive, negative, or neutral")
    confidence: float = Field(..., description="Confidence score (0-1)")
    details: dict | None = Field(default=None, description="Additional details")
```

### **Step 4: Validate Your Implementation**

```bash
make validate-skill NAME=my_skill
```

**What this checks:**
- ✅ File exists: `src/agentic_system/skills/my_skill.py`
- ✅ Class exists: `MySkillSkill`
- ✅ Inherits from `Skill` base class
- ✅ Has required methods: `spec()`, `input_model()`, `output_model()`, `_execute()`
- ✅ Pydantic models are valid
- ✅ Test file exists
- ✅ Documentation exists

**Example output:**
```
Validating skill: my_skill
✅ Implementation file found
✅ Test file found
✅ Documentation found
✅ Skill class exists
✅ Inherits from Skill
✅ Has spec() method
✅ Has input_model() method
✅ Has output_model() method
✅ Has _execute() method
✅ Input model is valid
✅ Output model is valid

🎉 Skill validation passed!
```

---

## 🧪 Testing & Validation

### **Run Unit Tests**

```bash
# Test a specific skill
make test-skill NAME=my_skill

# Test with coverage report
make test-skill-cov NAME=my_skill

# Run all tests
make test

# Run all tests with coverage
make test-cov
```

### **Test Output Examples**

```bash
# Example 1: Translation skill
make test-skill NAME=openai_translate

# Example 2: With coverage
make test-skill-cov NAME=sentiment_analysis
```

**Expected output:**
```
Running tests for: sentiment_analysis
=================================== test session starts ===================================
collected 6 items

tests/unit/test_sentiment_analysis_skill.py::test_skill_spec PASSED                [ 16%]
tests/unit/test_sentiment_analysis_skill.py::test_input_model PASSED               [ 33%]
tests/unit/test_sentiment_analysis_skill.py::test_output_model PASSED              [ 50%]
tests/unit/test_sentiment_analysis_skill.py::test_execute_basic PASSED             [ 66%]
tests/unit/test_sentiment_analysis_skill.py::test_execute_with_dict_input PASSED   [ 83%]
tests/unit/test_sentiment_analysis_skill.py::test_input_validation PASSED          [100%]

=================================== 6 passed in 0.42s ====================================
```

### **Manual Testing Script**

Create `test_my_skill.py`:

```python
#!/usr/bin/env python3
"""Manual test for my skill"""

from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.integrations.tasks import register_skills_and_agents

def main():
    # Setup
    register_skills_and_agents()
    registry = get_skill_registry()
    context = ExecutionContext(
        trace_id='manual-test',
        job_id='test-job',
        agent_id='user'
    )
    
    # Test cases
    test_cases = [
        "I love this product!",
        "This is terrible and awful",
        "The weather is okay today"
    ]
    
    for text in test_cases:
        print(f"\nTesting: {text}")
        result = registry.execute(
            name='sentiment_analysis',
            input_data={'text': text},
            context=context
        )
        print(f"Result: {result}")

if __name__ == "__main__":
    main()
```

Run it:
```bash
.venv/bin/python test_my_skill.py
```

---

## 🚀 Running Skills

### **Method 1: Make Command (Quickest)**

```bash
# Basic usage
make run-skill NAME=skill_name INPUT='your text'

# With additional parameters
make run-skill NAME=openai.translate INPUT='Hello' TARGET_LANG=Spanish
```

**Examples:**

```bash
# Translation
make run-skill NAME=openai.translate INPUT='خرسهای کثیف به تو می اندیشند' TARGET_LANG=English
# Output: Dirty bears are thinking of you.

# Sentiment analysis
make run-skill NAME=sentiment_analysis INPUT='I love this!'
# Output: positive (confidence: 0.85)

# Summarization
make run-skill NAME=text.summarize INPUT='Long text here...'
# Output: Brief summary
```

### **Method 2: Bash Functions (Interactive)**

Load the helper functions:
```bash
source quick_translate.sh
```

Then use simple commands:
```bash
# Translation shortcuts
to_english 'خرسهای کثیف'
to_spanish 'Hello world'
to_persian 'I love AI'

# General translation
translate 'Bonjour' English
```

### **Method 3: Python REPL**

```bash
.venv/bin/python
```

```python
from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.integrations.tasks import register_skills_and_agents

# Setup
register_skills_and_agents()
registry = get_skill_registry()
ctx = ExecutionContext(trace_id='repl', job_id='j1', agent_id='user')

# Run skill
result = registry.execute(
    name='sentiment_analysis',
    input_data={'text': 'I love this!'},
    context=ctx
)
print(result)
```

### **Method 4: Python Script**

Create `run_skill.py`:
```python
#!/usr/bin/env python3
import os
os.environ["OPENAI_API_KEY"] = "your-key"

from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.integrations.tasks import register_skills_and_agents

register_skills_and_agents()
registry = get_skill_registry()
ctx = ExecutionContext(trace_id='script', job_id='j1', agent_id='user')

# Run your skill
result = registry.execute(
    name='openai.translate',
    input_data={'text': 'Hello', 'target_language': 'Spanish'},
    context=ctx
)

print(f"Result: {result['translated_text']}")
```

---

## 🤖 Bounded Autonomy Integration

### **What is Bounded Autonomy?**

Bounded autonomy provides **safe AI agent development** with:
- ✅ **Context Gating (P0)** - Review context before planning
- ✅ **Human-in-the-Loop (P1)** - Review plans before execution
- ✅ **Compliance Checking (P2)** - Validate changes against rules

### **Bounded Autonomy Workflow**

#### **Step 1: Planning Phase**

```bash
make plan TASK='Create a sentiment analysis skill' FILES='src/agentic_system/skills/'
```

**What this does:**
1. Runs **Context Gate (P0)** - Analyzes the files you provided
2. Generates a detailed plan with steps
3. **YOU REVIEW** the plan before proceeding

**Example output:**
```
🔍 P0: Context Gating
Analyzing files: src/agentic_system/skills/

📋 Generated Plan:
1. Create sentiment_analysis.py with Skill subclass
2. Implement sentiment detection logic
3. Add unit tests
4. Register in tasks.py
5. Validate with make validate-skill

👤 Review this plan. Proceed? (y/n)
```

#### **Step 2: Implementation Phase**

After reviewing the plan, implement your skill:

```bash
# Create the skill
make new-skill NAME=sentiment_analysis

# Implement the logic (edit the file)
vim src/agentic_system/skills/sentiment_analysis.py
```

#### **Step 3: Review Phase**

```bash
make review FILES='src/agentic_system/skills/sentiment_analysis.py,tests/unit/test_sentiment_analysis_skill.py'
```

**What this does:**
1. Uses **Code Review Skill** to analyze your changes
2. Checks for:
   - Code quality issues
   - Security vulnerabilities
   - Best practice violations
   - Missing error handling
3. Provides actionable feedback

**Example output:**
```
🔍 P1: Code Review
Analyzing: sentiment_analysis.py

✅ Positive Findings:
- Proper use of Pydantic models
- Good error handling
- Comprehensive logging

⚠️  Issues Found:
- Line 45: Consider adding input validation for empty strings
- Line 67: Magic number - extract to constant
- Missing docstring for helper function

📊 Overall Score: 8/10
```

#### **Step 4: Compliance Check**

```bash
make check-compliance FILES='src/agentic_system/skills/sentiment_analysis.py'
```

**What this checks:**
- ✅ **P0 Compliance**: Context was properly gated
- ✅ **P1 Compliance**: Code was reviewed
- ✅ **P2 Compliance**: Follows skill development rules
  - Inherits from `Skill` base class
  - Has all required methods
  - Uses Pydantic for validation
  - Includes proper logging
  - Has unit tests

**Example output:**
```
🔍 P2: Compliance Check

✅ P0 Compliance: Context gating completed
✅ P1 Compliance: Code review completed
✅ P2 Compliance: Follows skill template
✅ Has required methods
✅ Uses Pydantic models
✅ Has unit tests
✅ Has documentation

🎉 All compliance checks passed!
```

### **Complete Bounded Autonomy Example**

```bash
# 1. Plan the work
make plan TASK='Create translation skill using OpenAI' FILES='src/agentic_system/skills/'

# 2. Review the plan, then implement
make new-skill NAME=openai_translate

# 3. Edit the implementation
vim src/agentic_system/skills/openai_translate.py

# 4. Review the code
make review FILES='src/agentic_system/skills/openai_translate.py'

# 5. Fix any issues, then check compliance
make check-compliance FILES='src/agentic_system/skills/openai_translate.py'

# 6. Test it
make test-skill NAME=openai_translate

# 7. Register it
make register-skill NAME=openai_translate

# 8. Run it!
make run-skill NAME=openai.translate INPUT='Hello' TARGET_LANG=Spanish
```

---

## 📚 Complete Examples

### **Example 1: Sentiment Analysis Skill**

**1. Create the skill**
```bash
make new-skill NAME=sentiment_analysis
```

**2. Implement the logic**
Edit `src/agentic_system/skills/sentiment_analysis.py`:

```python
from pydantic import BaseModel, Field
from agentic_system.runtime import ExecutionContext, SideEffect, Skill, SkillSpec

class SentimentInput(BaseModel):
    text: str = Field(..., description="Text to analyze")

class SentimentOutput(BaseModel):
    sentiment: str = Field(..., description="positive, negative, or neutral")
    score: float = Field(..., description="Score from -1 to 1")

class SentimentAnalysisSkill(Skill):
    def spec(self) -> SkillSpec:
        return SkillSpec(
            name="sentiment_analysis",
            version="1.0.0",
            side_effect=SideEffect.NONE,
            timeout_s=10,
            idempotent=True,
        )
    
    def input_model(self) -> type[BaseModel]:
        return SentimentInput
    
    def output_model(self) -> type[BaseModel]:
        return SentimentOutput
    
    def _execute(self, input_data: SentimentInput, context: ExecutionContext) -> SentimentOutput:
        text = input_data.text.lower()
        
        # Simple word-based sentiment
        positive_words = ['love', 'great', 'excellent', 'amazing', 'wonderful']
        negative_words = ['hate', 'terrible', 'awful', 'bad', 'horrible']
        
        pos_count = sum(1 for word in positive_words if word in text)
        neg_count = sum(1 for word in negative_words if word in text)
        
        score = (pos_count - neg_count) / max(pos_count + neg_count, 1)
        
        if score > 0.2:
            sentiment = "positive"
        elif score < -0.2:
            sentiment = "negative"
        else:
            sentiment = "neutral"
        
        return SentimentOutput(sentiment=sentiment, score=score)
```

**3. Validate and test**
```bash
make validate-skill NAME=sentiment_analysis
make test-skill NAME=sentiment_analysis
```

**4. Register and run**
```bash
make register-skill NAME=sentiment_analysis
make run-skill NAME=sentiment_analysis INPUT='I love this product!'
```

### **Example 2: Text Translation Pipeline**

Create a pipeline that translates and summarizes:

```python
#!/usr/bin/env python3
"""Translation + Summarization Pipeline"""

import os
os.environ["OPENAI_API_KEY"] = "your-key"

from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.integrations.tasks import register_skills_and_agents

def translate_and_summarize(text: str, target_lang: str = "English") -> dict:
    """Translate text then summarize it."""
    
    register_skills_and_agents()
    registry = get_skill_registry()
    ctx = ExecutionContext(trace_id='pipeline', job_id='p1', agent_id='user')
    
    # Step 1: Translate
    print(f"📝 Original: {text}")
    translation = registry.execute(
        name='openai.translate',
        input_data={'text': text, 'target_language': target_lang},
        context=ctx
    )
    translated_text = translation['translated_text']
    print(f"🌍 Translated: {translated_text}")
    
    # Step 2: Summarize
    summary = registry.execute(
        name='text.summarize',
        input_data={'text': translated_text},
        context=ctx
    )
    print(f"📊 Summary: {summary['summary']}")
    
    return {
        'original': text,
        'translated': translated_text,
        'summary': summary['summary']
    }

if __name__ == "__main__":
    result = translate_and_summarize(
        text="خرسهای کثیف به تو می اندیشند. این یک اصطلاح فارسی است.",
        target_lang="English"
    )
    print(f"\n🎉 Complete Result: {result}")
```

Run it:
```bash
.venv/bin/python translation_pipeline.py
```

### **Example 3: Batch Processing with Make**

Create `batch_translate.sh`:
```bash
#!/bin/bash
# Batch translation script

export OPENAI_API_KEY="your-key"

echo "🌍 Batch Translation Starting..."

# Array of texts to translate
texts=(
    "Hello, world!"
    "How are you today?"
    "I love programming with Python"
    "Artificial Intelligence is amazing"
)

# Target languages
languages=("Spanish" "Persian" "French" "Arabic")

# Process each text
for i in "${!texts[@]}"; do
    echo ""
    echo "==================================="
    echo "Text $((i+1)): ${texts[$i]}"
    echo "Target: ${languages[$i]}"
    echo "==================================="
    
    make run-skill NAME=openai.translate INPUT="${texts[$i]}" TARGET_LANG="${languages[$i]}" 2>&1 | grep "✅ Result"
done

echo ""
echo "🎉 Batch translation complete!"
```

Run it:
```bash
chmod +x batch_translate.sh
./batch_translate.sh
```

---

## 🎨 Advanced Patterns

### **Pattern 1: Skill Composition**

Chain multiple skills together:

```python
def analyze_multilingual_sentiment(text: str, source_lang: str = "auto") -> dict:
    """Translate to English, then analyze sentiment."""
    
    registry = get_skill_registry()
    ctx = ExecutionContext(trace_id='multi', job_id='m1', agent_id='user')
    
    # Translate to English first
    if source_lang != "English":
        translation = registry.execute(
            name='openai.translate',
            input_data={'text': text, 'target_language': 'English'},
            context=ctx
        )
        english_text = translation['translated_text']
    else:
        english_text = text
    
    # Analyze sentiment
    sentiment = registry.execute(
        name='sentiment_analysis',
        input_data={'text': english_text},
        context=ctx
    )
    
    return {
        'original': text,
        'translated': english_text,
        'sentiment': sentiment['sentiment'],
        'score': sentiment['score']
    }
```

### **Pattern 2: Error Handling & Retries**

```python
def robust_translate(text: str, target_lang: str, max_retries: int = 3) -> str:
    """Translate with automatic retries."""
    
    for attempt in range(max_retries):
        try:
            result = registry.execute(
                name='openai.translate',
                input_data={'text': text, 'target_language': target_lang},
                context=ctx
            )
            return result['translated_text']
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"Retry {attempt + 1}/{max_retries}: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
```

### **Pattern 3: Caching Results**

```python
from functools import lru_cache
import hashlib

@lru_cache(maxsize=100)
def cached_translate(text: str, target_lang: str) -> str:
    """Cache translation results to save API calls."""
    result = registry.execute(
        name='openai.translate',
        input_data={'text': text, 'target_language': target_lang},
        context=ctx
    )
    return result['translated_text']
```

### **Pattern 4: Bounded Autonomy Agent**

Create an agent that uses bounded autonomy:

```python
def safe_skill_development(task: str, files: list[str]) -> dict:
    """Develop a skill with bounded autonomy checks."""
    
    # P0: Context Gating
    print("🔍 P0: Analyzing context...")
    os.system(f"make plan TASK='{task}' FILES='{','.join(files)}'")
    
    proceed = input("Proceed with plan? (y/n): ")
    if proceed.lower() != 'y':
        return {'status': 'aborted', 'reason': 'User rejected plan'}
    
    # P1: Implementation (manual)
    print("\n📝 Implement your skill now...")
    input("Press Enter when implementation is complete...")
    
    # P1: Code Review
    print("\n🔍 P1: Reviewing code...")
    os.system(f"make review FILES='{','.join(files)}'")
    
    # P2: Compliance Check
    print("\n🔍 P2: Checking compliance...")
    os.system(f"make check-compliance FILES='{','.join(files)}'")
    
    return {'status': 'complete', 'files': files}
```

---

## 🐛 Troubleshooting

### **Problem: Skill not found**

```bash
# Check if skill is registered
make list-skills

# Register the skill
make register-skill NAME=my_skill

# Verify registration
make skill-info NAME=my_skill
```

### **Problem: Import errors**

```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Reinstall in development mode
make dev

# Check Python path
.venv/bin/python -c "import sys; print('\n'.join(sys.path))"
```

### **Problem: API key not set**

```bash
# Set it temporarily
export OPENAI_API_KEY="your-key"

# Or set it permanently in ~/.bashrc
echo 'export OPENAI_API_KEY="your-key"' >> ~/.bashrc
source ~/.bashrc
```

### **Problem: Tests failing**

```bash
# Run with verbose output
.venv/bin/pytest tests/unit/test_my_skill.py -v

# Run specific test
.venv/bin/pytest tests/unit/test_my_skill.py::test_execute_basic -v

# Run with debugging
.venv/bin/pytest tests/unit/test_my_skill.py -vv --tb=short
```

### **Problem: Validation errors**

```bash
# Check what's wrong
make validate-skill NAME=my_skill

# Common fixes:
# 1. Ensure class name is correct: MySkillSkill
# 2. Inherit from Skill base class
# 3. Implement all required methods
# 4. Use Pydantic models for input/output
```

---

## 📊 Quick Reference Card

### **Essential Commands**

```bash
# Create
make new-skill NAME=my_skill

# Validate
make validate-skill NAME=my_skill

# Test
make test-skill NAME=my_skill

# Register
make register-skill NAME=my_skill

# Run
make run-skill NAME=my_skill INPUT='text'

# Info
make skill-info NAME=my_skill
make list-skills
```

### **Bounded Autonomy Commands**

```bash
# Plan
make plan TASK='task description' FILES='path/to/files'

# Review
make review FILES='file1.py,file2.py'

# Check compliance
make check-compliance FILES='file1.py,file2.py'
```

### **File Locations**

```
src/agentic_system/skills/my_skill.py     # Implementation
tests/unit/test_my_skill_skill.py         # Tests
skills/my_skill/SKILL.md                  # Documentation
examples/my_skill_example.py              # Example usage
```

---

## 🎉 Summary

**You now have a complete workflow for:**

✅ **Creating skills** with `make new-skill`  
✅ **Validating** with `make validate-skill`  
✅ **Testing** with `make test-skill`  
✅ **Running** with `make run-skill`  
✅ **Safe development** with bounded autonomy (P0, P1, P2)  
✅ **Code review** with `make review`  
✅ **Compliance checking** with `make check-compliance`  

**Everything is integrated with make commands for a seamless experience!**

Try it now:
```bash
make new-skill NAME=my_awesome_skill
```

For more details:
- `make help` - See all commands
- `cat docs/SKILL_DEVELOPMENT.md` - Full development guide
- `cat RUN_SKILLS_GUIDE.md` - Detailed running guide
