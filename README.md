# Agentic System

Production-first agentic system with centralized LLM Gateway, built with FastAPI, Celery, RabbitMQ, and Redis.

## Overview

This system implements a production-ready agentic architecture with the following key principles:

- **KISS**: Minimal abstractions, readable code, testable components
- **Production-first**: Hard timeouts, step limits, safe retries, idempotency
- **Explicit contracts**: Pydantic v2 models everywhere
- **Observability**: Structured JSON logs with trace context
- **Centralized LLM access**: Single gateway skill for all Anthropic API calls with budget controls

## Architecture

```
┌─────────────────┐
│   FastAPI API   │  ← HTTP endpoints (jobs, n8n webhook, health)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  ExecutionStore │  ← Redis-backed job storage with idempotency
│     (Redis)     │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Celery Worker  │  ← Async job execution
│   (RabbitMQ)    │
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Agent Runtime  │  ← Orchestrates skills
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  Skill Registry │  ← LLM Gateway + Summarize + more
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│ LLM Gateway     │  ← ONLY place that calls Anthropic API
│ (Anthropic)     │     (budget controls, retries, logging)
└─────────────────┘
```

## Key Features

### 1. LLM Gateway Skill (`llm.anthropic_gateway`)

The **centralized and exclusive** integration point for Anthropic API:

- ✅ Strict input/output schemas with Pydantic
- ✅ Budget enforcement (cost, input/output token limits)
- ✅ Safe retry logic (only with `idempotency_key`)
- ✅ Centralized logging with prompt redaction
- ✅ Production-safe timeouts

See [`skills/llm_gateway/SKILL.md`](skills/llm_gateway/SKILL.md) for full documentation.

### 2. Execution Store

Redis-backed job storage with:

- ✅ Job status tracking (pending → running → completed/failed)
- ✅ Idempotency via `idempotency_key` (24h TTL)
- ✅ Full audit trail (created_at, updated_at)

### 3. Structured Logging

JSON logs with trace context:

```json
{
  "timestamp": "2025-12-20T10:30:45",
  "level": "INFO",
  "logger": "agentic_system.skills.llm_gateway",
  "message": "llm_call_end",
  "trace_id": "trace-abc123",
  "job_id": "job-def456",
  "agent_id": "simple_summarizer",
  "skill_name": "llm.anthropic_gateway",
  "skill_version": "1.0.0",
  "model": "claude-3-5-sonnet-20241022",
  "input_tokens": 50,
  "output_tokens": 100,
  "cost_usd_estimate": 0.0015
}
```

### 4. Production Defaults

- Hard task timeouts (5 min default)
- Step limits for agents (10 steps default)
- Safe Celery settings (acks_late, prefetch=1)
- No automatic retries (explicit via `idempotency_key`)

## Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for RabbitMQ & Redis)

### Installation

1. **Clone repository** (or use this as a starting point):

```bash
cd /home/toni/agent-skills
```

2. **Install dependencies**:

```bash
pip install -e ".[dev]"
```

3. **Copy environment file**:

```bash
cp .env.example .env
```

4. **Edit `.env`** and set required variables:

```bash
# REQUIRED: Add your Anthropic API key
AGENTIC_ANTHROPIC_API_KEY=your-anthropic-api-key-here
```

5. **Start infrastructure** (RabbitMQ + Redis):

```bash
docker compose up -d
```

Verify services:
- RabbitMQ Management UI: http://localhost:15672 (guest/guest)
- Redis: `redis-cli ping` should return `PONG`

## Running

### Start FastAPI Server

```bash
uvicorn agentic_system.api.main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: http://localhost:8000/docs

### Start Celery Worker

In a separate terminal:

```bash
celery -A agentic_system.integrations.tasks worker --loglevel=info
```

## Usage

### Create a Job via API

```bash
curl -X POST http://localhost:8000/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "simple_summarizer",
    "input": {
      "text": "The quick brown fox jumps over the lazy dog. This is a longer text that needs to be summarized into a shorter form while preserving the key information.",
      "max_words": 20
    },
    "idempotency_key": "my-unique-key-123"
  }'
```

Response:

```json
{
  "job_id": "a1b2c3d4-...",
  "agent_id": "simple_summarizer",
  "status": "pending",
  "trace_id": "trace-xyz",
  "created_at": "2025-12-20T10:30:00Z",
  "updated_at": "2025-12-20T10:30:00Z"
}
```

### Check Job Status

```bash
curl http://localhost:8000/v1/jobs/a1b2c3d4-...
```

Response when completed:

```json
{
  "job_id": "a1b2c3d4-...",
  "agent_id": "simple_summarizer",
  "status": "completed",
  "trace_id": "trace-xyz",
  "result": {
    "summary": "The quick brown fox jumps over the lazy dog. A longer text summarized..."
  },
  "error": null,
  "created_at": "2025-12-20T10:30:00Z",
  "updated_at": "2025-12-20T10:30:05Z"
}
```

### Health Check

```bash
curl http://localhost:8000/health
```

## Testing

Run all tests:

```bash
pytest
```

Run specific test categories:

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage
pytest --cov=agentic_system --cov-report=html
```

**Note**: Some tests require Redis to be running (use test DB 1):

```bash
docker compose up -d redis
```

## Configuration

All configuration via environment variables (prefix `AGENTIC_`):

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AGENTIC_ANTHROPIC_API_KEY` | ✅ Yes | - | Anthropic API key |
| `AGENTIC_ANTHROPIC_DEFAULT_MODEL` | No | `claude-3-5-sonnet-20241022` | Default model |
| `AGENTIC_LLM_MAX_TOKENS_CAP` | No | `4096` | Hard cap on max_tokens |
| `AGENTIC_LLM_DEFAULT_MAX_COST_USD` | No | `None` | Default cost limit per call |
| `AGENTIC_REDIS_URL` | No | `redis://localhost:6379/0` | Redis connection URL |
| `AGENTIC_RABBITMQ_URL` | No | `amqp://guest:guest@localhost:5672//` | RabbitMQ connection URL |
| `AGENTIC_LOG_LEVEL` | No | `INFO` | Logging level |
| `AGENTIC_DEFAULT_SKILL_TIMEOUT_S` | No | `30` | Default skill timeout |
| `AGENTIC_DEFAULT_AGENT_STEP_LIMIT` | No | `10` | Default agent step limit |
| `AGENTIC_CELERY_TASK_TIME_LIMIT` | No | `300` | Celery hard timeout (seconds) |
| `AGENTIC_CELERY_TASK_SOFT_TIME_LIMIT` | No | `270` | Celery soft timeout (seconds) |

See [`.env.example`](.env.example) for full list.

## Project Structure

```
agentic-system/
├── pyproject.toml              # Dependencies and build config
├── docker-compose.yml          # RabbitMQ + Redis
├── .env.example                # Environment variable template
├── README.md                   # This file
├── src/agentic_system/
│   ├── config/
│   │   └── settings.py         # Pydantic settings
│   ├── observability/
│   │   └── logging.py          # Structured JSON logging
│   ├── storage/
│   │   └── execution_store.py  # Redis job storage
│   ├── runtime/
│   │   ├── contracts.py        # Core contracts (SkillSpec, AgentSpec, etc.)
│   │   ├── skill.py            # Base Skill class
│   │   ├── agent.py            # Base Agent class
│   │   ├── registry.py         # Skill & Agent registries
│   │   └── runner.py           # Agent execution
│   ├── skills/
│   │   ├── llm_gateway.py      # LLM Gateway skill (Anthropic)
│   │   └── summarize.py        # Summarize skill (uses LLM Gateway)
│   ├── agents/
│   │   └── simple_summarizer.py # Simple summarizer agent
│   ├── integrations/
│   │   ├── celery_app.py       # Celery configuration
│   │   └── tasks.py            # Celery tasks + registration
│   └── api/
│       ├── main.py             # FastAPI app
│       └── routes/
│           ├── health.py       # Health check
│           ├── jobs.py         # Job management
│           └── n8n.py          # N8N webhook
├── skills/                     # Portable skill documentation
│   ├── llm_gateway/SKILL.md
│   └── summarize/SKILL.md
└── tests/
    ├── conftest.py             # Test fixtures
    ├── unit/
    │   ├── test_llm_gateway_skill.py
    │   └── test_summarize_skill.py
    └── integration/
        └── test_job_api.py
```

## Adding New Skills

1. **Create skill file** in `src/agentic_system/skills/`:

```python
from pydantic import BaseModel, Field
from agentic_system.runtime import Skill, SkillSpec, SideEffect, ExecutionContext

class MySkillInput(BaseModel):
    param: str = Field(..., description="Input parameter")

class MySkillOutput(BaseModel):
    result: str = Field(..., description="Output result")

class MySkill(Skill):
    def spec(self) -> SkillSpec:
        return SkillSpec(
            name="my.skill",
            version="1.0.0",
            side_effect=SideEffect.NONE,
            timeout_s=30,
            idempotent=True,
        )

    def input_model(self) -> type[BaseModel]:
        return MySkillInput

    def output_model(self) -> type[BaseModel]:
        return MySkillOutput

    def _execute(self, input_data: MySkillInput, context: ExecutionContext) -> MySkillOutput:
        # Implement skill logic
        return MySkillOutput(result=f"Processed: {input_data.param}")
```

2. **Register skill** in `src/agentic_system/integrations/tasks.py`:

```python
from agentic_system.skills.my_skill import MySkill

def register_skills_and_agents():
    skill_registry = get_skill_registry()
    
    # ... existing registrations ...
    
    my_skill = MySkill()
    skill_registry.register(my_skill)
```

3. **Add tests** in `tests/unit/test_my_skill.py`

4. **Document skill** in `skills/my_skill/SKILL.md`

## Adding New Agents

1. **Create agent file** in `src/agentic_system/agents/`:

```python
from pydantic import BaseModel
from agentic_system.runtime import Agent, AgentSpec, ExecutionContext
from agentic_system.runtime.registry import get_skill_registry

class MyAgentInput(BaseModel):
    # Define inputs
    pass

class MyAgentOutput(BaseModel):
    # Define outputs
    pass

class MyAgent(Agent):
    def spec(self) -> AgentSpec:
        return AgentSpec(
            agent_id="my_agent",
            version="1.0.0",
            step_limit=5,
            description="My custom agent",
        )

    def input_model(self) -> type[BaseModel]:
        return MyAgentInput

    def output_model(self) -> type[BaseModel]:
        return MyAgentOutput

    def _run(self, input_data: MyAgentInput, context: ExecutionContext) -> MyAgentOutput:
        self._check_step_limit()
        
        # Call skills via registry
        skill_registry = get_skill_registry()
        result = skill_registry.execute("my.skill", {...}, context)
        
        return MyAgentOutput(...)
```

2. **Register agent** in `src/agentic_system/integrations/tasks.py`

## Production Deployment

### Environment Variables

Set all required variables in production:

```bash
export AGENTIC_ENV=production
export AGENTIC_ANTHROPIC_API_KEY=<secret>
export AGENTIC_REDIS_URL=redis://<host>:6379/0
export AGENTIC_RABBITMQ_URL=amqp://<user>:<pass>@<host>:5672//
export AGENTIC_LOG_LEVEL=INFO
```

### Scaling Celery Workers

```bash
# Start multiple workers
celery -A agentic_system.integrations.tasks worker \
  --concurrency=4 \
  --loglevel=info \
  --max-tasks-per-child=1000
```

### Monitoring

- Monitor Redis: `redis-cli info stats`
- Monitor RabbitMQ: http://<host>:15672
- Monitor Celery: Use Flower (`pip install flower`)

```bash
celery -A agentic_system.integrations.tasks flower --port=5555
```

### Logging

All logs are JSON-formatted and go to stdout. Use your log aggregation tool (e.g., CloudWatch, Datadog, ELK) to collect and analyze.

Example log query patterns:
- Find all LLM calls: `skill_name="llm.anthropic_gateway"`
- Find expensive calls: `cost_usd_estimate > 0.01`
- Trace a specific job: `job_id="..."`

## Security Notes

- Never commit `.env` or API keys
- API keys are loaded as `SecretStr` (not logged)
- Prompt redaction enabled by default (`redact_prompt_in_logs=true`)
- Use HTTPS in production
- Consider rate limiting on API endpoints
- Run Redis/RabbitMQ with authentication in production

## Troubleshooting

### Job stuck in "pending"

- Check Celery worker is running: `celery -A agentic_system.integrations.tasks inspect active`
- Check RabbitMQ queues: http://localhost:15672/#/queues
- Check worker logs for errors

### LLM Gateway budget errors

- Check `AGENTIC_LLM_MAX_TOKENS_CAP` setting
- Check `budget.max_cost_usd` in request
- Review pricing map in settings

### Import errors

Make sure package is installed in editable mode:

```bash
pip install -e .
```

## License

MIT (or your preferred license)

## Contributing

1. Create feature branch
2. Add tests for new functionality
3. Ensure `pytest` passes
4. Update documentation
5. Submit pull request

---

**Built with KISS principles for production reliability.**
