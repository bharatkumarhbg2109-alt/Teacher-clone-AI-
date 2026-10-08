"""Celery application. Tasks live under app.tasks.*"""
from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "teachclone",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.media_tasks",
        "app.tasks.doc_tasks",
        "app.tasks.embedding_tasks",
        "app.tasks.style_tasks",
        "app.tasks.vision_tasks",
        "app.tasks.share_tasks",
        "app.tasks.review_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "media.*": {"queue": "media"},
        "ai.*": {"queue": "ai"},
    },
    task_default_queue="default",
    task_soft_time_limit=3600,   # 60 min soft limit (large / long media)
    task_time_limit=5400,        # 90 min hard limit
)

# --- Celery Beat schedule (periodic tasks) ---
celery_app.conf.beat_schedule = {
    "daily-review-checkpoints": {
        "task": "app.tasks.review_tasks.generate_review_checkpoints",
        "schedule": crontab(hour=9, minute=0),  # run every day at 9 AM UTC
    },
}

# Native / no-infra mode: run tasks in-process (no Redis broker / worker).
if settings.INLINE_TASKS:
    celery_app.conf.task_always_eager = True
    # Don't re-raise a task failure into the HTTP request — each task already
    # records its own status="failed" on the media source, so a failed ingest
    # should surface as a "Failed" badge, not a 500.
    celery_app.conf.task_eager_propagates = False
    celery_app.conf.task_store_eager_result = False
    # `update_state()` still needs a result backend object; use an in-process
    # memory cache so progress reporting works with no Redis running.
    celery_app.conf.result_backend = "cache+memory://"
