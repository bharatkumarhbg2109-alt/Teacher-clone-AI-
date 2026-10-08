"""Voice — speech-to-text (question input) and text-to-speech (answer audio)."""
import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.message import Message
from app.models.student_session import StudentSession
from app.models.teacher_profile import TeacherProfile
from app.models.user import User

router = APIRouter(prefix="/voice", tags=["voice"])


class SpeakRequest(BaseModel):
    message_id: str = Field(min_length=1, max_length=100)


@router.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
) -> dict:
    """Transcribe an uploaded voice clip to text (for voice questions)."""
    from app.services.transcriber import transcriber

    suffix = os.path.splitext(file.filename or "audio.webm")[1] or ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    try:
        chunks = transcriber.transcribe(path)
        text = " ".join(c.text for c in chunks).strip()
    finally:
        os.unlink(path)
    return {"text": text}


@router.post("/speak")
async def speak(
    payload: SpeakRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Synthesize (and cache) audio for an assistant message."""
    msg = (
        await db.execute(select(Message).where(Message.id == payload.message_id))
    ).scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "Message not found")
    if msg.audio_url:
        return {"audio_url": msg.audio_url}

    session = (
        await db.execute(select(StudentSession).where(StudentSession.id == msg.session_id))
    ).scalar_one()
    if session.student_id != user.id:
        raise HTTPException(403, "Not your session")
    profile = (
        await db.execute(
            select(TeacherProfile).where(TeacherProfile.id == session.teacher_profile_id)
        )
    ).scalar_one()

    from app.services.storage import storage_service
    from app.services.tts_service import synthesize

    tts_result = await synthesize(msg.content, profile.tts_voice)
    key = f"voice/{msg.id}.{tts_result.ext}"
    url = storage_service.upload_bytes(key, tts_result.audio, tts_result.mime)
    msg.audio_url = url
    await db.flush()
    return {"audio_url": url}
