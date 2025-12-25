# LLM Gateway Skill

**Skill Name:** `llm.anthropic_gateway`  
**Version:** `1.0.0`  
**Side Effect:** `NETWORK`  
**Idempotent:** Conditional (when `idempotency_key` is provided)

## Purpose

The LLM Gateway Skill is the **centralized and exclusive** integration point for all Anthropic LLM API calls in the system. No other component should directly call Anthropic APIs.

This skill provides:
- Strict input/output contracts via Pydantic models
- Budget enforcement (cost, token limits)
- Safe retry logic with exponential backoff
- Centralized logging with redaction support
- Production-safe timeout handling

## Input Schema

```python
{
  "model": "claude-3-5-sonnet-20241022",  # Optional, uses default from settings
  "system": "You are a helpful assistant.",  # Optional system prompt
  "messages": [
    {
      "role": "user",
      "content": "Hello, world!"
    }
  ],
  "max_tokens": 256,  # REQUIRED - maximum tokens to generate
  "temperature": 0.2,  # Default 0.2, range [0, 1]
  "top_p": null,  # Optional, range [0, 1]
  "stop_sequences": null,  # Optional list of stop strings
  "timeout_s": null,  # Optional override for timeout
  "idempotency_key": null,  # Optional key for safe retries
  "budget": {
    "max_cost_usd": null,  # Optional cost limit
    "max_input_tokens": null,  # Optional input token limit
    "max_output_tokens": null  # Optional output token limit
  },
  "redact_prompt_in_logs": true  # Default true - redacts prompts from logs
}
```

## Output Schema

```python
{
  "text": "Generated response text",
  "model": "claude-3-5-sonnet-20241022",
  "usage": {
    "input_tokens": 10,
    "output_tokens": 25
  },
  "cost_usd_estimate": 0.00045,
  "raw": {
    "id": "msg_...",
    "type": "message",
    "role": "assistant",
    "stop_reason": "end_turn"
  }
}
```

## Budget Controls

### Pre-Call Checks (Fail Fast)

1. **Hard Token Cap**: `max_tokens` must not exceed `AGENTIC_LLM_MAX_TOKENS_CAP`
2. **Output Budget**: If `budget.max_output_tokens` is set, `max_tokens` must be ≤ it
3. **Input Budget**: If `budget.max_input_tokens` is set, estimated input tokens (chars/4 heuristic) must be ≤ it
4. **Cost Budget**: If `budget.max_cost_usd` or `AGENTIC_LLM_DEFAULT_MAX_COST_USD` is set, estimated cost must be ≤ it

### Post-Call Checks

1. **Actual Cost**: If `budget.max_cost_usd` is set and actual cost exceeds it, raises `BudgetExceededError`

All budget violations result in immediate failure with clear error messages.

## Retry Behavior

- **Default**: No retries
- **With `idempotency_key`**: Up to 2 retries on:
  - HTTP 429 (rate limit)
  - HTTP 5xx (server errors)
  - Timeout exceptions
- **Exponential Backoff**: 0.5s, 1.5s
- **Never Retry**: HTTP 4xx (except 429)

## Logging

Logs `llm_call_start` and `llm_call_end` with:
- `trace_id`, `job_id`, `agent_id`
- `skill_name`, `skill_version`
- `model`, `max_tokens`
- `usage.input_tokens`, `usage.output_tokens`
- `cost_usd_estimate`

**Redaction**: If `redact_prompt_in_logs=true` (default), does not log `system` or `messages` content. API keys are never logged.

## Configuration

Environment variables (via `.env`):

```bash
AGENTIC_ANTHROPIC_API_KEY=<your-key>  # REQUIRED
AGENTIC_ANTHROPIC_BASE_URL=https://api.anthropic.com
AGENTIC_ANTHROPIC_VERSION=2023-06-01
AGENTIC_ANTHROPIC_DEFAULT_MODEL=claude-3-5-sonnet-20241022
AGENTIC_LLM_MAX_TOKENS_CAP=4096
AGENTIC_LLM_DEFAULT_MAX_COST_USD=1.0
```

## Pricing

Default pricing map (override via `AGENTIC_LLM_PRICING_JSON`):

```json
{
  "claude-3-5-sonnet-20241022": {
    "input_per_1k": 0.003,
    "output_per_1k": 0.015
  },
  "claude-3-5-haiku-20241022": {
    "input_per_1k": 0.001,
    "output_per_1k": 0.005
  },
  "claude-3-opus-20240229": {
    "input_per_1k": 0.015,
    "output_per_1k": 0.075
  }
}
```

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
    name="llm.anthropic_gateway",
    input_data={
        "messages": [
            {"role": "user", "content": "What is 2+2?"}
        ],
        "max_tokens": 100,
        "budget": {
            "max_cost_usd": 0.01
        }
    },
    context=context
)

print(result["text"])
```

## Error Handling

- `BudgetExceededError`: Budget limit exceeded (pre or post call)
- `SkillTimeoutError`: Execution timeout
- `SkillValidationError`: Input/output validation failed
- `SkillError`: HTTP errors, network issues, or unexpected errors

All errors are logged with full trace context.

## Security Notes

- API keys are loaded from environment (SecretStr)
- Never log API keys or secrets
- `redact_prompt_in_logs=true` by default to prevent accidental logging of sensitive prompts
- `raw` response excludes sensitive fields

## Portability

This skill can be copied to another system. Required dependencies:
- `pydantic>=2.5.0`
- `httpx>=0.26.0`
- Runtime contracts (`SkillSpec`, `ExecutionContext`, `Skill` base class)
- Settings management with environment variables
