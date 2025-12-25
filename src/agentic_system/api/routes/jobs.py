"""Job management routes."""
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agentic_system.integrations.tasks import run_job
from agentic_system.observability import get_logger
from agentic_system.storage import get_execution_store

logger = get_logger(__name__)
router = APIRouter()


class CreateJobRequest(BaseModel):
    """Request model for creating a job."""

    agent_id: str = Field(..., description="Agent ID to execute")
    input: dict[str, Any] = Field(..., description="Input data for the agent")
    idempotency_key: str | None = Field(
        default=None,
        description="Optional idempotency key",
    )


class JobResponse(BaseModel):
    """Response model for job operations."""

    job_id: str = Field(..., description="Job ID")
    agent_id: str = Field(..., description="Agent ID")
    status: str = Field(..., description="Job status")
    trace_id: str = Field(..., description="Trace ID")
    result: dict[str, Any] | None = Field(
        default=None,
        description="Job result (if completed)",
    )
    error: str | None = Field(
        default=None,
        description="Error message (if failed)",
    )
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Update timestamp")


@router.post("/v1/jobs", response_model=JobResponse)
def create_job(request: CreateJobRequest) -> JobResponse:
    """
    Create and enqueue a new job.

    Args:
        request: Job creation request

    Returns:
        Job response with job_id and status
    """
    store = get_execution_store()

    # Create job
    job = store.create_job(
        agent_id=request.agent_id,
        input_data=request.input,
        idempotency_key=request.idempotency_key,
    )

    logger.info(
        "Job created via API",
        extra={
            "job_id": job.job_id,
            "agent_id": job.agent_id,
            "trace_id": job.trace_id,
        },
    )

    # Enqueue Celery task
    run_job.delay(job.job_id)

    return JobResponse(
        job_id=job.job_id,
        agent_id=job.agent_id,
        status=job.status.value,
        trace_id=job.trace_id,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


@router.get("/v1/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    """
    Get job status and result.

    Args:
        job_id: Job ID

    Returns:
        Job response

    Raises:
        HTTPException: If job not found
    """
    store = get_execution_store()
    job = store.get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobResponse(
        job_id=job.job_id,
        agent_id=job.agent_id,
        status=job.status.value,
        trace_id=job.trace_id,
        result=job.result,
        error=job.error,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
