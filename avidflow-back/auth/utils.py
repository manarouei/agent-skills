import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from datetime import datetime, timedelta
from jose import jwt, JWTError
from pydantic import BaseModel
from config import settings

ph = PasswordHasher()


class TokenPayload(BaseModel):
    sub: str  # User ID
    exp: datetime
    type: str  # Token type (access or refresh)
    jti: str  # JWT ID (unique identifier for the token)


def create_access_token(user_id: str) -> str:
    """
    Create a new JWT access token for a user

    Args:
        user_id: User identifier

    Returns:
        JWT access token as a string
    """
    expire = datetime.utcnow() + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": "access",
        "jti": secrets.token_hex(8),  # Generate a unique token ID
    }

    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )

    return encoded_jwt


def create_refresh_token(user_id: str) -> str:
    """
    Create a new JWT refresh token for a user

    Args:
        user_id: User identifier

    Returns:
        JWT refresh token as a string
    """
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": str(user_id),
        "exp": expire,
        "type": "refresh",
        "jti": secrets.token_hex(8),  # Generate a unique token ID
    }

    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )

    return encoded_jwt


def decode_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT token

    Args:
        token: JWT token string

    Returns:
        TokenPayload with decoded information

    Raises:
        JWTError: If token is invalid or expired
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )

        token_data = TokenPayload(
            sub=payload["sub"],
            exp=datetime.fromtimestamp(payload["exp"]),
            type=payload["type"],
            jti=payload.get("jti", ""),
        )

        return token_data
    except JWTError as e:
        raise JWTError(f"Invalid token: {str(e)}")


def verify_password(plain_password, hashed_password):
    try:
        return ph.verify(hashed_password, plain_password)
    except VerifyMismatchError:
        return False


def get_password_hash(password):
    return ph.hash(password)


def nedd_password_rehash(hasehd_password):
    return ph.check_needs_rehash(hasehd_password)


def hashed_password_generator(length=12):
    return get_password_hash(secrets.token_urlsafe(length))
