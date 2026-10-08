"""GDPR compliance endpoints — data export and account deletion."""
import json
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.audit_log import AuditLog
from app.models.media_source import MediaSource
from app.models.message import Message
from app.models.quiz import Quiz
from app.models.student_session import StudentSession
from app.models.teacher_profile import TeacherProfile
from app.models.teacher_share import TeacherShare
from app.models.usage_log import UsageLog
from app.models.user import User
from app.models.user_badge import UserBadge
from app.models.user_stats import UserStats

router = APIRouter(prefix="/gdpr", tags=["gdpr"])
log = logging.getLogger("teachclone.gdpr")


def _user_to_dict(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "full_name": user.full_name,
        "avatar_url": user.avatar_url,
        "plan": user.plan,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/export")
async def export_data(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Collect all data belonging to the current user and return as JSON."""
    # --- User profile ---
    user_data = _user_to_dict(user)

    # --- Teacher profiles ---
    profiles = (
        (await db.execute(
            select(TeacherProfile).where(TeacherProfile.user_id == user.id)
        )).scalars().all()
    )
    profiles_data = [
        {
            "id": str(p.id),
            "name": p.name,
            "subject": p.subject,
            "description": p.description,
            "visibility": p.visibility,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in profiles
    ]

    # --- Sessions ---
    sessions = (
        (await db.execute(
            select(StudentSession).where(StudentSession.student_id == user.id)
        )).scalars().all()
    )
    session_ids = [s.id for s in sessions]
    sessions_data = [
        {
            "id": str(s.id),
            "teacher_profile_id": str(s.teacher_profile_id),
            "student_profile": s.student_profile,
            "current_effective_level": s.current_effective_level,
            "concept_mastery": s.concept_mastery,
            "message_count": s.message_count,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in sessions
    ]

    # --- Messages ---
    messages_data = []
    if session_ids:
        messages = (
            (await db.execute(
                select(Message).where(Message.session_id.in_(session_ids))
            )).scalars().all()
        )
        messages_data = [
            {
                "id": str(m.id),
                "session_id": str(m.session_id),
                "role": m.role,
                "content": m.content,
                "audio_url": m.audio_url,
                "tokens_used": m.tokens_used,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ]

    # --- Media sources (metadata only) ---
    media = (
        (await db.execute(
            select(MediaSource).where(MediaSource.uploaded_by == user.id)
        )).scalars().all()
    )
    media_data = [
        {
            "id": str(m.id),
            "teacher_profile_id": str(m.teacher_profile_id),
            "source_type": m.source_type,
            "original_url": m.original_url,
            "file_name": m.file_name,
            "file_size_bytes": m.file_size_bytes,
            "status": m.status,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        }
        for m in media
    ]

    # --- Quizzes ---
    quizzes_data = []
    if session_ids:
        quizzes = (
            (await db.execute(
                select(Quiz).where(Quiz.session_id.in_(session_ids))
            )).scalars().all()
        )
        quizzes_data = [
            {
                "id": str(q.id),
                "session_id": str(q.session_id),
                "kind": q.kind,
                "score": q.score,
                "completed_at": q.completed_at.isoformat() if q.completed_at else None,
            }
            for q in quizzes
        ]

    # --- Stats / badges / usage ---
    stats_row = (
        (await db.execute(
            select(UserStats).where(UserStats.user_id == user.id)
        )).scalar_one_or_none()
    )
    stats_data = {
        "xp_total": stats_row.xp_total if stats_row else 0,
        "level": stats_row.level if stats_row else 1,
        "streak_days": stats_row.streak_days if stats_row else 0,
        "sessions_completed": stats_row.sessions_completed if stats_row else 0,
        "quizzes_completed": stats_row.quizzes_completed if stats_row else 0,
    }

    badges = (
        (await db.execute(
            select(UserBadge).where(UserBadge.user_id == user.id)
        )).scalars().all()
    )
    badges_data = [{"badge_id": b.badge_id} for b in badges]

    usage = (
        (await db.execute(
            select(UsageLog).where(UsageLog.user_id == user.id)
        )).scalars().all()
    )
    usage_data = [
        {"event_type": u.event_type, "billing_period": u.billing_period}
        for u in usage
    ]

    # --- Shares ---
    shares = (
        (await db.execute(
            select(TeacherShare).where(TeacherShare.created_by == user.id)
        )).scalars().all()
    )
    shares_data = [
        {"token": s.token, "mode": s.mode, "created_at": s.created_at.isoformat() if s.created_at else None}
        for s in shares
    ]

    export = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "user": user_data,
        "profiles": profiles_data,
        "sessions": sessions_data,
        "messages": messages_data,
        "media": media_data,
        "quizzes": quizzes_data,
        "stats": stats_data,
        "badges": badges_data,
        "usage": usage_data,
        "shares": shares_data,
    }

    AuditLog.write(db, user.id, user.email, "gdpr.exported", "user", str(user.id))

    def generate():
        yield json.dumps(export, indent=2, default=str)

    return StreamingResponse(
        generate(),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="my_data_export.json"'},
    )


@router.delete("/account")
async def delete_account(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete all data for the current user. Irreversible."""
    user_id = user.id
    user_email = user.email
    log.warning("GDPR: Account deletion requested for user %s (%s)", user_id, user_email)

    # 1. Get all sessions (needed to cascade delete messages and quizzes)
    sessions = (
        (await db.execute(
            select(StudentSession).where(StudentSession.student_id == user_id)
        )).scalars().all()
    )
    session_ids = [s.id for s in sessions]

    # 2. Delete chat messages
    if session_ids:
        msgs = (
            (await db.execute(
                select(Message).where(Message.session_id.in_(session_ids))
            )).scalars().all()
        )
        for m in msgs:
            await db.delete(m)
        await db.flush()

    # 3. Delete sessions
    for s in sessions:
        await db.delete(s)
    await db.flush()

    # 4. Delete quizzes
    if session_ids:
        quizzes = (
            (await db.execute(
                select(Quiz).where(Quiz.session_id.in_(session_ids))
            )).scalars().all()
        )
        for q in quizzes:
            await db.delete(q)
        await db.flush()

    # 5. Delete media sources
    media = (
        (await db.execute(
            select(MediaSource).where(MediaSource.uploaded_by == user_id)
        )).scalars().all()
    )
    for m in media:
        await db.delete(m)
    await db.flush()

    # 6. Delete teacher profiles
    profiles = (
        (await db.execute(
            select(TeacherProfile).where(TeacherProfile.user_id == user_id)
        )).scalars().all()
    )
    for p in profiles:
        await db.delete(p)
    await db.flush()

    # 7. Delete shares
    shares = (
        (await db.execute(
            select(TeacherShare).where(TeacherShare.created_by == user_id)
        )).scalars().all()
    )
    for s in shares:
        await db.delete(s)
    await db.flush()

    # 8. Delete usage / stats / badges / audit
    for model_class, user_id_field in [
        (UsageLog, "user_id"),
        (UserStats, "user_id"),
        (UserBadge, "user_id"),
        (AuditLog, "actor_id"),
    ]:
        rows = (
            (await db.execute(
                select(model_class).where(getattr(model_class, user_id_field) == user_id)
            )).scalars().all()
        )
        for row in rows:
            await db.delete(row)
    await db.flush()

    # 9. Delete user from Clerk (if configured)
    if settings.CLERK_SECRET_KEY and user.clerk_id and user.clerk_id != "dev_local_user":
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.delete(
                    f"https://api.clerk.com/v1/users/{user.clerk_id}",
                    headers={"Authorization": f"Bearer {settings.CLERK_SECRET_KEY}"},
                )
                log.info("Clerk user deletion: status %s", resp.status_code)
        except Exception as exc:
            log.warning("Failed to delete Clerk user %s: %s", user.clerk_id, exc)

    # 10. Delete user record
    await db.delete(user)
    await db.flush()

    deleted_at = datetime.now(timezone.utc).isoformat()
    log.warning("GDPR: Account %s deleted at %s", user_id, deleted_at)
    return {"message": "Account deleted", "deleted_at": deleted_at}
