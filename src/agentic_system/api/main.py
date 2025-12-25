"""FastAPI application."""
from fastapi import FastAPI

from agentic_system.api.routes import health, jobs, n8n
from agentic_system.observability import setup_logging

# Setup logging
setup_logging()

# Create FastAPI app
app = FastAPI(
    title="Agentic System",
    description="Production-first agentic system with LLM gateway",
    version="0.1.0",
)

# Include routers
app.include_router(health.router, tags=["health"])
app.include_router(jobs.router, tags=["jobs"])
app.include_router(n8n.router, tags=["n8n"])


@app.get("/")
def root() -> dict:
    """Root endpoint."""
    return {
        "service": "agentic-system",
        "version": "0.1.0",
        "docs": "/docs",
    }
