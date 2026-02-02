from fastapi import APIRouter, Depends, HTTPException, status, Request, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import Dict, Any
from jose import JWTError

from database.models import User
from auth.dependencies import get_db_from_app
from auth.utils import (
    create_access_token,
    create_refresh_token,
    verify_password,
    get_password_hash,
    decode_token,
    nedd_password_rehash,
)
from services.auth import VerificationService, TokenService
from models.auth import PhoneVerification, Token, RefreshRequest, Phone, LoginRequest


router = APIRouter()


@router.post("/request-verification", response_model=Dict[str, Any])
async def request_verification(
    request: Request,
    phone: Phone,
    db: AsyncSession = Depends(get_db_from_app),
):
    """
    Request a verification code to be sent via SMS
    """
    # try:
    verification_service = VerificationService(db)
    _, task_id = await verification_service.generate_verification_code(
        phone.phone_number
    )
    return {
        "message": "Verification code sent",
    }


@router.post("/verify", response_model=Token)
async def verify_phone(
    request: Request,
    verification: PhoneVerification,
    db: AsyncSession = Depends(get_db_from_app),
):
    """
    Verify a phone number using the code sent via SMS and return JWT tokens
    """
    verification_service = VerificationService(db)
    user = await verification_service.verify_code(
        verification.phone_number, verification.code
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid verification code"
        )

    return TokenService.generate_token_pair(user.id)


@router.post("/refresh", response_model=Token)
async def refresh_token(
    request: Request,
    refresh_request: RefreshRequest,
    db: AsyncSession = Depends(get_db_from_app),
):
    """
    Get a new access token using a refresh token
    """
    try:
        # Decode and validate the refresh token

        token_data = decode_token(refresh_request.refresh_token)

        # Check if it's a refresh token
        if token_data.type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Get the user
        result = await db.execute(select(User).where(User.id == token_data.sub))
        user = result.scalars().first()

        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Generate new tokens
        access_token = create_access_token(user.id)
        refresh_token = create_refresh_token(user.id)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid refresh token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/login", response_model=Token)
async def login(
    request: Request,
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db_from_app),
):
    """
    Login with username and password, return JWT tokens.
    """
    result = await db.execute(select(User).where(User.username == login_data.username))
    user = result.scalars().first()
    if (
        not user
        or not user.hashed_password
        or not verify_password(login_data.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نام کاربری یا رمز عبور نامعتبر است.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="دسترسی شما به سامانه امکان پذیر نمی باشد.",
        )
    
    if nedd_password_rehash(user.hashed_password):
        user.hashed_password = get_password_hash(login_data.password)
        await db.commit()
        await db.refresh(user)
    
    return TokenService.generate_token_pair(user.id)


@router.post("/logout")
async def logout():
    """
    Logout the current user

    Note: For JWT-based authentication, server-side logout isn't typical since
    tokens are stateless. A full implementation would require token blacklisting.
    """
    # In a real implementation, you would add the token to a blacklist
    # For now, we'll just return a success message
    return {"message": "Successfully logged out"}
