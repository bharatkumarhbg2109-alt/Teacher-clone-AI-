"""Trigger a Celery task — via the broker normally, or in-process (a background
thread) when INLINE_TASKS is set, so no Redis/worker is needed."""
import asyncio

from app.config import settings


async def dispatch(task, *args) -> None:
    if settings.INLINE_TASKS:
        # Run in a worker thread so the task's own event loop doesn't collide
        # with the request's running loop.
        await asyncio.to_thread(task.apply, args=list(args))
    else:
        task.delay(*args)
