"""Teach Me feature — 7-beat lesson arc on a selected source."""
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import call_ollama, get_chroma_context, get_db_connection

logger = logging.getLogger("teach_router")

router = APIRouter(prefix="/teach", tags=["teach"])

# ── 7-beat arc definition ────────────────────────────────────────────────────
BEATS = [
    {
        "beat": "hook",
        "label": "Hook 🎣",
        "prompt": "Start with a surprising fact, real-world example, or interesting question about {topic} that immediately grabs attention. Keep it to 2-3 sentences. Make the student curious.",
    },
    {
        "beat": "concept",
        "label": "Core Concept 🧠",
        "prompt": "Explain the main concept of {topic} in the simplest possible language. Use short sentences. No jargon. Imagine explaining to a 15-year-old. 3-5 sentences max.",
    },
    {
        "beat": "example",
        "label": "Example 💡",
        "prompt": "Give one clear, concrete, real-world example of {topic}. Walk through it step by step. The example should make the concept feel obvious.",
    },
    {
        "beat": "analogy",
        "label": "Analogy 🔗",
        "prompt": "Create a simple analogy that compares {topic} to something from everyday life (cooking, sports, traffic, shopping, etc.). The analogy should make the concept stick in memory.",
    },
    {
        "beat": "deep_dive",
        "label": "Deep Dive 🔬",
        "prompt": "Now go a bit deeper on {topic}. Cover the important technical details, edge cases, or nuances. Use bullet points for clarity. Still keep the language simple.",
    },
    {
        "beat": "quiz",
        "label": "Quick Quiz ✅",
        "prompt": """Generate exactly 3 quiz questions about {topic} based on what was just taught.
Format STRICTLY as JSON array only, no other text:
[
  {{
    "q": "question text",
    "options": ["A. option1", "B. option2", "C. option3", "D. option4"],
    "answer": "A",
    "explanation": "brief reason"
  }}
]""",
    },
    {
        "beat": "summary",
        "label": "Summary 📝",
        "prompt": "Give a crisp summary of {topic} in 5 bullet points. Each bullet = one key takeaway. Start each with a strong verb. This should work as a revision cheat-sheet.",
    },
]


class StartTeachRequest(BaseModel):
    source_id: str
    source_name: str
    topic: Optional[str] = None  # auto-extracted if not provided


class BeatRequest(BaseModel):
    session_id: str
    beat_index: int  # 0-6


@router.post("/start")
async def start_teaching(req: StartTeachRequest):
    """Create a teaching session for a source.

    Returns session_id + first beat (hook) content immediately.
    """
    # Auto-extract topic from source name if not provided
    topic = req.topic or req.source_name.replace(".pdf", "").replace("_", " ")

    # Pull relevant context from ChromaDB
    context = get_chroma_context(topic, source_id=req.source_id)

    if not context:
        # Fallback to general context query on topic
        context = get_chroma_context(topic)

    if not context:
        return {
            "error": f"No content found for '{topic}' in ChromaDB. Make sure the PDF is processed."
        }

    # Generate the first beat (hook) immediately
    hook_beat = BEATS[0]
    system_prompt = f"""You are an expert teacher. Teach ONLY from the provided context.
Context from uploaded PDF:
{context}

Instructions: {hook_beat['prompt'].format(topic=topic)}
Language: If the student has been speaking Hindi/Hinglish, respond in Hinglish. Otherwise English.
Keep it conversational, warm, and encouraging."""

    hook_content = await call_ollama(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Teach me about: {topic}"},
        ],
        options={"temperature": 0.7, "num_ctx": 4096},
    )

    # Save session to SQLite
    session_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """INSERT INTO teach_sessions
                   (id, source_id, source_name, topic, current_beat, beats_json, status)
                   VALUES (?, ?, ?, ?, 0, ?, 'active')""",
                (
                    session_id,
                    req.source_id,
                    req.source_name,
                    topic,
                    json.dumps([{
                        "beat_index": 0,
                        "beat_label": hook_beat["label"],
                        "content": hook_content,
                    }]),
                ),
            )
    finally:
        conn.close()

    return {
        "session_id": session_id,
        "topic": topic,
        "total_beats": len(BEATS),
        "current_beat": 0,
        "beat_label": BEATS[0]["label"],
        "content": hook_content,
        "is_quiz": False,
        "next_beat": 1,
        "beats_remaining": len(BEATS) - 1,
    }


@router.post("/next-beat")
async def get_next_beat(req: BeatRequest):
    """Get the next beat of the lesson.

    beat_index: 1=Concept, 2=Example, 3=Analogy, 4=DeepDive, 5=Quiz, 6=Summary
    """
    conn = get_db_connection()
    try:
        session = conn.execute(
            "SELECT * FROM teach_sessions WHERE id = ?", (req.session_id,)
        ).fetchone()
    finally:
        conn.close()

    if not session:
        return {"error": "Session not found"}

    if req.beat_index >= len(BEATS):
        return {"error": "All beats complete", "lesson_done": True}

    topic = session["topic"]
    source_id = session["source_id"]
    beat = BEATS[req.beat_index]
    context = get_chroma_context(topic, source_id=source_id) or get_chroma_context(topic)

    is_quiz = beat["beat"] == "quiz"

    system_prompt = f"""You are an expert teacher continuing a lesson on '{topic}'.
Context from uploaded PDF:
{context}

Instructions: {beat['prompt'].format(topic=topic)}
{"Return ONLY valid JSON array, no extra text." if is_quiz else "Keep language simple and engaging."}"""

    content = await call_ollama(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Continue teaching: {beat['beat']} for {topic}"},
        ],
        options={"temperature": 0.6 if not is_quiz else 0.2, "num_ctx": 4096},
    )

    # For quiz beat, parse and return structured JSON
    quiz_data = None
    if is_quiz:
        try:
            clean = content.strip()
            if "```" in clean:
                parts = clean.split("```")
                for p in parts:
                    p = p.strip()
                    if p.startswith("json"):
                        p = p[4:].strip()
                    if p.startswith("["):
                        clean = p
                        break
            first_br = clean.find("[")
            last_br = clean.rfind("]")
            if first_br != -1 and last_br > first_br:
                quiz_data = json.loads(clean[first_br : last_br + 1])
            else:
                quiz_data = json.loads(clean)
        except Exception as e:
            logger.warning(f"Failed to parse quiz json: {e}")
            quiz_data = None

    # Update current_beat in session
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE teach_sessions SET current_beat = ? WHERE id = ?",
                (req.beat_index, req.session_id),
            )
    finally:
        conn.close()

    return {
        "session_id": req.session_id,
        "topic": topic,
        "current_beat": req.beat_index,
        "beat_label": beat["label"],
        "content": content,
        "is_quiz": is_quiz,
        "quiz_data": quiz_data,
        "lesson_done": req.beat_index == len(BEATS) - 1,
        "next_beat": req.beat_index + 1 if req.beat_index < len(BEATS) - 1 else None,
    }


@router.post("/followup")
async def teaching_followup(session_id: str, question: str):
    """User asks a follow-up question during a lesson beat."""
    conn = get_db_connection()
    try:
        session = conn.execute(
            "SELECT * FROM teach_sessions WHERE id = ?", (session_id,)
        ).fetchone()
    finally:
        conn.close()

    if not session:
        return {"error": "Session not found"}

    topic = session["topic"]
    source_id = session["source_id"]
    context = (
        get_chroma_context(f"{topic} {question}", source_id=source_id)
        or get_chroma_context(f"{topic} {question}")
    )

    answer = await call_ollama(
        messages=[
            {
                "role": "system",
                "content": f"""You are teaching '{topic}'. Answer the student's follow-up question using the context below. Keep it simple and direct.
Context:
{context}""",
            },
            {"role": "user", "content": question},
        ],
        options={"temperature": 0.7, "num_ctx": 3000},
    )
    return {"answer": answer}
