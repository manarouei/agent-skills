from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from uuid import UUID
from .connection import Connections
from .node import Node


class WorkflowBase(BaseModel):
    name: str
    description: Optional[str] = None
    nodes: List[Node]
    connections: Connections
    settings: Optional[Dict[str, Any]] = None
    pin_data: Optional[Dict[str, Any]] = None
    active: bool = False

# Model for creating a new workflow
class WorkflowCreate(WorkflowBase):
    """Used when creating a new workflow"""
    pass

# Model for updating an existing workflow
class WorkflowUpdate(BaseModel):
    """Used when updating an existing workflow"""
    name: Optional[str] = None
    description: Optional[str] = None
    nodes: Optional[List[Node]] = None
    connections: Optional[Connections] = None
    settings: Optional[Dict[str, Any]] = None
    pin_data: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None


# Complete Workflow model for responses
class WorkflowResponse(WorkflowBase):
    """Used for workflow responses"""
    id: str
    user_id: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    trigger_count: int = 0

    class Config:
        from_attributes = True


class WorkflowModel(BaseModel):
    id: str
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = None
    nodes: List[Node]
    connections: Connections
    active: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class CopyWorkflow(BaseModel):
    new_name: Optional[str] = None