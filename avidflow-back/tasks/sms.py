from celery_app import celery_app
from services.sms import KavenegarSMS
from database.config import get_sync_session, get_sync_session_manual
from database.models import PhoneCode
from datetime import datetime, timezone
from sqlalchemy import select



@celery_app.task(name="send_verification_sms", queue='message')
def send_verification_sms(phone_number: str, code: str):
    sms = KavenegarSMS()
    result = sms.send_verification(phone_number, code)

    with get_sync_session_manual() as session:
        stmt = select(PhoneCode).where(PhoneCode.phone_number == phone_number)
        phone_code = session.execute(stmt).scalar_one_or_none()
        if phone_code:
            phone_code.tmp_code_sent_time = datetime.now(timezone.utc)
        phone_code.tmp_code_sent_counter += 1
        session.commit()
    return result
