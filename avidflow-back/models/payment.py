from typing import Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class PaymentsPlans(BaseModel):
    id: int
    title: str
    nodes_limit: int
    price: int
    duration_days: int
    is_active: bool
    description: str
    created_at: datetime


class OrderCreateRequest(BaseModel):
    plan_id: int


class OrderResponse(BaseModel):
    id: int
    amount: int
    status: str
    created_at: datetime


class PlanSnapshotOut(BaseModel):
    name: Optional[str] = None
    nodes_limit: Optional[int] = None


class OrderRead(BaseModel):
    id: int
    amount: int
    tax: Optional[int] = None
    status: str
    created_at: datetime
    total_price: Optional[int] = None

    plan_snapshot: PlanSnapshotOut

    class Config:
        from_attributes = True

    @field_validator("plan_snapshot", mode="before")
    def extract_fields(cls, v: Any) -> Dict[str, Any]:
        if isinstance(v, dict):
            return {
                "name": v.get("title"),
                "nodes_limit": v.get("nodes_limit"),
            }
        return {}


class SubscriptionDetail(BaseModel):
    nodes_used: int
    nodes_limit: int
    start_date: datetime
    end_date: datetime
