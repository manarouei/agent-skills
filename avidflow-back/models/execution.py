from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Union, Literal, Any
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID
from .workflow import WorkflowBase


class ExecutionStatus(str, Enum):
    UNKNOWN = "unknown"
    CANCELED = "canceled"
    CRASHED = "crashed"
    NEW = "new"
    WAITING = "waiting"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class ExecutionData(BaseModel):
    workflow_data: WorkflowBase
    data: str


class ExecutionModel(BaseModel):
    id: Optional[UUID] = None
    workflow_id: UUID
    status: ExecutionStatus
    started_at: datetime
    stopped_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now(timezone.utc))


class ExecutionSummary(BaseModel):
    id: str
    workflow_id: str
    workflow_name: str
    status: str
    mode: str
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    finished: bool

    class Config:
        from_attributes = True