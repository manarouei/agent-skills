.PHONY: help install dev test lint clean start-infra stop-infra start-api start-worker

# Python executable (use venv if available, otherwise system python)
PYTHON := $(shell if [ -f .venv/bin/python ]; then echo .venv/bin/python; else echo python; fi)
PIP := $(PYTHON) -m pip

help:  ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo '══════════════════════════════════════════════════════════════'
	@echo '  AGENT SKILLS - DEVELOPMENT COMMANDS'
	@echo '══════════════════════════════════════════════════════════════'
	@echo ''
	@echo '📦 Setup & Installation'
	@echo '──────────────────────────────────────────────────────────────'
	@grep -E '^(install|dev|setup):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ''
	@echo '🧪 Testing & Quality'
	@echo '──────────────────────────────────────────────────────────────'
	@grep -E '^(test|test-cov|test-skill|test-skill-cov|lint|lint-fix):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ''
	@echo '🛠️  Skill Development'
	@echo '──────────────────────────────────────────────────────────────'
	@grep -E '^(new-skill|register-skill|validate-skill|list-skills|skill-info|skill-docs|all-skill-docs|skill-example|run-skill):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ''
	@echo '🤖 Bounded Autonomy'
	@echo '──────────────────────────────────────────────────────────────'
	@grep -E '^(plan|review|check-compliance|validate-changes|show-rules|show-templates|prompt-.*):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ''
	@echo '🚀 Infrastructure'
	@echo '──────────────────────────────────────────────────────────────'
	@grep -E '^(start-infra|stop-infra|start-api|start-worker|logs|check-health):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ''
	@echo '🧹 Utilities'
	@echo '──────────────────────────────────────────────────────────────'
	@grep -E '^(clean|help):.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ''
	@echo 'For skill development guide: cat docs/SKILL_DEVELOPMENT.md'
	@echo ''

install:  ## Install dependencies
	$(PIP) install -e .

dev:  ## Install dev dependencies
	$(PIP) install -e ".[dev]"

test:  ## Run tests
	$(PYTHON) -m pytest

test-cov:  ## Run tests with coverage
	$(PYTHON) -m pytest --cov=agentic_system --cov-report=html --cov-report=term

lint:  ## Run linter
	ruff check src/ tests/

lint-fix:  ## Fix linting issues
	ruff check --fix src/ tests/

clean:  ## Clean up build artifacts
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +

start-infra:  ## Start RabbitMQ and Redis
	docker compose up -d

stop-infra:  ## Stop infrastructure
	docker compose down

start-api:  ## Start FastAPI server (foreground)
	uvicorn agentic_system.api.main:app --reload --host 0.0.0.0 --port 8000

start-worker:  ## Start Celery worker (foreground)
	celery -A agentic_system.integrations.tasks worker --loglevel=info

logs:  ## Show infrastructure logs
	docker compose logs -f

check-health:  ## Check service health
	@echo "Checking services..."
	@curl -s http://localhost:8000/health | jq . || echo "❌ API not responding"
	@docker compose ps

setup:  ## Quick setup (run once)
	@./quickstart.sh

# Bounded Autonomy Commands

prompt-A0:  ## Generate A0 planning prompt
	python -m agentic_system.cli prompt --template A0

prompt-A1:  ## Generate A1 implementation prompt
	python -m agentic_system.cli prompt --template A1

check-compliance:  ## Check P0/P1/P2 compliance (requires --pr-files)
	@if [ -z "$(FILES)" ]; then \
		echo "Usage: make check-compliance FILES='file1.py,file2.py'"; \
		exit 1; \
	fi
	python -m agentic_system.cli check-compliance --pr-files "$(FILES)"

plan:  ## Generate plan with context gating (requires TASK, optional FILES)
	@if [ -z "$(TASK)" ]; then \
		echo "Usage: make plan TASK='your task description' [FILES='file1.py,file2.py']"; \
		exit 1; \
	fi
	@if [ -n "$(FILES)" ]; then \
		python -m agentic_system.cli plan --task "$(TASK)" --files "$(FILES)"; \
	else \
		python -m agentic_system.cli plan --task "$(TASK)"; \
	fi

review:  ## Review code changes (requires FILES)
	@if [ -z "$(FILES)" ]; then \
		echo "Usage: make review FILES='file1.py,file2.py'"; \
		exit 1; \
	fi
	python -m agentic_system.cli review --files "$(FILES)"

show-rules:  ## Show LLM rules
	@cat docs/LLM_RULES.md

show-templates:  ## Show LLM task templates
	@cat docs/LLM_TASK_TEMPLATES.md

validate-changes:  ## Validate current git changes
	@echo "Validating uncommitted changes..."
	@git diff --name-only | tr '\n' ',' | xargs -I {} python -m agentic_system.cli check-compliance --pr-files "{}"

# Skill Development Commands

new-skill:  ## Create a new skill from template (requires NAME)
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make new-skill NAME=my_skill"; \
		echo "Example: make new-skill NAME=translate"; \
		exit 1; \
	fi
	@echo "Creating new skill: $(NAME)..."
	@mkdir -p skills/$(NAME)
	@mkdir -p src/agentic_system/skills
	@mkdir -p tests/unit
	@$(PYTHON) -c "from agentic_system.dev_tools.skill_generator import generate_skill; generate_skill('$(NAME)')"
	@echo "✅ Skill created!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Edit src/agentic_system/skills/$(NAME).py - implement _execute()"
	@echo "  2. Edit skills/$(NAME)/SKILL.md - document the skill"
	@echo "  3. Run: make test-skill NAME=$(NAME)"
	@echo "  4. Run: make register-skill NAME=$(NAME)"

test-skill:  ## Test a specific skill (requires NAME)
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make test-skill NAME=my_skill"; \
		exit 1; \
	fi
	@echo "Testing skill: $(NAME)..."
	@$(PYTHON) -m pytest tests/unit/test_$(NAME)_skill.py -v

test-skill-cov:  ## Test skill with coverage (requires NAME)
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make test-skill-cov NAME=my_skill"; \
		exit 1; \
	fi
	@$(PYTHON) -m pytest tests/unit/test_$(NAME)_skill.py -v --cov=agentic_system.skills.$(NAME) --cov-report=term --cov-report=html

register-skill:  ## Register skill in system (requires NAME)
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make register-skill NAME=my_skill"; \
		exit 1; \
	fi
	@echo "Registering skill: $(NAME)..."
	@$(PYTHON) -c "from agentic_system.dev_tools.skill_generator import register_skill; register_skill('$(NAME)')"
	@echo "✅ Skill registered in integrations/tasks.py and __init__.py"

validate-skill:  ## Validate skill implementation (requires NAME)
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make validate-skill NAME=my_skill"; \
		exit 1; \
	fi
	@echo "Validating skill: $(NAME)..."
	@$(PYTHON) -c "from agentic_system.dev_tools.skill_validator import validate_skill; validate_skill('$(NAME)')"

list-skills:  ## List all skills in the system
	@echo "Available skills:"
	@$(PYTHON) -c "from agentic_system.runtime.registry import get_skill_registry; registry = get_skill_registry(); [print(f'  - {name} ({skill.spec().version})') for name, skill in sorted(registry._skills.items())]"

skill-info:  ## Show detailed info about a skill (requires NAME)
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make skill-info NAME=my_skill"; \
		exit 1; \
	fi
	@$(PYTHON) -c "from agentic_system.dev_tools.skill_inspector import inspect_skill; inspect_skill('$(NAME)')"

skill-docs:  ## Generate skill documentation (requires NAME)
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make skill-docs NAME=my_skill"; \
		exit 1; \
	fi
	@echo "Generating docs for skill: $(NAME)..."
	@cat skills/$(NAME)/SKILL.md

all-skill-docs:  ## Show all skill documentation
	@for dir in skills/*/; do \
		if [ -f "$$dir/SKILL.md" ]; then \
			echo ""; \
			echo "========================================"; \
			cat "$$dir/SKILL.md"; \
		fi; \
	done

skill-example:  ## Run skill example (requires NAME)
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make skill-example NAME=my_skill"; \
		exit 1; \
	fi
	@if [ -f "examples/$(NAME)_example.py" ]; then \
		$(PYTHON) examples/$(NAME)_example.py; \
	else \
		echo "No example found for $(NAME)"; \
		echo "Create one at: examples/$(NAME)_example.py"; \
	fi

run-skill:  ## Run a skill with input (requires NAME and INPUT, optional TARGET_LANG)
	@if [ -z "$(NAME)" ]; then \
		echo "Usage: make run-skill NAME=skill_name INPUT='your text'"; \
		echo ""; \
		echo "Examples:"; \
		echo "  make run-skill NAME=openai.translate INPUT='Hello' TARGET_LANG=Spanish"; \
		echo "  make run-skill NAME=openai.translate INPUT='خرسهای کثیف به تو می اندیشند' TARGET_LANG=English"; \
		echo "  make run-skill NAME=text.summarize INPUT='long text here'"; \
		exit 1; \
	fi
	@if [ -z "$(INPUT)" ]; then \
		echo "Error: INPUT is required"; \
		echo "Usage: make run-skill NAME=$(NAME) INPUT='your text here'"; \
		exit 1; \
	fi
	@echo "Running skill: $(NAME)"
	@echo "Input: $(INPUT)"
	@if [ ! -z "$(TARGET_LANG)" ]; then \
		echo "Target language: $(TARGET_LANG)"; \
		$(PYTHON) -c "import os; os.environ.setdefault('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY', '')); from agentic_system.runtime import ExecutionContext; from agentic_system.runtime.registry import get_skill_registry; from agentic_system.integrations.tasks import register_skills_and_agents; register_skills_and_agents(); registry = get_skill_registry(); ctx = ExecutionContext(trace_id='make-cmd', job_id='manual', agent_id='user'); result = registry.execute(name='$(NAME)', input_data={'text': '''$(INPUT)''', 'target_language': '$(TARGET_LANG)'}, context=ctx); print('\n✅ Result:', result.get('translated_text', result.get('result', result)))"; \
	else \
		$(PYTHON) -c "import os; os.environ.setdefault('OPENAI_API_KEY', os.getenv('OPENAI_API_KEY', '')); from agentic_system.runtime import ExecutionContext; from agentic_system.runtime.registry import get_skill_registry; from agentic_system.integrations.tasks import register_skills_and_agents; register_skills_and_agents(); registry = get_skill_registry(); ctx = ExecutionContext(trace_id='make-cmd', job_id='manual', agent_id='user'); result = registry.execute(name='$(NAME)', input_data={'text': '''$(INPUT)'''}, context=ctx); print('\n✅ Result:', result.get('translated_text', result.get('result', result)))"; \
	fi

