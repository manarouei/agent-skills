from pydantic import BaseModel
from typing import Optional


class Phone(BaseModel):
    """Phone model"""

    phone_number: str


class PhoneVerification(BaseModel):
    """Phone verification request/check model"""

    phone_number: str
    code: str


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    """Token response model"""

    access_token: str
    refresh_token: str


class RefreshRequest(BaseModel):
    """Token refresh request model"""

    refresh_token: str
