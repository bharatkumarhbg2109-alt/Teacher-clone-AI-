"""Export a session as a PDF or Markdown study guide."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.student_session import StudentSession
from app.models.teacher_profile import TeacherProfile
from app.models.user import User
from app.services import billing
from app.services.export_service import export_as_markdown, export_as_pdf
from app.services.levels import LEVEL_LABELS, effective_level
from app.services.session_summarizer import summarize_session

router = APIRouter(tags=["export"])


class ExportRequest(BaseModel):
    format: str = "pdf"  # pdf|markdown


@router.post("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    payload: ExportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = (
        await db.execute(select(StudentSession).where(StudentSession.id == session_id))
    ).scalar_one_or_none()
    if not session or session.student_id != user.id:
        raise HTTPException(404, "Session not found")

    ok, reason = await billing.check_quota(db, user, "export_created")
    if not ok:
        raise HTTPException(402, detail={"error": "quota_exceeded", "reason": reason})

    summary = session.session_notes or await summarize_session(db, session.id)
    session.session_notes = summary

    teacher = (
        await db.execute(
            select(TeacherProfile).where(TeacherProfile.id == session.teacher_profile_id)
        )
    ).scalar_one()
    level = LEVEL_LABELS.get(
        effective_level(session.student_profile, session.current_effective_level), "learner"
    )
    await billing.log_usage(db, user.id, "export_created")

    if payload.format == "markdown":
        md = await export_as_markdown(teacher.name, level, session.id, summary)
        return Response(
            content=md,
            media_type="text/markdown",
            headers={"Content-Disposition": f'attachment; filename="session-{session_id}.md"'},
        )
    pdf = await export_as_pdf(teacher.name, level, session.id, summary)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="session-{session_id}.pdf"'},
    )
