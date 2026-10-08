"""Streaming adaptive teaching chat (SSE), with citations and audio output."""
import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.dependencies import get_current_user, get_db
from app.models.message import Message
from app.models.student_session import StudentSession
from app.models.teacher_profile import TeacherProfile
from app.models.user import User
from app.schemas.chat import ChatMessageRequest
from app.services import billing, gamification, llm
from app.services.prompt_builder import build_system_prompt
from app.services.retrieval import retrieve_context

router = APIRouter(prefix="/chat", tags=["chat"])

_CITE = re.compile(r"\[(\d+)\]")


@router.post("/{session_id}/message")
async def send_message(
    session_id: str,
    payload: ChatMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = (
        await db.execute(select(StudentSession).where(StudentSession.id == session_id))
    ).scalar_one_or_none()
    if not session or session.student_id != user.id:
        raise HTTPException(404, "Session not found")

    ok, reason = await billing.check_quota(db, user, "message_sent")
    if not ok:
        raise HTTPException(402, detail={"error": "quota_exceeded", "reason": reason})

    user_msg = payload.content
    want_audio = payload.want_audio
    teacher_profile_id = str(session.teacher_profile_id)

    async def event_gen():
        from app.db.session import AsyncSessionLocal

        # 1. Load context + build prompt (fresh session).
        async with AsyncSessionLocal() as db1:
            sess = (
                await db1.execute(select(StudentSession).where(StudentSession.id == session_id))
            ).scalar_one()
            profile = (
                await db1.execute(
                    select(TeacherProfile).where(TeacherProfile.id == sess.teacher_profile_id)
                )
            ).scalar_one()
            history_rows = (
                (await db1.execute(
                    select(Message)
                    .where(Message.session_id == sess.id)
                    .order_by(Message.created_at.desc())
                    .limit(10)
                )).scalars().all()
            )
            history = [{"role": m.role, "content": m.content} for m in reversed(history_rows)]
            turn = sess.message_count

            db1.add(Message(session_id=sess.id, role="user", content=user_msg, citations=[]))
            await db1.commit()

            context = await retrieve_context(user_msg, teacher_profile_id, top_k=8)
            system = build_system_prompt(profile, sess, context, turn=turn)
            tts_voice = profile.tts_voice

        messages = history + [{"role": "user", "content": user_msg}]

        # 2. Stream the answer.
        full = ""
        try:
            async for token in llm.stream_teaching(system, messages):
                full += token
                yield {"event": "token", "data": json.dumps({"token": token})}
        except Exception as exc:
            import logging
            logging.getLogger("teachclone.chat").error(
                "Chat stream error for session %s: %s", session_id, exc, exc_info=True
            )
            yield {"event": "error", "data": json.dumps({"message": "An error occurred while generating the response. Please try again."})}
            return

        # 3. Citations from [n] markers.
        cited = sorted({int(n) for n in _CITE.findall(full)})
        citations = []
        for n in cited:
            if 1 <= n <= len(context):
                r = context[n - 1]
                citations.append(
                    {
                        "media_source_id": r.media_source_id,
                        "start_time": r.start_time,
                        "end_time": r.end_time,
                        "page": r.page,
                        "chunk_text": r.text[:240],
                    }
                )

        # 4. Optional audio output.
        audio_url = None
        message_id = None
        provider = llm.get_llm_provider()
        async with AsyncSessionLocal() as db2:
            assistant = Message(
                session_id=session_id,
                role="assistant",
                content=full,
                citations=citations,
                model_used=provider.model_name,
            )
            db2.add(assistant)
            sess = (
                await db2.execute(select(StudentSession).where(StudentSession.id == session_id))
            ).scalar_one()
            sess.message_count = (sess.message_count or 0) + 2
            from datetime import datetime, timezone

            sess.last_activity_at = datetime.now(timezone.utc)
            await db2.flush()
            message_id = str(assistant.id)

            if want_audio:
                try:
                    from app.services.storage import storage_service
                    from app.services.tts_service import synthesize

                    tts_res = await synthesize(full, tts_voice)
                    if tts_res and tts_res.audio:
                        key = f"voice/{message_id}.{tts_res.ext}"
                        audio_url = storage_service.upload_bytes(key, tts_res.audio, tts_res.mime)
                        assistant.audio_url = audio_url
                except Exception as exc:
                    import logging
                    logging.getLogger("teachclone.chat").warning("TTS audio synthesis skipped/failed: %s", exc)
                    audio_url = None

            await billing.log_usage(db2, user.id, "message_sent")
            if sess.message_count % 10 == 0:
                await gamification.award_xp(db2, user.id, "message_sent", multiplier=5)
            await db2.commit()

        yield {
            "event": "done",
            "data": json.dumps(
                {"message_id": message_id, "citations": citations, "audio_url": audio_url}
            ),
        }

    return EventSourceResponse(event_gen())
