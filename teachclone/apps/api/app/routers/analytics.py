"""Teacher profile analytics — engagement metrics for profile owners.

    GET /profiles/{profile_id}/analytics   → full analytics dashboard data
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.media_source import MediaSource
from app.models.message import Message
from app.models.quiz import Quiz
from app.models.student_session import StudentSession
from app.models.teacher_profile import TeacherProfile
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(tags=["analytics"])


@router.get("/profiles/{profile_id}/analytics")
async def get_profile_analytics(
    profile_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return engagement analytics for a teacher profile.

    The caller must own the profile.  Returns:
    - overview: total_sessions, unique_learners, total_messages, avg_message_length
    - quiz_stats: total_quizzes, avg_score, completion_rate, quizzes_by_kind
    - activity: session counts per day for the last 30 days
    - content: media source counts by type and status
    - student_levels: distribution of student levels across sessions
    - top_concepts: most frequently tested concepts from quizzes
    """
    # --- ownership check ---------------------------------------------------
    profile = (
        await db.execute(select(TeacherProfile).where(TeacherProfile.id == profile_id))
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Teacher profile not found")
    if profile.user_id != user.id:
        raise HTTPException(403, "Not your teacher profile")

    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    # --- 1. Overview --------------------------------------------------------
    sessions = (
        await db.execute(
            select(StudentSession).where(StudentSession.teacher_profile_id == profile_id)
        )
    ).scalars().all()

    total_sessions = len(sessions)
    unique_learners = len({str(s.student_id) for s in sessions})

    total_messages = sum(s.message_count or 0 for s in sessions)

    # Average message length (character count) across all sessions
    avg_msg_len = 0.0
    if total_messages > 0:
        sample_size = min(total_sessions, 50)
        char_total = sum(
            (s.message_count or 0) * 120  # rough estimate; refined below
            for s in sessions[:sample_size]
        )
        # Get actual average from messages table for accuracy
        avg_row = (
            await db.execute(
                select(func.avg(func.length(Message.content)))
                .join(StudentSession, Message.session_id == StudentSession.id)
                .where(StudentSession.teacher_profile_id == profile_id)
            )
        ).scalar()
        if avg_row:
            avg_msg_len = round(float(avg_row), 1)

    # --- 2. Quiz stats ------------------------------------------------------
    quizzes = (
        await db.execute(
            select(Quiz).where(Quiz.teacher_profile_id == profile_id)
        )
    ).scalars().all()

    total_quizzes = len(quizzes)
    completed_quizzes = [q for q in quizzes if q.score is not None]
    avg_score = (
        round(sum(q.score for q in completed_quizzes) / len(completed_quizzes) * 100, 1)
        if completed_quizzes
        else 0.0
    )
    completion_rate = (
        round(len(completed_quizzes) / total_quizzes * 100, 1)
        if total_quizzes > 0
        else 0.0
    )

    quizzes_by_kind: dict[str, int] = {}
    for q in quizzes:
        quizzes_by_kind[q.kind] = quizzes_by_kind.get(q.kind, 0) + 1

    # --- 3. Activity (last 30 days) -----------------------------------------
    activity: list[dict] = []
    if sessions:
        session_ids = [s.id for s in sessions]
        rows = (
            await db.execute(
                select(
                    func.date(StudentSession.created_at).label("day"),
                    func.count(StudentSession.id).label("cnt"),
                )
                .where(
                    StudentSession.teacher_profile_id == profile_id,
                    StudentSession.created_at >= thirty_days_ago,
                )
                .group_by(func.date(StudentSession.created_at))
                .order_by(func.date(StudentSession.created_at))
            )
        ).all()
        activity = [{"date": str(r.day), "sessions": r.cnt} for r in rows]

    # --- 4. Content breakdown -----------------------------------------------
    media_rows = (
        await db.execute(
            select(MediaSource).where(MediaSource.teacher_profile_id == profile_id)
        )
    ).scalars().all()

    content_by_type: dict[str, int] = {}
    content_by_status: dict[str, int] = {}
    for m in media_rows:
        content_by_type[m.source_type] = content_by_type.get(m.source_type, 0) + 1
        content_by_status[m.status] = content_by_status.get(m.status, 0) + 1

    # --- 5. Student level distribution --------------------------------------
    level_counts: dict[str, int] = {}
    for s in sessions:
        level = "unknown"
        if s.student_profile and isinstance(s.student_profile, dict):
            level = s.student_profile.get("level", "unknown")
        elif s.current_effective_level:
            level = s.current_effective_level
        level_counts[level] = level_counts.get(level, 0) + 1

    # --- 6. Top concepts from quizzes ---------------------------------------
    concept_counts: dict[str, int] = {}
    for q in quizzes:
        if q.questions and isinstance(q.questions, list):
            for question in q.questions:
                if isinstance(question, dict):
                    concept = question.get("concept", "")
                    if concept:
                        concept_counts[concept] = concept_counts.get(concept, 0) + 1

    top_concepts = sorted(concept_counts.items(), key=lambda x: x[1], reverse=True)[:15]
    top_concepts_list = [{"concept": c, "count": n} for c, n in top_concepts]

    return {
        "overview": {
            "total_sessions": total_sessions,
            "unique_learners": unique_learners,
            "total_messages": total_messages,
            "avg_message_length": avg_msg_len,
        },
        "quiz_stats": {
            "total_quizzes": total_quizzes,
            "avg_score": avg_score,
            "completion_rate": completion_rate,
            "quizzes_by_kind": quizzes_by_kind,
        },
        "activity": activity,
        "content": {
            "total_sources": len(media_rows),
            "by_type": content_by_type,
            "by_status": content_by_status,
        },
        "student_levels": [
            {"level": lvl, "count": cnt}
            for lvl, cnt in sorted(level_counts.items(), key=lambda x: x[1], reverse=True)
        ],
        "top_concepts": top_concepts_list,
    }
