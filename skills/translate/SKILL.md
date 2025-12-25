# Translate Skill

**Skill Name:** `translate`  
**Version:** `1.0.0`  
**Side Effect:** `NONE`  
**Idempotent:** Yes

## Purpose

TODO: Describe what this skill does and why it's useful.

## Input Schema

```python
{
  "text": "Input text to process"  # TODO: Update with actual fields
}
```

## Output Schema

```python
{
  "result": "Processing result"  # TODO: Update with actual fields
}
```

## Behavior

TODO: Describe the skill's behavior:
1. What processing does it perform?
2. What are the key steps?
3. What external services does it call (if any)?
4. What are the performance characteristics?

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

# Execute skill
result = skill_registry.execute(
    skill_name="translate",
    input_data={
        "text": "Hello, world!"
    },
    context=context,
)

print(result["result"])
```

## Error Handling

TODO: Document error conditions and how they're handled:
- What input validations are performed?
- What exceptions can be raised?
- What are the retry semantics (if any)?

## Testing

Run tests with:
```bash
make test-skill NAME=translate
```

## Notes

TODO: Add any additional notes:
- Known limitations
- Performance considerations
- Future enhancements
- Related skills
