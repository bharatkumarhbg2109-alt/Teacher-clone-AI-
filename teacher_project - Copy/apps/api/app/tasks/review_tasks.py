"""Spaced repetition review scheduler � Celery task.

Finds concepts marked as 'shaky' or 'review_due' for all users, and generates
review quiz checkpoints. Runs daily via Celery Beat at 9 AM UTC.
"""
import logging
from datetime import datetime, timedelta, timezone

from celery import shared_task

log = logging.getLogger("teachclone.review")


@shared_task(name="app.tasks.review_tasks.generate_review_checkpoints")
def generate_review_checkpoints():
    """Find concepts needing review and create checkpoint quizzes for users."""
    # Import inside the task so the module loads even if Celery deps are missing.
    import asyncio
    from app.db.session import AsyncSessionLocal
    from sqlalchemy import select
    from app.models.student_session import StudentSession
    from app.models.quiz import Quiz
    from app.services.quiz_generator import quiz_generator

    async def _run():
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)

        async with AsyncSessionLocal() as db:
            # Find all sessions with concept mastery data
            sessions = (
                (await db.execute(
                    select(StudentSession)
                    .where(StudentSession.concept_mastery.isnot(None))
                )).scalars().all()
            )

            reviews_created = 0
            for session in sessions:
                mastery = session.concept_mastery or []
                if not mastery:
                    continue

                # Load teacher profile for subject/level info
                profile = session.teacher_profile
                if not profile:
                    continue

                # Get recent messages as context text for quiz generation
                from app.models.message import Message
                recent_msgs = (
                    (await db.execute(
                        select(Message)
                        .where(Message.session_id == session.id)
                        .where(Message.role == "assistant")
                        .order_by(Message.created_at.desc())
                        .limit(10)
                    )).scalars().all()
                )
                context_text = "\n".join(m.content for m in recent_msgs) if recent_msgs else "General knowledge"

                # Get student level from session profile
                student_level = session.current_effective_level or "intermediate"
                subject = profile.subject or "general"

                for concept in mastery:
                    state = concept.get("mastery_state", "")
                    if state not in ("shaky", "review_due"):
                        continue

                    # Check last_reviewed_at to avoid spamming
                    last_reviewed = concept.get("last_reviewed_at")
                    if last_reviewed:
                        try:
                            lr = datetime.fromisoformat(str(last_reviewed))
                            if lr > cutoff:
                                continue
                        except (ValueError, TypeError):
                            pass

                    topic = concept.get("topic") or concept.get("concept") or "topic"

                    # Generate the actual quiz checkpoint
                    try:
                        quiz_data = await quiz_generator.generate_checkpoint(
                            context_text=context_text,
                            level_label=student_level,
                            subject=subject,
                            concept=topic,
                            num=2,
                        )

                        # Save quiz to DB
                        quiz = Quiz(
                            session_id=session.id,
                            teacher_profile_id=session.teacher_profile_id,
                            kind="checkpoint",
                            questions=quiz_data.get("questions", []),
                        )
                        db.add(quiz)
                        reviews_created += 1

                        log.info(
                            "Review checkpoint created for session %s, user %s, topic '%s' (%d questions)",
                            session.id, session.student_id, topic,
                            len(quiz_data.get("questions", [])),
                        )
                    except Exception as exc:
                        log.warning(
                            "Failed to generate checkpoint for session %s, topic '%s': %s",
                            session.id, topic, exc,
                        )
                        continue

                    # Update last_reviewed_at
                    concept["last_reviewed_at"] = now.isoformat()

                # Save updated mastery back
                await db.commit()

            return reviews_created

    try:
        count = asyncio.run(_run())
        log.info("Review scheduler: %d review checkpoints generated", count)
        return {"reviews_created": count}
    except Exception as exc:
        log.exception("Review scheduler task failed: %s", exc)
        raise
