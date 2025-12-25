"""Health check routes."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict:
    """
    Health check endpoint.

    Returns:
        Status dict
    """
    return {
        "status": "healthy",
        "service": "agentic-system",
    }
