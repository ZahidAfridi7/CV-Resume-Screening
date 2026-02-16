"""
Celery app for background processing. Broker: Redis.
"""
from celery import Celery

from app.config import get_settings

settings = get_settings()
celery_app = Celery(
    "cv_screening",
    broker=settings.celery_broker_url,
    backend=settings.redis_url,
    include=["app.tasks.process_resume"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=600,
    task_soft_time_limit=540,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    result_expires=3600,
)
