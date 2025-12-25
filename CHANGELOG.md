# Changelog

All notable changes to this project will be documented in this file.

## [0.1.0] - 2025-12-20

### Added - Initial Release

#### Core Infrastructure
- **Configuration Management**: Pydantic-based settings with environment variable support
- **Structured Logging**: JSON logging with trace context (trace_id, job_id, agent_id)
- **Execution Store**: Redis-backed job storage with idempotency support
- **Docker Compose**: RabbitMQ + Redis infrastructure setup

#### Runtime System
- **Skill Base Class**: Validation, timeout enforcement, error handling
- **Agent Base Class**: Step limits, orchestration support
- **Skill Registry**: Dependency injection for skills
- **Agent Registry**: Dependency injection for agents
- **Execution Context**: Trace context propagation
- **Contracts**: SkillSpec, AgentSpec, SideEffect enums

#### LLM Gateway Skill (v1.0.0)
- **Centralized Anthropic Integration**: ONLY place that calls Anthropic API
- **Budget Controls**: 
  - Pre-call cost estimation and enforcement
  - Token limits (input, output, hard cap)
  - Post-call budget verification
- **Safe Retries**: Exponential backoff with idempotency key
- **Logging**: Centralized with prompt redaction support
- **Input Validation**: Strict Pydantic schemas
- **Pricing Map**: Configurable model pricing with sensible defaults

#### Skills
- **Summarize Skill (v1.0.0)**: Text summarization using LLM Gateway
- **HealthCheck Skill (v1.0.0)**: Simple diagnostic skill with no side effects

#### Agents
- **Simple Summarizer Agent (v1.0.0)**: Orchestrates summarization workflow

#### API
- **FastAPI Application**: REST API with auto-generated docs
- **Job Management**:
  - `POST /v1/jobs` - Create and enqueue job
  - `GET /v1/jobs/{job_id}` - Get job status/result
- **N8N Integration**:
  - `POST /v1/n8n/webhook` - Webhook endpoint for n8n workflows
- **Health Check**:
  - `GET /health` - Service health status
  - `GET /` - Root endpoint with API info

#### Celery Integration
- **Celery Worker**: Async job execution
- **Production Defaults**:
  - Hard time limits (5 min)
  - Soft time limits (4.5 min)
  - acks_late=True (safer)
  - prefetch=1 (one task at a time)
- **Task Registration**: Automatic skill/agent registration on worker startup

#### Testing
- **Unit Tests**:
  - LLM Gateway budget enforcement
  - LLM Gateway response parsing
  - Summarize skill integration
  - Input validation
- **Integration Tests**:
  - Job creation API contract
  - Job retrieval
  - Idempotency verification
  - N8N webhook
  - Health checks
- **Test Fixtures**: pytest configuration with sample data

#### Documentation
- **README.md**: Complete setup and usage guide
- **STRUCTURE.md**: Detailed project structure documentation
- **LLM Gateway SKILL.md**: Comprehensive skill documentation
- **Summarize SKILL.md**: Skill usage and examples
- **.env.example**: Environment variable template

#### Developer Tools
- **Makefile**: Convenience commands for common tasks
- **quickstart.sh**: One-command setup script
- **example.py**: Runnable example demonstrating skill usage
- **.gitignore**: Python and IDE-specific ignores

### Dependencies
- FastAPI 0.109.0+
- Celery 5.3.0+
- Redis 5.0.0+
- Pydantic 2.5.0+
- httpx 0.26.0+
- python-json-logger 2.0.7+
- pytest 7.4.0+ (dev)
- ruff 0.1.0+ (dev)

### Architecture Decisions
1. **KISS Principle**: Minimal abstractions, explicit contracts, readable code
2. **Production-First**: Hard timeouts, safe retries, budget controls by default
3. **Centralized LLM Access**: Single gateway skill for all LLM calls
4. **Explicit Contracts**: Pydantic models for all inputs/outputs
5. **Observability**: Structured logging with trace context everywhere
6. **Idempotency**: First-class support via idempotency_key
7. **No Auto-Retry**: Retries only with explicit idempotency_key

### Security
- API keys stored as SecretStr (never logged)
- Prompt redaction enabled by default
- No secrets in job results
- Environment-based configuration

### Known Limitations
- Signal-based timeout only works on Unix (Linux/macOS)
- Simple token estimation (chars/4 heuristic)
- In-memory registries (reset on worker restart)
- No persistence for skill/agent registry

### Future Enhancements
- Async skill execution support
- Tool calling in LLM Gateway
- Streaming responses
- Multi-model support (OpenAI, etc.)
- Persistent skill registry
- Advanced rate limiting
- Job cancellation
- Job scheduling
- Webhook callbacks on job completion

---

## Release Notes Template

For future releases, use this format:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- New features

### Changed
- Changes to existing features

### Deprecated
- Features marked for removal

### Removed
- Removed features

### Fixed
- Bug fixes

### Security
- Security improvements
```

---

**Version**: 0.1.0  
**Status**: Production-ready baseline  
**Built**: 2025-12-20
