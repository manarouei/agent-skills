import random
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from database.models import PhoneCode, User, WhiteListPhones
from tasks import send_verification_sms
from auth.rate_limit import SMSRateLimit
from models.auth import Token
from auth.utils import create_access_token, create_refresh_token
from fastapi import HTTPException, status


class VerificationService:
    """Service for handling SMS verification operations"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.code_expiration_minutes = 5

    async def generate_verification_code(self, phone_number: str):
        """
        Generate verification code and store it in the database

        Args:
            phone_number: The phone number to send code to

        Returns:
            tuple: (code, task_id) - The generated code and Celery task ID
        Raises:
        HTTPException: If phone number is not in whitelist
        """
        # Check if phone number is in whitelist
        # result = await self.db.execute(
        #     select(WhiteListPhones).where(WhiteListPhones.phone_number == phone_number)
        # )
        # if not result.scalars().first():
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="اجازه ورود به سامانه را ندارید."
        #     )
    
        # Check rate limits
        rate_limiter = SMSRateLimit(self.db)
        await rate_limiter.check_rate_limit(phone_number)

        # Generate code
        code = self._generate_random_code()

        # Store in database
        await self._store_verification_code(phone_number, code)

        # Send SMS
        task = send_verification_sms.delay(phone_number, code)

        return code, task.id

    async def verify_code(self, phone_number: str, code: str):
        """
        Verify a code for a phone number

        Args:
            phone_number: The phone number
            code: The verification code

        Returns:
            User: User object if verified, None otherwise
        """
        # Check if code is valid
        result = await self.db.execute(
            select(PhoneCode).where(PhoneCode.phone_number == phone_number)
        )
        code_record = result.scalars().first()

        if not code_record or not code_record.check_code(code):
            return None

        # Find or create user
        result = await self.db.execute(
            select(User).where(User.username == phone_number)
        )
        user = result.scalars().first()

        if not user:
            # Create new user
            user = User(
                id=str(uuid.uuid4()),
                username=phone_number,
                hashed_password="",  # No password needed for SMS auth
                is_active=True,
            )
            self.db.add(user)
            await self.db.commit()
            await self.db.refresh(user)

        return user

    def _generate_random_code(self):
        """Generate random 6-digit code"""
        return "".join(random.choices("0123456789", k=6))

    async def _store_verification_code(self, phone_number: str, code: str):
        """Store verification code in database"""
        expire_time = datetime.now(timezone.utc) + timedelta(
            minutes=self.code_expiration_minutes
        )
        now = datetime.now(timezone.utc)

        # Check if code already exists
        result = await self.db.execute(
            select(PhoneCode).where(PhoneCode.phone_number == phone_number)
        )
        existing_code = result.scalars().first()

        if existing_code:
            if (
                existing_code.tmp_code_sent_time is not None
                and existing_code.tmp_code_sent_time.date() != now.date()
            ):
                existing_code.tmp_code_sent_counter = 0
            existing_code.tmp_code = code
            existing_code.tmp_code_expire = expire_time
            existing_code.tmp_code_sent_time = now
            existing_code.tmp_code_sent_counter += 1
        else:
            # Create new code
            new_code = PhoneCode(
                id=str(uuid.uuid4()),
                phone_number=phone_number,
                tmp_code=code,
                tmp_code_expire=expire_time,
                tmp_code_sent_time=now,
                tmp_code_sent_counter=1,
            )
            self.db.add(new_code)

        await self.db.commit()


class TokenService:
    """Service for handling JWT token operations"""

    @staticmethod
    def generate_token_pair(user_id: str) -> Token:
        """
        Generate an access token and refresh token pair

        Args:
            user_id: The user ID

        Returns:
            Token: Token object containing access and refresh tokens
        """
        access_token = create_access_token(user_id)
        refresh_token = create_refresh_token(user_id)

        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
        )
