"""Redis-backed execution store for job management."""
import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

import redis
from pydantic import BaseModel, Field

from agentic_system.config import get_settings
from agentic_system.observability import get_logger

logger = get_logger(__name__)


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobRecord(BaseModel):
    """Job record stored in Redis."""

    job_id: str = Field(..., description="Unique job ID")
    agent_id: str = Field(..., description="Agent ID that processes this job")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Job status")
    input_data: dict[str, Any] = Field(..., description="Input data for the job")
    result: dict[str, Any] | None = Field(default=None, description="Job result")
    error: str | None = Field(default=None, description="Error message if failed")
    trace_id: str = Field(..., description="Trace ID for observability")
    idempotency_key: str | None = Field(
        default=None,
        description="Idempotency key for deduplication",
    )
    created_at: str = Field(..., description="ISO timestamp when job was created")
    updated_at: str = Field(..., description="ISO timestamp when job was last updated")


class ExecutionStore:
    """Redis-backed store for job execution state."""

    def __init__(self, redis_client: redis.Redis | None = None):
        """
        Initialize execution store.

        Args:
            redis_client: Optional Redis client (will create one if not provided)
        """
        if redis_client is None:
            settings = get_settings()
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
            )
        else:
            self.redis_client = redis_client

        self._job_prefix = "job:"
        self._idempotency_prefix = "idempotency:"

    def _job_key(self, job_id: str) -> str:
        """Get Redis key for job."""
        return f"{self._job_prefix}{job_id}"

    def _idempotency_key(self, key: str) -> str:
        """Get Redis key for idempotency."""
        return f"{self._idempotency_prefix}{key}"

    def create_job(
        self,
        agent_id: str,
        input_data: dict[str, Any],
        trace_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> JobRecord:
        """
        Create a new job with idempotency support.

        Args:
            agent_id: Agent ID to process the job
            input_data: Input data for the job
            trace_id: Optional trace ID (generated if not provided)
            idempotency_key: Optional idempotency key for deduplication

        Returns:
            JobRecord for the created (or existing) job

        Raises:
            Exception: If job creation fails
        """
        # Check for existing job with same idempotency key
        if idempotency_key:
            existing_job_id = self.redis_client.get(
                self._idempotency_key(idempotency_key)
            )
            if existing_job_id:
                logger.info(
                    "Job already exists for idempotency key",
                    extra={
                        "idempotency_key": idempotency_key,
                        "job_id": existing_job_id,
                    },
                )
                existing_job = self.get_job(existing_job_id)
                if existing_job:
                    return existing_job

        # Create new job
        job_id = str(uuid.uuid4())
        if trace_id is None:
            trace_id = str(uuid.uuid4())

        now = datetime.now(timezone.utc).isoformat()

        job = JobRecord(
            job_id=job_id,
            agent_id=agent_id,
            status=JobStatus.PENDING,
            input_data=input_data,
            trace_id=trace_id,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )

        # Store job
        self.redis_client.set(
            self._job_key(job_id),
            job.model_dump_json(),
        )

        # Store idempotency mapping if provided
        if idempotency_key:
            # Store for 24 hours
            self.redis_client.setex(
                self._idempotency_key(idempotency_key),
                86400,
                job_id,
            )

        logger.info(
            "Job created",
            extra={
                "job_id": job_id,
                "agent_id": agent_id,
                "trace_id": trace_id,
                "has_idempotency_key": idempotency_key is not None,
            },
        )

        return job

    def get_job(self, job_id: str) -> JobRecord | None:
        """
        Get job by ID.

        Args:
            job_id: Job ID

        Returns:
            JobRecord if found, None otherwise
        """
        job_data = self.redis_client.get(self._job_key(job_id))
        if job_data is None:
            return None

        return JobRecord.model_validate_json(job_data)

    def set_status(
        self,
        job_id: str,
        status: JobStatus,
        error: str | None = None,
    ) -> None:
        """
        Update job status.

        Args:
            job_id: Job ID
            status: New status
            error: Optional error message (for FAILED status)
        """
        job = self.get_job(job_id)
        if job is None:
            logger.error("Job not found", extra={"job_id": job_id})
            return

        job.status = status
        job.updated_at = datetime.now(timezone.utc).isoformat()

        if error:
            job.error = error

        self.redis_client.set(
            self._job_key(job_id),
            job.model_dump_json(),
        )

        logger.info(
            "Job status updated",
            extra={
                "job_id": job_id,
                "status": status.value,
                "has_error": error is not None,
            },
        )

    def set_result(
        self,
        job_id: str,
        result: dict[str, Any],
    ) -> None:
        """
        Set job result and mark as completed.

        Args:
            job_id: Job ID
            result: Job result data
        """
        job = self.get_job(job_id)
        if job is None:
            logger.error("Job not found", extra={"job_id": job_id})
            return

        job.status = JobStatus.COMPLETED
        job.result = result
        job.updated_at = datetime.now(timezone.utc).isoformat()

        self.redis_client.set(
            self._job_key(job_id),
            job.model_dump_json(),
        )

        logger.info(
            "Job completed",
            extra={"job_id": job_id, "trace_id": job.trace_id},
        )


def get_execution_store() -> ExecutionStore:
    """Get or create execution store instance."""
    return ExecutionStore()
