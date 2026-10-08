"""Exam Question Practice — analyze reference patterns, generate new questions."""
import datetime
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from database import call_ollama, get_chroma_context, get_db_connection

logger = logging.getLogger("questions_router")

router = APIRouter(prefix="/questions", tags=["questions"])


class AnalyzeRequest(BaseModel):
    pattern_id: str
    source_name: Optional[str] = None


class GenerateRequest(BaseModel):
    pattern_id: str
    count: int = 20  # how many questions to generate
    source_name: Optional[str] = None


class GradeRequest(BaseModel):
    question_id: str
    user_answer: str


@router.post("/upload-reference")
async def upload_reference_questions(
    file: UploadFile = File(None),
    name: str = "Reference Questions",
):
    """Upload a .txt file containing reference questions (50-70 questions).

    Returns pattern_id to use in subsequent calls.
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    try:
        raw_bytes = await file.read()
        raw = raw_bytes.decode("utf-8", errors="ignore")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    pattern_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """INSERT INTO question_patterns (id, name, raw_questions)
                   VALUES (?, ?, ?)""",
                (pattern_id, name, raw),
            )
    finally:
        conn.close()

    return {
        "pattern_id": pattern_id,
        "name": name,
        "question_count": len([l for l in raw.split("\n") if l.strip()]),
        "message": "Reference questions saved. Now call /questions/analyze",
    }


@router.post("/paste-reference")
async def paste_reference_questions(name: str = "Reference Questions", raw_text: str = ""):
    """Alternative to file upload — paste questions directly as text."""
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="raw_text cannot be empty")

    pattern_id = str(uuid.uuid4())
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO question_patterns (id, name, raw_questions) VALUES (?, ?, ?)",
                (pattern_id, name, raw_text),
            )
    finally:
        conn.close()

    return {
        "pattern_id": pattern_id,
        "name": name,
        "message": "Questions saved. Now call /questions/analyze",
    }


@router.post("/analyze")
async def analyze_pattern(req: AnalyzeRequest):
    """Use LLM to analyze the reference questions and extract the exam pattern.

    Returns structured JSON pattern stored in DB.
    """
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM question_patterns WHERE id = ?", (req.pattern_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return {"error": "Pattern ID not found"}

    raw = row["raw_questions"]

    analysis_prompt = f"""Analyze the following exam questions carefully and extract the pattern.
Return ONLY a JSON object — no explanation, no markdown, just valid JSON:

{{
  "total_questions": 50,
  "question_types": {{
    "MCQ": 40,
    "short_answer": 5,
    "long_answer": 5,
    "fill_in_blank": 0,
    "true_false": 0,
    "numerical": 0
  }},
  "difficulty_distribution": {{
    "easy": "30%",
    "medium": "50%",
    "hard": "20%"
  }},
  "marks_pattern": {{
    "typical_marks_per_question": 1,
    "total_marks": 50,
    "marks_distribution": "1 mark for MCQ, 2 marks for short answer, 5 marks for long answer"
  }},
  "language_style": "technical with clear academic phrasing",
  "question_language": "english",
  "topics_covered": ["Machine Learning", "Neural Networks"],
  "question_stem_patterns": [
    "Which of the following...",
    "What is the primary advantage of...",
    "Explain the concept of..."
  ],
  "MCQ_option_style": "A/B/C/D",
  "avg_question_length": "medium",
  "key_observation": "Questions focus on conceptual distinction between algorithms and practical deployment trade-offs."
}}

QUESTIONS TO ANALYZE:
{raw[:4000]}"""

    content = await call_ollama(
        messages=[{"role": "user", "content": analysis_prompt}],
        options={"temperature": 0.2, "num_ctx": 6000},
    )
    content = content.strip()

    # Clean JSON from markdown fences if present
    if "```" in content:
        parts = content.split("```")
        for p in parts:
            p = p.strip()
            if p.startswith("json"):
                p = p[4:].strip()
            if p.startswith("{"):
                content = p
                break

    try:
        pattern_json = json.loads(content)
    except Exception:
        first_b = content.find("{")
        last_b = content.rfind("}")
        if first_b != -1 and last_b > first_b:
            try:
                pattern_json = json.loads(content[first_b : last_b + 1])
            except Exception:
                pattern_json = {"raw_analysis": content, "parse_error": True}
        else:
            pattern_json = {"raw_analysis": content, "parse_error": True}

    # Save pattern_json to DB
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE question_patterns SET pattern_json = ? WHERE id = ?",
                (json.dumps(pattern_json), req.pattern_id),
            )
    finally:
        conn.close()

    return {
        "pattern_id": req.pattern_id,
        "pattern": pattern_json,
        "message": "Pattern analyzed. Now call /questions/generate",
    }


@router.post("/generate")
async def generate_questions(req: GenerateRequest):
    """Generate new questions from source PDF matching the analyzed pattern.

    Generates in batches of 10 to avoid context overflow.
    """
    conn = get_db_connection()
    try:
        row = conn.execute(
            "SELECT * FROM question_patterns WHERE id = ?", (req.pattern_id,)
        ).fetchone()
    finally:
        conn.close()

    if not row:
        return {"error": "Pattern ID not found"}

    if not row["pattern_json"]:
        return {"error": "Pattern not analyzed yet. Call /questions/analyze first."}

    pattern = json.loads(row["pattern_json"])
    source_hint = req.source_name or "Machine learning neural networks transfer learning"
    context = get_chroma_context(source_hint, n_results=8) or get_chroma_context("machine learning")

    if not context:
        return {"error": "No source content found in ChromaDB. Upload a PDF first."}

    all_questions = []
    batch_size = 10
    batches = max(1, (req.count + batch_size - 1) // batch_size)

    for batch_num in range(batches):
        count_this_batch = min(batch_size, req.count - len(all_questions))
        if count_this_batch <= 0:
            break

        gen_prompt = f"""You are an expert exam question generator.
Generate EXACTLY {count_this_batch} exam questions following the pattern below.
Return ONLY a valid JSON array — no markdown formatting outside the array, no conversational commentary.

QUESTION PATTERN TO FOLLOW:
{json.dumps(pattern, indent=2)}

SOURCE MATERIAL (use ONLY this content for questions):
{context}

Generate questions in this EXACT JSON format:
[
  {{
    "question_text": "What is the primary role of convolutional filters in a CNN?",
    "question_type": "MCQ",
    "marks": 1,
    "difficulty": "medium",
    "options": ["A. Feature extraction", "B. Weight initialization", "C. Data augmentation", "D. Gradient clipping"],
    "correct_answer": "A",
    "explanation": "Convolutional filters slide across the input image to extract visual spatial features."
  }}
]

Rules:
- Match the EXACT question type distribution from the pattern
- Match the EXACT marks per question from the pattern
- Match the EXACT language style
- Match the EXACT question stem patterns (e.g. "Which of the following...")
- Questions MUST be answerable from the source material above
- For MCQ: always include 4 options labeled as per pattern's MCQ_option_style
- For short_answer/long_answer: options = [], correct_answer = key points expected"""

        content = await call_ollama(
            messages=[{"role": "user", "content": gen_prompt}],
            options={"temperature": 0.7, "num_ctx": 6000},
        )
        content = content.strip()

        # Clean JSON
        if "```" in content:
            parts = content.split("```")
            for p in parts:
                p = p.strip()
                if p.startswith("json"):
                    p = p[4:].strip()
                if p.startswith("["):
                    content = p
                    break

        first_sq = content.find("[")
        last_sq = content.rfind("]")
        if first_sq != -1 and last_sq > first_sq:
            content = content[first_sq : last_sq + 1]

        try:
            batch_questions = json.loads(content)
            if isinstance(batch_questions, list):
                all_questions.extend(batch_questions)
        except Exception as e:
            logger.warning(f"[Batch {batch_num} parse error] {e}")
            continue

    # Fallback default questions if parsing yielded empty
    if not all_questions:
        all_questions = [
            {
                "question_text": f"Explain the core mechanism of {source_hint} based on the study materials.",
                "question_type": "short_answer",
                "marks": 2,
                "difficulty": "medium",
                "options": [],
                "correct_answer": "Core mechanism involves progressive representation learning and feature extraction.",
                "explanation": "Study materials highlight the importance of layered abstraction.",
            }
        ]

    # Save all generated questions to DB
    saved_ids = []
    conn = get_db_connection()
    try:
        with conn:
            for q in all_questions:
                qid = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO generated_questions
                       (id, pattern_id, question_text, question_type, marks, difficulty,
                        options_json, correct_answer, explanation)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        qid,
                        req.pattern_id,
                        q.get("question_text", ""),
                        q.get("question_type", "MCQ"),
                        q.get("marks", 1),
                        q.get("difficulty", "medium"),
                        json.dumps(q.get("options", [])),
                        q.get("correct_answer", ""),
                        q.get("explanation", ""),
                    ),
                )
                saved_ids.append(qid)
    finally:
        conn.close()

    return {
        "pattern_id": req.pattern_id,
        "generated_count": len(all_questions),
        "question_ids": saved_ids,
        "questions": all_questions,
        "message": f"Generated {len(all_questions)} questions. Ready to practice!",
    }


@router.get("/list/{pattern_id}")
async def list_questions(pattern_id: str):
    """Get all generated questions for a pattern."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM generated_questions WHERE pattern_id = ? ORDER BY created_at",
            (pattern_id,),
        ).fetchall()
    finally:
        conn.close()

    questions = []
    for r in rows:
        questions.append({
            "id": r["id"],
            "question_text": r["question_text"],
            "question_type": r["question_type"],
            "marks": r["marks"],
            "difficulty": r["difficulty"],
            "options": json.loads(r["options_json"] or "[]"),
            "attempted": r["user_answer"] is not None,
        })
    return {"questions": questions, "total": len(questions)}


@router.post("/grade")
async def grade_answer(req: GradeRequest):
    """Grade a student's answer and provide explanation.

    Works for both MCQ and subjective questions.
    """
    conn = get_db_connection()
    try:
        q = conn.execute(
            "SELECT * FROM generated_questions WHERE id = ?", (req.question_id,)
        ).fetchone()
    finally:
        conn.close()

    if not q:
        return {"error": "Question not found"}

    # For MCQ — direct comparison
    if q["question_type"] == "MCQ":
        user_clean = req.user_answer.strip().upper()
        # handle "A", "A. ...", etc.
        user_opt = user_clean[0] if user_clean else ""
        correct_clean = q["correct_answer"].strip().upper()
        correct_opt = correct_clean[0] if correct_clean else ""
        is_correct = (user_opt == correct_opt) or (user_clean == correct_clean)
        explanation = q["explanation"]

    else:
        # For subjective — use LLM to grade
        grade_prompt = f"""Grade this student answer. Return ONLY a JSON object:
{{
  "is_correct": true,
  "score": 2,
  "feedback": "Clear explanation covering the main points.",
  "model_answer": "The ideal answer covers..."
}}

Question: {q['question_text']}
Expected Answer: {q['correct_answer']}
Student Answer: {req.user_answer}"""

        resp = await call_ollama(
            messages=[{"role": "user", "content": grade_prompt}],
            options={"temperature": 0.2, "num_ctx": 2000},
        )
        try:
            clean = resp.strip()
            if "```" in clean:
                clean = clean.split("```")[1]
                if clean.startswith("json"):
                    clean = clean[4:]
            first_b = clean.find("{")
            last_b = clean.rfind("}")
            grade_data = json.loads(clean[first_b : last_b + 1])
            is_correct = grade_data.get("is_correct", False)
            explanation = (
                grade_data.get("feedback", "")
                + "\n\n**Model Answer:** "
                + grade_data.get("model_answer", "")
            )
        except Exception:
            is_correct = False
            explanation = resp

    # Save attempt to DB
    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                """UPDATE generated_questions
                   SET user_answer=?, is_correct=?, attempted_at=?
                   WHERE id=?""",
                (req.user_answer, int(is_correct), datetime.datetime.now(), req.question_id),
            )
    finally:
        conn.close()

    return {
        "question_id": req.question_id,
        "is_correct": is_correct,
        "correct_answer": q["correct_answer"],
        "explanation": explanation,
        "marks_awarded": q["marks"] if is_correct else 0,
    }
