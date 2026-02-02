from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from sqlalchemy import Column, Integer, DateTime, Boolean


class AbstractModel:
    id: int
    date_joined: Optional[datetime]
    last_login: Optional[datetime]
    is_active: bool 
    

class TimestampedModel(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

class NamedModel(TimestampedModel):
    name: str
    description: Optional[str] = None
