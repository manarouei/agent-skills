# AI-Assisted Code Review Guidelines

> **Based on**: [Graphite's AI Code Review Best Practices](https://graphite.com/guides/ai-code-review-implementation-best-practices)
> **Tailored for**: Python/FastAPI/Celery/RabbitMQ Backend
> **Repository**: [GitLab - Avid Workflow](https://gitlab.zaris-dev.ir/avid/workflow/back)
> **Primary Branch**: `develop`

---

## Table of Contents

1. [Overview](#overview)
2. [AI Review Scope](#ai-review-scope)
3. [Human Review Focus](#human-review-focus)
4. [GitHub Copilot Workflow](#github-copilot-workflow)
5. [VS Code Integration](#vs-code-integration)
6. [Evaluating AI Suggestions](#evaluating-ai-suggestions)
7. [Security-First Mindset](#security-first-mindset)
8. [Performance Patterns](#performance-patterns)
9. [Measuring Success](#measuring-success)
10. [Common Challenges](#common-challenges)
11. [Team Adoption Checklist](#team-adoption-checklist)

---

## Overview

This guide establishes a **human-in-the-loop** approach to AI-assisted code review, combining automated tooling with human expertise for optimal code quality.

### Key Principles

| Principle | Description |
|-----------|-------------|
| **Complementary** | AI assists but doesn't replace human reviewers |
| **Actionable** | Focus on high-impact, fixable issues |
| **Continuous** | Learn from accepted/rejected suggestions |
| **Security-First** | Prioritize security in all AI suggestions |

---

## AI Review Scope

### ✅ What AI Should Review

| Category | Examples |
|----------|----------|
| **Style Consistency** | PEP 8, Black formatting, import ordering |
| **Basic Logic Errors** | Undefined variables, unreachable code, type mismatches |
| **Security Scanning** | SQL injection, hardcoded secrets, insecure defaults |
| **Performance Patterns** | N+1 queries, missing `async`/`await`, inefficient loops |
| **Documentation** | Missing docstrings, outdated comments |
| **Test Coverage** | Untested edge cases, missing assertions |

### ❌ What Requires Human Review

| Category | Why AI Falls Short |
|----------|-------------------|
| **Architecture Decisions** | Lacks project context and long-term vision |
| **Business Logic** | Doesn't understand domain requirements |
| **Complex Algorithms** | May miss subtle correctness issues |
| **Team Conventions** | Custom patterns not in training data |
| **External Integrations** | Can't verify API contracts or behavior |

---

## Human Review Focus

When AI handles routine checks, human reviewers should prioritize:

### 1. FastAPI-Specific Concerns
```python
# Review: Is this endpoint properly secured?
@router.post("/admin/users")
async def create_admin_user(
    data: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),  # ← Human verifies auth logic
):
    ...

# Review: Is the dependency injection correct?
# Review: Are rate limits appropriate for this endpoint?
```

### 2. Celery Task Safety
```python
@celery_app.task(bind=True, max_retries=3)
def process_workflow(self, workflow_id: str):
    # Human reviews:
    # - Is retry logic appropriate?
    # - What happens if RabbitMQ is down?
    # - Is idempotency handled?
    # - Are timeouts configured?
```

### 3. Database Transaction Boundaries
```python
async def transfer_credits(from_user: int, to_user: int, amount: int):
    async with db.begin():
        # Human reviews:
        # - Is the transaction isolation level correct?
        # - Are there race conditions?
        # - What happens on partial failure?
```

---

## GitHub Copilot Workflow

### In-Editor Review (VS Code)

1. **Before Writing Code**
   - Open relevant files to give Copilot context
   - Use `#file` references in Copilot Chat for specific questions

2. **While Writing Code**
   - Accept suggestions that match project patterns
   - Question suggestions that seem overly complex
   - Use `/explain` for unfamiliar patterns

3. **During Self-Review**
   ```
   Copilot Chat Commands:
   
   /explain    - Understand complex code sections
   /fix        - Get suggestions for fixing errors
   /tests      - Generate test cases
   @workspace  - Ask questions about the codebase
   ```

### Copilot Chat Prompts for Code Review

```markdown
# Security Review
"Review this FastAPI endpoint for security vulnerabilities, 
especially SQL injection, authentication bypass, and input validation."

# Performance Review  
"Analyze this function for N+1 query patterns and suggest 
SQLAlchemy eager loading improvements."

# Async Correctness
"Check if this async function has any blocking calls that 
should be awaited or run in an executor."

# Test Coverage
"What edge cases should I test for this Celery task? Consider 
failure scenarios and retry behavior."
```

---

## VS Code Integration

### Recommended Extensions

| Extension | Purpose |
|-----------|---------|
| **GitHub Copilot** | AI code suggestions |
| **GitHub Copilot Chat** | Interactive AI assistance |
| **Pylance** | Python type checking |
| **Ruff** | Fast Python linting |
| **GitLens** | Git history and blame |

### Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Accept Copilot suggestion | `Tab` |
| Show next suggestion | `Alt + ]` |
| Show previous suggestion | `Alt + [` |
| Open Copilot Chat | `Ctrl + Shift + I` |
| Inline Chat | `Ctrl + I` |

### Settings (`.vscode/settings.json`)

Already configured in your workspace with:
- Python type checking enabled
- Format on save with Black
- Import sorting with isort
- Copilot enabled for all Python files

---

## Evaluating AI Suggestions

Use this framework to assess AI recommendations:

| AI Suggestion | Assessment | Action |
|--------------|------------|--------|
| "Replace synchronous file operations with async" | Valid performance concern | **Accept** - Use `aiofiles` |
| "Add null check for parameter" | Pydantic already validates | **Decline** - Explain in comment |
| "Use more descriptive variable name" | Subjective but improves clarity | **Accept** |
| "Restructure entire class hierarchy" | Too broad, needs discussion | **Defer** - Team meeting |
| "Remove unused import" | Auto-fixable | **Accept** - Let pre-commit handle |
| "Change database isolation level" | Complex implications | **Review** - Manual verification |

### Red Flags in AI Suggestions

⚠️ **Be Cautious When AI Suggests**:
- Removing authentication/authorization checks
- Changing database transaction boundaries
- Modifying Celery task retry logic
- Altering error handling in critical paths
- Updating security-sensitive configurations

---

## Security-First Mindset

### AI-Generated Code Checklist

Before accepting AI suggestions that handle:

#### User Input
- [ ] Input validated with Pydantic schemas
- [ ] No direct string interpolation in queries
- [ ] File uploads sanitized and size-limited

#### Authentication
- [ ] JWT tokens properly verified
- [ ] Rate limiting applied
- [ ] Session management secure

#### Database Queries
- [ ] Using SQLAlchemy ORM (parameterized)
- [ ] No raw SQL with user data
- [ ] Proper transaction handling

#### External APIs
- [ ] Secrets from environment variables
- [ ] Timeouts configured
- [ ] Error responses don't leak info

---

## Performance Patterns

### Common Issues AI Should Catch

```python
# ❌ N+1 Query Pattern (AI should flag)
async def get_workflows_with_nodes(db: AsyncSession):
    workflows = await db.execute(select(Workflow))
    for workflow in workflows.scalars():
        nodes = await db.execute(
            select(Node).where(Node.workflow_id == workflow.id)
        )  # N+1 query!

# ✅ Eager Loading (AI should suggest)
async def get_workflows_with_nodes(db: AsyncSession):
    result = await db.execute(
        select(Workflow).options(selectinload(Workflow.nodes))
    )
    return result.scalars().all()
```

```python
# ❌ Blocking in Async (AI should flag)
async def process_file(file_path: str):
    with open(file_path, 'r') as f:  # Blocking!
        content = f.read()

# ✅ Async File Operations
async def process_file(file_path: str):
    async with aiofiles.open(file_path, 'r') as f:
        content = await f.read()
```

---

## Measuring Success

### Metrics to Track

| Metric | Target | How to Measure |
|--------|--------|----------------|
| **Bug Reduction** | -30% in 6 months | Production incident count |
| **Review Time** | -40% per PR | PR open-to-merge time |
| **Security Issues** | Zero critical | Security scan results |
| **AI Acceptance Rate** | 60-70% | Track accept/reject ratio |
| **Developer Satisfaction** | 4+/5 | Quarterly surveys |

### Weekly Review Questions

1. What AI suggestions were most valuable this week?
2. What false positives should we configure away?
3. Are there patterns AI keeps missing that we should document?
4. Which team members need more AI tooling training?

---

## Common Challenges

| Challenge | Solution |
|-----------|----------|
| **False positives overwhelming** | Tune `.pre-commit-config.yaml` ignore rules |
| **AI missing context-specific issues** | Update `.github/copilot-instructions.md` |
| **Team resistance** | Start with opt-in, share success metrics |
| **Slow skill development** | Use AI suggestions as teaching moments |
| **Inconsistent adoption** | Pair programming sessions with AI tools |

---

## Team Adoption Checklist

### Phase 1: Setup (Week 1)
- [ ] Install VS Code extensions (Copilot, Pylance, Ruff)
- [ ] Install dev tools: `pip install pip-tools pre-commit`
- [ ] Sync dependencies: `pip-sync requirements.txt`
- [ ] Run `pre-commit install` in repository
- [ ] Review `.github/copilot-instructions.md`
- [ ] Test Copilot Chat with simple queries

### Phase 2: Pilot (Weeks 2-3)
- [ ] Use AI review on non-critical MRs
- [ ] Document false positives encountered
- [ ] Share useful Copilot Chat prompts
- [ ] Collect initial feedback from team

### Phase 3: Rollout (Weeks 4-6)
- [ ] Enable AI review for all MRs
- [ ] Configure GitLab CI checks (`.gitlab-ci.yml`)
- [ ] Establish metrics tracking
- [ ] Weekly retrospectives on AI effectiveness

### Phase 4: Optimization (Ongoing)
- [ ] Tune rule sensitivity monthly
- [ ] Update copilot-instructions quarterly
- [ ] Share learnings across teams
- [ ] Evaluate new AI tools as they emerge

---

## Quick Reference Card

### Copilot Chat Commands
```
/explain  - Understand code
/fix      - Fix errors
/tests    - Generate tests
/doc      - Generate docs
@workspace - Search codebase
```

### Pre-commit Commands
```bash
pre-commit install          # Setup hooks
pre-commit run --all-files  # Run all checks
pre-commit autoupdate       # Update hooks
```

### Package Management (pip-tools)
```bash
pip-compile requirements.in  # Generate requirements.txt from .in file
pip-sync requirements.txt    # Install exact dependencies
```

### Review Priority
1. 🔴 Security vulnerabilities
2. 🟠 Async/await correctness
3. 🟡 Error handling
4. 🟢 Type safety
5. 🔵 Performance
6. ⚪ Style/formatting

---

## Resources

- [Graphite AI Code Review Guide](https://graphite.com/guides/ai-code-review-implementation-best-practices)
- [GitHub Copilot Documentation](https://docs.github.com/en/copilot)
- [FastAPI Best Practices](https://fastapi.tiangolo.com/advanced/)
- [Celery Best Practices](https://docs.celeryq.dev/en/stable/userguide/tasks.html#best-practices)
- [SQLAlchemy Async Guide](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

---

*Last Updated: December 2024*
*Maintainer: Backend Team*
