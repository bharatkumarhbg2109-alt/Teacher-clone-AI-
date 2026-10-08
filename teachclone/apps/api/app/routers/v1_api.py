"""Public v1 API (API-key authenticated) — for institutes embedding TeachClone.

Same capabilities as the app, but stateless-friendly and non-streaming, so
partner apps can drop it into their own student experiences.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import check_api_key, get_db
from app.models.student_session import StudentSession
from app.models.teacher_profile import TeacherProfile
from app.models.user import User
from app.schemas.session import StudentProfileInput
from app.services import llm
from app.services.prompt_builder import build_system_prompt
from app.services.retrieval import retrieve_context

router = APIRouter(prefix="/v1", tags=["v1"])


class V1SessionCreate(BaseModel):
    teacher_profile_id: str
    student_profile: StudentProfileInput


class V1Chat(BaseModel):
    message: str


@router.get("/profiles")
async def v1_profiles(
    user: User = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    rows = (
        (await db.execute(
            select(TeacherProfile).where(TeacherProfile.user_id == user.id)
        )).scalars().all()
    )
    return [{"id": str(p.id), "name": p.name, "subject": p.subject} for p in rows]


@router.post("/sessions")
async def v1_create_session(
    payload: V1SessionCreate,
    user: User = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    session = StudentSession(
        student_id=user.id,
        teacher_profile_id=payload.teacher_profile_id,
        student_profile=payload.student_profile.model_dump(),
        concept_mastery=[],
    )
    db.add(session)
    await db.flush()
    return {"session_id": str(session.id)}


@router.post("/sessions/{session_id}/chat")
async def v1_chat(
    session_id: str,
    payload: V1Chat,
    user: User = Depends(check_api_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
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

    context = await retrieve_context(payload.message, str(profile.id), top_k=8)
    system = build_system_prompt(profile, session, context, turn=session.message_count)
    answer = await llm.complete_text(system, [{"role": "user", "content": payload.message}])

    session.message_count = (session.message_count or 0) + 2
    await db.flush()
    citations = [
        {"page": c.page, "start_time": c.start_time, "text": c.text[:200]} for c in context
    ]
    return {"response": answer, "citations": citations, "session_id": session_id}
