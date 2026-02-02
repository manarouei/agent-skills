# GitHub Copilot Instructions for Workflow Automation API

## Project Overview
This is a workflow automation platform built with:
- **Framework**: FastAPI (async)
- **Task Queue**: Celery with RabbitMQ
- **Database**: PostgreSQL with SQLAlchemy (async)
- **Cache**: Redis
- **Authentication**: JWT-based

## Code Style Guidelines

### Python Standards
- Follow PEP 8 with 88-character line limit (Black formatter)
- Use type hints for all function signatures
- Prefer async/await patterns for I/O operations
- Use Pydantic models for request/response validation

### Naming Conventions
- `snake_case` for functions, variables, and module names
- `PascalCase` for class names
- `SCREAMING_SNAKE_CASE` for constants
- Prefix private methods with single underscore `_`

### Import Organization (isort profile: black)
1. Standard library imports
2. Third-party imports (fastapi, celery, sqlalchemy, pydantic)
3. Local application imports (routers, models, services, utils)

## Architecture Patterns

### API Endpoints (FastAPI)
```python
@router.post("/resource", response_model=ResponseSchema)
async def create_resource(
    data: CreateSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResponseSchema:
    """Create a new resource.
    
    Args:
        data: The resource creation data.
        db: Database session dependency.
        current_user: Authenticated user dependency.
    
    Returns:
        The created resource.
    
    Raises:
        HTTPException: If resource creation fails.
    """
```

### Celery Tasks
```python
@celery_app.task(bind=True, max_retries=3)
def process_workflow(self, workflow_id: str) -> dict:
    """Process a workflow asynchronously.
    
    Use exponential backoff for retries.
    """
    try:
        # Task implementation
        pass
    except Exception as exc:
        self.retry(exc=exc, countdown=2 ** self.request.retries)
```

### Database Models (SQLAlchemy)
```python
class Resource(Base):
    __tablename__ = "resources"
    
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
```

### Pydantic Schemas
```python
class ResourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    
    model_config = ConfigDict(from_attributes=True)
```

## Security Requirements

### ALWAYS
- Validate all user inputs with Pydantic
- Use parameterized queries (SQLAlchemy handles this)
- Hash passwords with bcrypt/argon2
- Verify JWT tokens on protected endpoints
- Sanitize data before logging

### NEVER
- Expose sensitive data in error messages
- Use raw SQL queries with string interpolation
- Store secrets in code (use environment variables)
- Trust client-side data without validation

## Error Handling
```python
from fastapi import HTTPException, status

# Standard error responses
raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Resource not found"
)

# For async database operations
try:
    async with db.begin():
        # operations
except IntegrityError:
    raise HTTPException(status_code=409, detail="Resource already exists")
```

## Testing Patterns
```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_resource(client: AsyncClient, auth_headers: dict):
    response = await client.post(
        "/api/v1/resource",
        json={"name": "test"},
        headers=auth_headers,
    )
    assert response.status_code == 201
```

## Performance Considerations
- Use `select_in_load` or `joined_load` for relationships
- Implement pagination for list endpoints
- Cache frequently accessed data in Redis
- Use background tasks for non-blocking operations

## Documentation
- Add docstrings to all public functions (Google style)
- Include type hints for better IDE support
- Document API endpoints with FastAPI's built-in docs

## Common Patterns in This Codebase

### Dependency Injection
```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
```

### Background Task Pattern
```python
from fastapi import BackgroundTasks

@router.post("/workflow/execute")
async def execute_workflow(
    workflow_id: str,
    background_tasks: BackgroundTasks,
):
    background_tasks.add_task(process_workflow_task, workflow_id)
    return {"status": "queued"}
```

## Review Focus Areas
When reviewing code, prioritize:
1. Security vulnerabilities (SQL injection, XSS, auth bypass)
2. Async/await correctness (no blocking calls in async context)
3. Error handling completeness
4. Type safety and validation
5. Performance implications (N+1 queries, missing indexes)
6. Test coverage for critical paths
