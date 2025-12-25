"""Celery application configuration."""
from celery import Celery

from agentic_system.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "agentic_system",
    broker=settings.rabbitmq_url,
    backend=settings.redis_url,
)

# Configure Celery with production-safe defaults
celery_app.conf.update(
    # Task execution
    task_time_limit=settings.celery_task_time_limit,  # Hard time limit
    task_soft_time_limit=settings.celery_task_soft_time_limit,  # Soft time limit
    task_acks_late=True,  # Acknowledge after task completes (safer)
    task_reject_on_worker_lost=True,  # Reject if worker dies
    worker_prefetch_multiplier=1,  # Process one task at a time (safer)
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    # Results
    result_expires=3600,  # Results expire after 1 hour
    result_backend_transport_options={"master_name": "mymaster"},
    # Timezone
    timezone="UTC",
    enable_utc=True,
)
