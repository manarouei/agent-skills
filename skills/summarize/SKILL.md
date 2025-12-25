# Summarize Skill

**Skill Name:** `text.summarize`  
**Version:** `1.0.0`  
**Side Effect:** `NETWORK` (calls LLM Gateway)  
**Idempotent:** No

## Purpose

The Summarize Skill generates concise summaries of text using the LLM Gateway skill.

## Input Schema

```python
{
  "text": "Long text to summarize...",  # Text to summarize (required)
  "max_words": 100  # Maximum words in summary (default: 100)
}
```

## Output Schema

```python
{
  "summary": "Concise summary of the text..."
}
```

## Behavior

1. Constructs a prompt with the input text and word limit constraint
2. Calls `llm.anthropic_gateway` skill with:
   - System prompt: "You are a helpful assistant that creates concise summaries."
   - User message: Text + word limit instruction
   - `max_tokens`: 256 (conservative)
   - `temperature`: 0.2 (low for consistency)
3. Post-processes the output to enforce word limit (truncates if needed)

## Usage Example

```python
from agentic_system.runtime.registry import get_skill_registry
from agentic_system.runtime import ExecutionContext

skill_registry = get_skill_registry()

context = ExecutionContext(
    trace_id="trace-123",
    job_id="job-456",
    agent_id="my_agent"
)

result = skill_registry.execute(
    name="text.summarize",
    input_data={
        "text": "The quick brown fox jumps over the lazy dog. " * 50,
        "max_words": 20
    },
    context=context
)

print(result["summary"])
```

## Dependencies

- Requires `llm.anthropic_gateway` skill to be registered
- Uses skill registry to call LLM Gateway (no direct imports)

## Error Handling

All errors from LLM Gateway are propagated (budget exceeded, timeout, validation errors, etc.)

## Portability

This skill can be copied to another system. Required:
- LLM Gateway skill registered in the skill registry
- Runtime contracts (`SkillSpec`, `ExecutionContext`, `Skill` base class)
