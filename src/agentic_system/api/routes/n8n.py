"""N8N webhook integration routes."""
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from agentic_system.integrations.tasks import run_job
from agentic_system.observability import get_logger
from agentic_system.storage import get_execution_store

logger = get_logger(__name__)
router = APIRouter()


class N8NWebhookRequest(BaseModel):
    """Request model for N8N webhook."""

    agent_id: str = Field(..., description="Agent ID to execute")
    input: dict[str, Any] = Field(..., description="Input data for the agent")
    idempotency_key: str | None = Field(
        default=None,
        description="Optional idempotency key",
    )


class N8NWebhookResponse(BaseModel):
    """Response model for N8N webhook."""

    job_id: str = Field(..., description="Job ID")
    status: str = Field(..., description="Job status")
    trace_id: str = Field(..., description="Trace ID")


@router.post("/v1/n8n/webhook", response_model=N8NWebhookResponse)
def n8n_webhook(request: N8NWebhookRequest) -> N8NWebhookResponse:
    """
    N8N webhook endpoint - thin adapter to job creation.

    Args:
        request: Webhook request

    Returns:
        Webhook response with job_id and status
    """
    store = get_execution_store()

    # Create job (same contract as /v1/jobs)
    job = store.create_job(
        agent_id=request.agent_id,
        input_data=request.input,
        idempotency_key=request.idempotency_key,
    )

    logger.info(
        "Job created via N8N webhook",
        extra={
            "job_id": job.job_id,
            "agent_id": job.agent_id,
            "trace_id": job.trace_id,
        },
    )

    # Enqueue Celery task
    run_job.delay(job.job_id)

    return N8NWebhookResponse(
        job_id=job.job_id,
        status=job.status.value,
        trace_id=job.trace_id,
    )
