from typing import Optional, Annotated
from pydantic import BaseModel, EmailStr, StringConstraints, constr
from sqlalchemy import Column, String
from sqlalchemy.orm import validates
import re
from .base import AbstractModel

class UserBase(BaseModel):
    email: EmailStr
    username: str
    is_active: bool = True

class UserCreate(UserBase):
    password: str

class User(AbstractModel):
    username = Column(String, unique=True, index=True)
    email = Column(String, unique=True, nullable=True)
    first_name = Column(String(150), nullable=True)
    last_name = Column(String(150), nullable=True)
    phone_number = Column(String(11), unique=True)
    hashed_password = Column(String)

    @validates('phone_number')
    def validate_phone(self, key, value):
        if value and not re.match(r'09\d{9}', value):
            raise ValueError('Invalid phone number format')
        return value


class UserUpdateRequest(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    password: Annotated[str, StringConstraints(min_length=8)] | None = None
