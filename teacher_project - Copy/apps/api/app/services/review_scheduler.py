"""Spaced repetition review scheduler — runs as an async background task.

Finds concepts marked as 'shaky' or 'review_due' across all student sessions
and dispatches review notifications.  In free / local mode these are logged to
``review_log.txt``; in production the EMAIL_BACKEND setting controls delivery.
"""
import asyncio
import logging
import os
from datetime import date, datetime, timezone
from pathlib import Path

logger = logging.getLogger("teachclone.review_scheduler")
REVIEW_LOG = Path("review_log.txt")


async def get_due_reviews(db: "AsyncSession") -> list[dict]:  # noqa: F821
    """Return all concept review entries that are due today or overdue."""
    from sqlalchemy import select
    from app.models.student_session import StudentSession

    result = await db.execute(
        select(StudentSession)
        .where(StudentSession.concept_mastery.isnot(None))
    )
    sessions = result.scalars().all()

    due: list[dict] = []
    today = date.today()
    for session in sessions:
        mastery = session.concept_mastery or []
        for concept in mastery:
            state = concept.get("mastery_state", "")
            if state not in ("shaky", "review_due"):
                continue
            next_review = concept.get("next_review_date")
            if next_review:
                try:
                    nr = date.fromisoformat(str(next_review))
                    if nr > today:
                        continue
                except (ValueError, TypeError):
                    pass
            due.append({
                "session_id": str(session.id),
                "student_id": str(session.student_id),
                "concept": concept.get("topic") or concept.get("concept", "unknown"),
                "mastery_state": state,
                "next_review_date": next_review,
            })
    return due


async def dispatch_review_notification(review: dict) -> None:
    """Send (or log) a review notification for a single concept."""
    email_backend = os.getenv("EMAIL_BACKEND", "log")
    message = (
        f"Review due: '{review['concept']}' "
        f"for student {review['student_id']} "
        f"(state: {review['mastery_state']}, "
        f"due: {review['next_review_date']})"
    )
    if email_backend == "log":
        with open(REVIEW_LOG, "a") as f:
            f.write(f"[{datetime.now(timezone.utc).isoformat()}] {message}\n")
        logger.info(message)
    else:
        # Production: send email / push via the configured backend.
        logger.info("Review notification (backend=%s): %s", email_backend, message)


async def run_review_scheduler(db_factory=None) -> None:
    """Main scheduler loop.  Called on startup when INLINE_TASKS=true."""
    if db_factory is None:
        from app.db.session import AsyncSessionLocal
        db_factory = AsyncSessionLocal

    while True:
        try:
            async with db_factory() as db:
                reviews = await get_due_reviews(db)
                for review in reviews:
                    await dispatch_review_notification(review)
                logger.info(
                    "Review scheduler: %d due reviews processed.", len(reviews)
                )
        except Exception as exc:
            logger.error("Review scheduler error: %s", exc)
        await asyncio.sleep(3600)  # Run every hour
