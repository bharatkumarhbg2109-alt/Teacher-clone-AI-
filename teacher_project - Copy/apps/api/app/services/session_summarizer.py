"""Generate structured study notes from a completed session."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message
from app.services import llm

_SUMMARY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "overview": {"type": "string"},
        "key_concepts": {"type": "array", "items": {"type": "string"}},
        "definitions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"term": {"type": "string"}, "definition": {"type": "string"}},
                "required": ["term", "definition"],
            },
        },
        "takeaways": {"type": "array", "items": {"type": "string"}},
        "questions_to_explore": {"type": "array", "items": {"type": "string"}},
        "topics_to_review": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["overview", "key_concepts", "definitions", "takeaways",
                 "questions_to_explore", "topics_to_review"],
}


async def summarize_session(db: AsyncSession, session_id) -> dict:
    messages = (
        (await db.execute(
            select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
        )).scalars().all()
    )
    transcript = "\n".join(f"{m.role.upper()}: {m.content}" for m in messages)
    prompt = (
        "Create structured study notes from this learning session.\n\n"
        f"SESSION:\n{transcript[:12000]}\n\n"
        "Include an overview, key concepts, important definitions, key takeaways, "
        "follow-up questions to explore, and topics to review."
    )
    return await llm.complete_json(prompt, _SUMMARY_SCHEMA, max_tokens=2000)
