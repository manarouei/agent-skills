from config import settings
from celery import Celery
from database.config import make_sync_url

celery_app = Celery(
    'workflow',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    beat_dburi=make_sync_url(settings.DATABASE_URL),
    beat_schema='celery_schema',
)

celery_app.conf.include = ['tasks']
# celery_app.autodiscover_tasks(["tasks"])
