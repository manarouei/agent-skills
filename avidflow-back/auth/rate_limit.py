from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone, timedelta
from database.models import PhoneCode

class SMSRateLimit:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.max_per_day = 10
        self.min_interval_seconds = 120  # 2 minute between SMS

    async def check_rate_limit(self, phone_number: str):
        """
        Check if the phone number has exceeded rate limits
        
        Args:
            phone_number: The phone number to check
            
        Raises:
            HTTPException: If rate limit is exceeded
        """
        # Get the phone code record if it exists
        result = await self.db.execute(
            select(PhoneCode).where(PhoneCode.phone_number == phone_number)
        )
        code_record = result.scalars().first()
        
        if not code_record:
            return
        
        # Check daily limit
        now = datetime.now(timezone.utc)
        if (
                code_record.tmp_code_sent_time is not None
                and code_record.tmp_code_sent_time.date() != now.date()
            ):
            return
        
        if (code_record.tmp_code_sent_counter >= self.max_per_day and 
            code_record.tmp_code_sent_time.date() == now.date()):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"محدودیت در ارسال پیامک"
            )
        
        # Check interval between requests
        if code_record.tmp_code_sent_time:
            seconds_since_last = (now - code_record.tmp_code_sent_time).total_seconds()
            if seconds_since_last < self.min_interval_seconds:
                wait_seconds = self.min_interval_seconds - seconds_since_last
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"لطفا برای {int(wait_seconds)} ثانیه صبر کنید."
                )