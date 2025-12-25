# 🚀 Running Skills with Make Commands

## ✅ YES! You can now run skills directly with `make`!

---

## 📋 Quick Reference

### **Run Any Skill**
```bash
make run-skill NAME=skill_name INPUT='your text'
```

### **Run Translation**
```bash
make run-skill NAME=openai.translate INPUT='text' TARGET_LANG=language
```

---

## 🌍 Translation Examples

### **Persian to English** (Your text!)
```bash
export OPENAI_API_KEY="your-key"
make run-skill NAME=openai.translate INPUT='خرسهای کثیف به تو می اندیشند' TARGET_LANG=English
```

**Output:** `Dirty bears are thinking of you.`

### **English to Spanish**
```bash
make run-skill NAME=openai.translate INPUT='Hello, how are you?' TARGET_LANG=Spanish
```

**Output:** `Hola, ¿cómo estás?`

### **English to Persian**
```bash
make run-skill NAME=openai.translate INPUT='I love AI' TARGET_LANG=Persian
```

**Output:** `من عاشق هوش مصنوعی هستم`

### **English to Arabic**
```bash
make run-skill NAME=openai.translate INPUT='Python is amazing' TARGET_LANG=Arabic
```

**Output:** `بايثون رائع`

### **English to French**
```bash
make run-skill NAME=openai.translate INPUT='Good morning' TARGET_LANG=French
```

**Output:** `Bonjour`

---

## 🎯 All Available Make Commands

### **Skill Execution**
```bash
# Run a skill directly
make run-skill NAME=openai.translate INPUT='text' TARGET_LANG=Spanish

# Run skill example script
make skill-example NAME=translate
```

### **Skill Development**
```bash
# Create new skill
make new-skill NAME=my_skill

# Validate skill
make validate-skill NAME=my_skill

# Test skill
make test-skill NAME=my_skill

# Get skill info
make skill-info NAME=my_skill

# List all skills
make list-skills
```

### **Other Commands**
```bash
# Show help
make help

# Run all tests
make test

# Run with coverage
make test-cov
```

---

## ⚡ Super Quick Translation (Bash Functions)

Load the quick translate functions:
```bash
source quick_translate.sh
```

Then use simple commands:

```bash
# Translate to any language
translate 'Hello' Spanish

# Quick shortcuts
to_english 'خرسهای کثیف به تو می اندیشند'
to_spanish 'Good morning'
to_persian 'I love programming'
to_arabic 'Artificial Intelligence'
to_french 'Thank you'
```

---

## 🔧 Environment Setup

### **Set API Key Permanently**

Add to your `~/.bashrc` or `~/.zshrc`:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

Then reload:
```bash
source ~/.bashrc
```

### **Set API Key Temporarily**
```bash
export OPENAI_API_KEY="your-key"
make run-skill NAME=openai.translate INPUT='text' TARGET_LANG=English
```

---

## 📊 All Skills You Can Run

| Skill Name | Description | Example |
|------------|-------------|---------|
| `openai.translate` | Translate text between languages | `make run-skill NAME=openai.translate INPUT='Hello' TARGET_LANG=Spanish` |
| `translate` | Anthropic-powered translation | `make run-skill NAME=translate INPUT='Hello' TARGET_LANG=en` |
| `text.summarize` | Summarize long text | `make run-skill NAME=text.summarize INPUT='long text'` |
| `system.healthcheck` | Check system health | `make run-skill NAME=system.healthcheck INPUT=''` |
| `llm.anthropic_gateway` | Direct LLM access | (requires messages format) |
| `context_gate` | Bounded autonomy context check | (requires specific format) |
| `code_review` | Code review analysis | (requires code input) |

---

## 🎨 Custom Skill Runner Script

For more complex inputs, create a runner script:

```python
#!/usr/bin/env python3
"""Custom skill runner"""

import os
os.environ["OPENAI_API_KEY"] = "your-key"

from agentic_system.runtime import ExecutionContext
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.integrations.tasks import register_skills_and_agents

register_skills_and_agents()
registry = get_skill_registry()
ctx = ExecutionContext(trace_id='custom', job_id='job', agent_id='user')

# Run skill
result = registry.execute(
    name='openai.translate',
    input_data={
        'text': 'Your text here',
        'target_language': 'Spanish'
    },
    context=ctx
)

print(result['translated_text'])
```

Save as `run_my_skill.py` and run:
```bash
.venv/bin/python run_my_skill.py
```

---

## 💡 Pro Tips

### **1. Use Make for Quick Tests**
```bash
make run-skill NAME=openai.translate INPUT='test' TARGET_LANG=Spanish
```

### **2. Use Bash Functions for Interactive Work**
```bash
source quick_translate.sh
to_english 'خرسهای کثیف'
```

### **3. Use Python Scripts for Complex Logic**
```python
# For batch processing, pipelines, etc.
result = registry.execute(...)
```

### **4. Chain Skills Together**
```python
# Translate then summarize
translation = registry.execute(name='openai.translate', ...)
summary = registry.execute(name='text.summarize', input_data={'text': translation['translated_text']}, ...)
```

---

## 🐛 Troubleshooting

### **Error: "Skill not found"**
```bash
# Check available skills
make list-skills

# Make sure skill is registered
make skill-info NAME=openai.translate
```

### **Error: "OPENAI_API_KEY not set"**
```bash
# Set it before running
export OPENAI_API_KEY="your-key"
make run-skill ...
```

### **Error: "Module 'openai' not found"**
```bash
# Install OpenAI package
.venv/bin/pip install openai
```

---

## 🎉 Summary

**YES!** You can now run skills with make commands:

✅ **Simple**: `make run-skill NAME=openai.translate INPUT='text' TARGET_LANG=Spanish`  
✅ **Fast**: Bash functions loaded with `source quick_translate.sh`  
✅ **Powerful**: Full Python API for complex workflows  
✅ **Flexible**: Works with all registered skills  

**Your Persian text "خرسهای کثیف به تو می اندیشند" translates to "Dirty bears are thinking of you"!** 🐻✨

Try it now:
```bash
export OPENAI_API_KEY="your-key"
make run-skill NAME=openai.translate INPUT='خرسهای کثیف به تو می اندیشند' TARGET_LANG=English
```
