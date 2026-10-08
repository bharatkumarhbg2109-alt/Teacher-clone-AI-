"""Run an async coroutine from a synchronous Celery task."""
import asyncio


def run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
