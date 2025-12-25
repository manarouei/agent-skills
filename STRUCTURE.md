# Project Structure

Complete file tree of the agentic system:

```
agentic-system/
├── .env.example                          # Environment variable template
├── .gitignore                            # Git ignore patterns
├── docker-compose.yml                    # RabbitMQ + Redis infrastructure
├── example.py                            # Example usage script (runnable)
├── Makefile                              # Convenience commands
├── pyproject.toml                        # Python project configuration
├── quickstart.sh                         # Quick setup script
├── README.md                             # Main documentation
│
├── src/agentic_system/                   # Main source code
│   ├── __init__.py                       # Root package
│   │
│   ├── config/                           # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py                   # Pydantic settings with env vars
│   │
│   ├── observability/                    # Logging and monitoring
│   │   ├── __init__.py
│   │   └── logging.py                    # JSON logging with trace context
│   │
│   ├── storage/                          # Data persistence
│   │   ├── __init__.py
│   │   └── execution_store.py            # Redis job storage with idempotency
│   │
│   ├── runtime/                          # Core runtime components
│   │   ├── __init__.py                   # Exports all runtime classes
│   │   ├── contracts.py                  # SkillSpec, AgentSpec, ExecutionContext
│   │   ├── skill.py                      # Base Skill class with validation
│   │   ├── agent.py                      # Base Agent class with step limits
│   │   ├── registry.py                   # Skill & Agent registries
│   │   ├── runner.py                     # Agent execution runner
│   │   └── context.py                    # Execution context (re-export)
│   │
│   ├── skills/                           # Skill implementations
│   │   ├── __init__.py                   # Exports all skills
│   │   ├── llm_gateway.py                # LLM Gateway (Anthropic) - CORE SKILL
│   │   ├── summarize.py                  # Text summarization (uses LLM Gateway)
│   │   └── healthcheck.py                # Simple healthcheck (no side effects)
│   │
│   ├── agents/                           # Agent implementations
│   │   ├── __init__.py
│   │   └── simple_summarizer.py          # Simple summarizer agent
│   │
│   ├── integrations/                     # External integrations
│   │   ├── __init__.py
│   │   ├── celery_app.py                 # Celery configuration
│   │   └── tasks.py                      # Celery tasks + skill/agent registration
│   │
│   └── api/                              # FastAPI application
│       ├── __init__.py
│       ├── main.py                       # FastAPI app with routes
│       └── routes/
│           ├── __init__.py
│           ├── health.py                 # GET /health
│           ├── jobs.py                   # POST/GET /v1/jobs
│           └── n8n.py                    # POST /v1/n8n/webhook
│
├── skills/                               # Portable skill documentation
│   ├── llm_gateway/
│   │   └── SKILL.md                      # LLM Gateway documentation
│   └── summarize/
│       └── SKILL.md                      # Summarize skill documentation
│
└── tests/                                # Test suite
    ├── conftest.py                       # Pytest configuration and fixtures
    ├── unit/                             # Unit tests
    │   ├── test_llm_gateway_skill.py     # LLM Gateway tests (mocked)
    │   └── test_summarize_skill.py       # Summarize skill tests
    └── integration/                      # Integration tests
        └── test_job_api.py               # API endpoint tests
```

## Key Files

### Configuration & Setup
- **`.env.example`**: Template for environment variables
- **`docker-compose.yml`**: Infrastructure (RabbitMQ, Redis)
- **`pyproject.toml`**: Python dependencies and project metadata
- **`Makefile`**: Convenience commands (`make help` to see all)
- **`quickstart.sh`**: One-command setup script

### Core Runtime
- **`runtime/contracts.py`**: Data models (SkillSpec, AgentSpec, ExecutionContext)
- **`runtime/skill.py`**: Base Skill class with validation and timeout
- **`runtime/agent.py`**: Base Agent class with step limits
- **`runtime/registry.py`**: Skill and Agent registries (dependency injection)

### LLM Gateway (Most Important)
- **`skills/llm_gateway.py`**: The ONLY place that calls Anthropic API
  - Budget controls (cost, tokens)
  - Safe retries with idempotency
  - Centralized logging with redaction
  - Strict input/output schemas

### Storage & Observability
- **`storage/execution_store.py`**: Redis-backed job storage with idempotency
- **`observability/logging.py`**: Structured JSON logging with trace context

### API & Tasks
- **`api/main.py`**: FastAPI application
- **`integrations/tasks.py`**: Celery tasks and skill/agent registration

### Tests
- **`tests/unit/test_llm_gateway_skill.py`**: Budget tests, response parsing
- **`tests/integration/test_job_api.py`**: API contract tests

## File Count

- **Python files**: 33 (including tests)
- **Documentation**: 4 (README, 2 SKILL.md, this file)
- **Configuration**: 5 (pyproject.toml, docker-compose, .env.example, .gitignore, Makefile)
- **Scripts**: 2 (quickstart.sh, example.py)

**Total: 44 files**

## Package Architecture

```
agentic_system
    ├── config          → Settings management
    ├── observability   → Logging
    ├── storage         → Job persistence
    ├── runtime         → Core abstractions (Skill, Agent, Registry)
    ├── skills          → Skill implementations (LLM Gateway, Summarize, etc.)
    ├── agents          → Agent implementations
    ├── integrations    → Celery, external systems
    └── api             → FastAPI REST API
```

## Dependencies

### Production
- **FastAPI**: REST API framework
- **Celery**: Async task queue
- **Redis**: Job storage + Celery backend
- **RabbitMQ**: Message broker for Celery
- **Pydantic**: Data validation
- **httpx**: HTTP client for Anthropic API
- **python-json-logger**: JSON logging

### Development
- **pytest**: Testing framework
- **pytest-asyncio**: Async test support
- **ruff**: Linting and formatting
- **httpx**: Test client for FastAPI

## Extension Points

### Adding a New Skill
1. Create `src/agentic_system/skills/my_skill.py`
2. Inherit from `Skill` base class
3. Implement `spec()`, `input_model()`, `output_model()`, `_execute()`
4. Register in `integrations/tasks.py`
5. Add tests in `tests/unit/test_my_skill.py`
6. Document in `skills/my_skill/SKILL.md`

### Adding a New Agent
1. Create `src/agentic_system/agents/my_agent.py`
2. Inherit from `Agent` base class
3. Implement `spec()`, `input_model()`, `output_model()`, `_run()`
4. Register in `integrations/tasks.py`
5. Add tests

### Adding a New API Endpoint
1. Create `src/agentic_system/api/routes/my_route.py`
2. Define Pydantic request/response models
3. Include router in `api/main.py`
4. Add integration tests in `tests/integration/`

## Production Checklist

- [ ] Set all environment variables in production
- [ ] Use secure Redis/RabbitMQ credentials
- [ ] Enable HTTPS for API
- [ ] Set up log aggregation (CloudWatch, Datadog, etc.)
- [ ] Monitor Celery workers
- [ ] Set up alerts for failed jobs
- [ ] Review and adjust budget limits
- [ ] Set appropriate timeout values
- [ ] Enable rate limiting on API endpoints
- [ ] Backup Redis data regularly

## Security Notes

- API keys stored as `SecretStr` (not logged)
- Prompts redacted by default in logs
- No secrets in job results
- Use environment variables for all sensitive config
- Run infrastructure with authentication in production

---

**Status**: ✅ Complete and ready for use

**Next Steps**: 
1. Run `./quickstart.sh` to set up
2. Start API and worker
3. Test with example requests
4. Extend with your own skills and agents
