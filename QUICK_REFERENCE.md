# Quick Reference Guide

Essential commands and patterns for daily development.

## Setup (First Time)

```bash
# 1. Clone/navigate to project
cd /home/toni/agent-skills

# 2. Run quickstart (checks env, starts infra, installs deps)
./quickstart.sh

# 3. Edit .env and add your API key
nano .env  # Set AGENTIC_ANTHROPIC_API_KEY

# 4. Start services
make start-infra
```

## Daily Development

### Start Everything

```bash
# Terminal 1: Start infrastructure
make start-infra

# Terminal 2: Start API server
make start-api

# Terminal 3: Start Celery worker
make start-worker
```

### Quick Commands

```bash
make help           # Show all available commands
make test           # Run tests
make test-cov       # Run tests with coverage
make lint           # Check code style
make lint-fix       # Fix linting issues
make logs           # Show infrastructure logs
make check-health   # Check all services
make clean          # Clean build artifacts
```

## API Usage

### Create a Job

```bash
curl -X POST http://localhost:8000/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "simple_summarizer",
    "input": {
      "text": "Your long text here...",
      "max_words": 50
    },
    "idempotency_key": "optional-unique-key"
  }'
```

### Get Job Status

```bash
curl http://localhost:8000/v1/jobs/{job_id}
```

### Health Check

```bash
curl http://localhost:8000/health
```

### Interactive API Docs

Open in browser: http://localhost:8000/docs

## Environment Variables

```bash
# Required
AGENTIC_ANTHROPIC_API_KEY=sk-ant-...

# Common overrides
AGENTIC_LOG_LEVEL=DEBUG                    # More verbose logging
AGENTIC_LLM_MAX_TOKENS_CAP=2048            # Lower token limit
AGENTIC_LLM_DEFAULT_MAX_COST_USD=0.50      # Lower cost limit
AGENTIC_ANTHROPIC_DEFAULT_MODEL=claude-3-5-haiku-20241022  # Cheaper model
```

## Testing Patterns

### Run Specific Tests

```bash
pytest tests/unit/test_llm_gateway_skill.py       # Single file
pytest tests/unit/ -v                              # Unit tests only
pytest tests/integration/ -v                       # Integration tests only
pytest -k "budget"                                 # Tests matching "budget"
pytest --lf                                        # Last failed tests
```

### Run with Coverage

```bash
pytest --cov=agentic_system --cov-report=html
open htmlcov/index.html  # View coverage report
```

## Direct Skill Usage (No API/Celery)

```python
from agentic_system.runtime import ExecutionContext, get_skill_registry
from agentic_system.skills import LLMGatewaySkill, SummarizeSkill

# Setup
skill_registry = get_skill_registry()
skill_registry.register(LLMGatewaySkill())
skill_registry.register(SummarizeSkill())

# Create context
context = ExecutionContext(
    trace_id="test-trace",
    job_id="test-job",
    agent_id="test"
)

# Execute skill
result = skill_registry.execute(
    name="text.summarize",
    input_data={
        "text": "Your text here...",
        "max_words": 30
    },
    context=context
)

print(result["summary"])
```

## Common LLM Gateway Patterns

### Basic Call

```python
result = skill_registry.execute(
    name="llm.anthropic_gateway",
    input_data={
        "messages": [
            {"role": "user", "content": "What is 2+2?"}
        ],
        "max_tokens": 100
    },
    context=context
)
```

### With Budget

```python
result = skill_registry.execute(
    name="llm.anthropic_gateway",
    input_data={
        "messages": [{"role": "user", "content": "Question"}],
        "max_tokens": 100,
        "budget": {
            "max_cost_usd": 0.01,
            "max_output_tokens": 50
        }
    },
    context=context
)
```

### With Retry Support

```python
result = skill_registry.execute(
    name="llm.anthropic_gateway",
    input_data={
        "messages": [{"role": "user", "content": "Question"}],
        "max_tokens": 100,
        "idempotency_key": "my-unique-key-123"  # Enables retries
    },
    context=context
)
```

### With System Prompt

```python
result = skill_registry.execute(
    name="llm.anthropic_gateway",
    input_data={
        "system": "You are a helpful coding assistant.",
        "messages": [{"role": "user", "content": "Write a hello world in Python"}],
        "max_tokens": 200,
        "temperature": 0.7
    },
    context=context
)
```

## Adding a New Skill (Checklist)

- [ ] Create `src/agentic_system/skills/my_skill.py`
- [ ] Define `MySkillInput(BaseModel)` and `MySkillOutput(BaseModel)`
- [ ] Implement `MySkill(Skill)` class with all required methods
- [ ] Add to `src/agentic_system/skills/__init__.py`
- [ ] Register in `src/agentic_system/integrations/tasks.py`
- [ ] Create `tests/unit/test_my_skill.py`
- [ ] Create `skills/my_skill/SKILL.md` documentation
- [ ] Run tests: `pytest tests/unit/test_my_skill.py -v`

## Adding a New Agent (Checklist)

- [ ] Create `src/agentic_system/agents/my_agent.py`
- [ ] Define input/output models
- [ ] Implement `MyAgent(Agent)` class
- [ ] Add to `src/agentic_system/agents/__init__.py`
- [ ] Register in `src/agentic_system/integrations/tasks.py`
- [ ] Create tests
- [ ] Test via API: POST to `/v1/jobs` with new `agent_id`

## Debugging

### Check Logs

```bash
# API logs (stdout)
# Watch Terminal 2

# Worker logs
# Watch Terminal 3

# Infrastructure logs
make logs

# Job-specific logs (grep by job_id)
docker logs agentic-redis
```

### Check Job Store

```bash
redis-cli
> SELECT 0
> KEYS job:*
> GET job:your-job-id-here
```

### Check Celery Queue

```bash
# RabbitMQ Management UI
open http://localhost:15672  # guest/guest

# Or via CLI
celery -A agentic_system.integrations.tasks inspect active
celery -A agentic_system.integrations.tasks inspect stats
```

## Troubleshooting

### "Import could not be resolved"
```bash
pip install -e .  # Reinstall in editable mode
```

### "Job stuck in pending"
```bash
# Check worker is running
celery -A agentic_system.integrations.tasks inspect active

# Check RabbitMQ
make logs | grep rabbitmq
```

### "Redis connection refused"
```bash
make start-infra  # Ensure infrastructure is running
docker ps         # Check container status
```

### "Anthropic API error"
```bash
# Check API key
echo $AGENTIC_ANTHROPIC_API_KEY

# Check budget limits in .env
cat .env | grep LLM
```

## Useful URLs

- **API Docs**: http://localhost:8000/docs
- **API Redoc**: http://localhost:8000/redoc
- **RabbitMQ Management**: http://localhost:15672
- **Health Check**: http://localhost:8000/health

## Performance Tips

1. **Use cheaper models for testing**: Set `AGENTIC_ANTHROPIC_DEFAULT_MODEL=claude-3-5-haiku-20241022`
2. **Lower token limits**: Set conservative `max_tokens` values
3. **Enable budget controls**: Always set `budget.max_cost_usd`
4. **Use idempotency keys**: For safe retries on expensive operations
5. **Scale workers**: Run multiple Celery workers for parallel execution

## Production Checklist

- [ ] Set production environment: `AGENTIC_ENV=production`
- [ ] Use secure Redis/RabbitMQ credentials
- [ ] Enable HTTPS on API
- [ ] Set up log aggregation (CloudWatch, etc.)
- [ ] Configure monitoring and alerts
- [ ] Review and adjust all timeout values
- [ ] Set appropriate budget limits
- [ ] Enable API rate limiting
- [ ] Backup Redis regularly
- [ ] Document runbook for incidents

---

**Quick Links**:
- [README](README.md) - Full documentation
- [STRUCTURE](STRUCTURE.md) - Project structure
- [CHANGELOG](CHANGELOG.md) - Version history
- [LLM Gateway Docs](skills/llm_gateway/SKILL.md) - Skill documentation
