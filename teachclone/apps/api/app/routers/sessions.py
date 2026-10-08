"""Learning sessions — create (with grade/subject/pace), list, summary, level."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.message import Message
from app.models.student_session import StudentSession
from app.models.teacher_profile import TeacherProfile
from app.models.user import User
from app.schemas.session import (
    AdjustLevelRequest,
    AdjustLevelResponse,
    MessagePreview,
    SessionCreate,
    SessionListItem,
    SessionResponse,
)
from app.schemas.teacher_profile import TeacherProfileResponse


def _session_response(
    session: StudentSession,
    profile: TeacherProfile | None = None,
    messages: list[Message] | None = None,
) -> SessionResponse:
    """Build the response explicitly — never assign to ORM relationships,
    which would trigger an async lazy-load."""
    return SessionResponse(
        id=session.id,
        teacher_profile_id=session.teacher_profile_id,
        student_profile=session.student_profile,
        current_effective_level=session.current_effective_level,
        concept_mastery=session.concept_mastery or [],
        message_count=session.message_count or 0,
        created_at=session.created_at,
        teacher_profile=(
            TeacherProfileResponse.model_validate(profile) if profile else None
        ),
        messages=[MessagePreview.model_validate(m) for m in (messages or [])],
    )
from app.services import billing, gamification
from app.services.levels import effective_level, step_level

router = APIRouter(prefix="/sessions", tags=["sessions"])


async def _usable_profile(db: AsyncSession, profile_id: str, user: User) -> TeacherProfile:
    profile = (
        await db.execute(select(TeacherProfile).where(TeacherProfile.id == profile_id))
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Teacher profile not found")
    if profile.user_id == user.id or profile.visibility in ("public", "unlisted"):
        return profile
    # (org membership check would go here for org profiles)
    if profile.org_id is not None:
        return profile
    raise HTTPException(403, "You can't learn from this teacher")


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    payload: SessionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    profile = await _usable_profile(db, payload.teacher_profile_id, user)

    session = StudentSession(
        student_id=user.id,
        teacher_profile_id=profile.id,
        student_profile=payload.student_profile.model_dump(),
        concept_mastery=[],
    )
    db.add(session)

    # Popularity metrics for the "most used teacher" ranking.
    prior = (
        await db.execute(
            select(func.count())
            .select_from(StudentSession)
            .where(
                StudentSession.teacher_profile_id == profile.id,
                StudentSession.student_id == user.id,
            )
        )
    ).scalar_one()
    profile.session_count = (profile.session_count or 0) + 1
    if prior == 0:
        profile.unique_learners = (profile.unique_learners or 0) + 1

    await db.flush()
    await billing.log_usage(db, user.id, "session_started")
    await gamification.award_xp(db, user.id, "session_started")
    await db.flush()

    return _session_response(session, profile, [])


@router.get("", response_model=list[SessionListItem])
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[StudentSession]:
    rows = (
        (await db.execute(
            select(StudentSession)
            .where(StudentSession.student_id == user.id)
            .order_by(StudentSession.last_activity_at.desc())
            .limit(50)
        )).scalars().all()
    )
    return list(rows)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StudentSession:
    session = (
        await db.execute(select(StudentSession).where(StudentSession.id == session_id))
    ).scalar_one_or_none()
    if not session or session.student_id != user.id:
        raise HTTPException(404, "Session not found")
    profile = (
        await db.execute(
            select(TeacherProfile).where(TeacherProfile.id == session.teacher_profile_id)
        )
    ).scalar_one()
    messages = (
        (await db.execute(
            select(Message)
            .where(Message.session_id == session.id)
            .order_by(Message.created_at)
            .limit(50)
        )).scalars().all()
    )
    return _session_response(session, profile, list(messages))


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    session = (
        await db.execute(select(StudentSession).where(StudentSession.id == session_id))
    ).scalar_one_or_none()
    if not session or session.student_id != user.id:
        raise HTTPException(404, "Session not found")
    await db.delete(session)
    await db.flush()
    return {"success": True}


@router.post("/{session_id}/adjust-level", response_model=AdjustLevelResponse)
async def adjust_level(
    session_id: str,
    payload: AdjustLevelRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdjustLevelResponse:
    session = (
        await db.execute(select(StudentSession).where(StudentSession.id == session_id))
    ).scalar_one_or_none()
    if not session or session.student_id != user.id:
        raise HTTPException(404, "Session not found")
    current = effective_level(session.student_profile, session.current_effective_level)
    session.current_effective_level = step_level(current, payload.direction)
    await db.flush()
    return AdjustLevelResponse(level=session.current_effective_level)


@router.get("/{session_id}/summary")
async def session_summary(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    session = (
        await db.execute(select(StudentSession).where(StudentSession.id == session_id))
    ).scalar_one_or_none()
    if not session or session.student_id != user.id:
        raise HTTPException(404, "Session not found")
    if session.session_notes:
        return session.session_notes

    from app.services.session_summarizer import summarize_session

    summary = await summarize_session(db, session.id)
    session.session_notes = summary
    await db.flush()
    return summary
