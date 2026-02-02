from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime
from uuid import UUID

# Model for credential properties
class CredentialProperty(BaseModel):
    name: str
    displayName: str
    type: str = "string"
    default: Any = None
    required: bool = False
    description: Optional[str] = None
    options: Optional[List[Dict[str, Any]]] = None

# Model for credential types
class CredentialType(BaseModel):
    name: str
    displayName: str
    properties: List[CredentialProperty]
    is_oauth2: bool = False
    authenticate: Optional[Dict[str, Any]] = None

# Model for creating credentials
class CredentialCreate(BaseModel):
    name: str
    type: str
    data: Dict[str, Any]

# Model for updating credentials
class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

# Owner information
class CredentialOwner(BaseModel):
    id: str
    firstName: Optional[str] = None
    lastName: Optional[str] = None
    email: Optional[str] = None

# Model for credential responses
class CredentialResponse(BaseModel):
    id: str
    name: str
    type: str
    data: Optional[Dict[str, Any] | str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    sharedWith: Optional[List[Any]] = None

# Model for testing credentials
class CredentialTest(BaseModel):
    type: str
    data: Dict[str, Any]

# Existing credential model
class CredentialModel(BaseModel):
    id: Optional[UUID] = None
    name: str = Field(..., min_length=1, max_length=128)
    type: str = Field(..., description="Type of credential")
    data: str = Field(..., description="Encrypted credential data")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
