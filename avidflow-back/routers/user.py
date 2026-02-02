from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from database.models import  User
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import UserUpdateRequest
from auth.dependencies import get_current_user, get_db_from_app
from auth.utils import get_password_hash


router = APIRouter()

@router.get("/me", response_model=Dict[str, Any])
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get information about the currently authenticated user"""
    return {
        "id": current_user.id,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "is_active": current_user.is_active,
    }


@router.put("/me", response_model=dict)
async def update_user_me(
    data: UserUpdateRequest,
    db: AsyncSession = Depends(get_db_from_app),
    current_user: User = Depends(get_current_user),
):
    updated = False

    # Update profile fields
    if data.first_name is not None:
        current_user.first_name = data.first_name
        updated = True
    if data.last_name is not None:
        current_user.last_name = data.last_name
        updated = True

    # Change password if requested
    if data.password:
        current_user.hashed_password = get_password_hash(data.password)
        updated = True

    if updated:
        await db.commit()
        await db.refresh(current_user)

    return {
        "id": current_user.id,
        "username": current_user.username,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "is_active": current_user.is_active,
    }
