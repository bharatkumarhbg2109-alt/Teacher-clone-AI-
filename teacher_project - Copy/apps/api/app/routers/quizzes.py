"""Full quizzes + inline mid-lecture checkpoints (which adapt the teacher)."""
import copy
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.message import Message
from app.models.quiz import Quiz
from app.models.student_session import StudentSession
from app.models.user import User
from app.schemas.quiz import (
    CheckpointGenerateRequest,
    CheckpointSubmitResponse,
    QuizGenerateRequest,
    QuizResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from app.services import billing, gamification
from app.services.levels import LEVEL_LABELS, effective_level, step_level
from app.services.quiz_generator import quiz_generator
from app.services.retrieval import format_context_chunks, retrieve_context

router = APIRouter(tags=["quizzes"])


async def _session(db: AsyncSession, session_id: str, user: User) -> StudentSession:
    s = (
        await db.execute(select(StudentSession).where(StudentSession.id == session_id))
    ).scalar_one_or_none()
    if not s or s.student_id != user.id:
        raise HTTPException(404, "Session not found")
    return s


def _level_label(session: StudentSession) -> str:
    lvl = effective_level(session.student_profile, session.current_effective_level)
    return LEVEL_LABELS.get(lvl, lvl)


def _strip_answers(questions: list) -> list:
    out = copy.deepcopy(questions)
    for q in out:
        q.pop("correct_answer", None)
        q.pop("sample_answer", None)
        q.pop("explanation", None)
    return out


async def _context_text(session: StudentSession, query: str) -> str:
    results = await retrieve_context(query, str(session.teacher_profile_id), top_k=8)
    return format_context_chunks(results)


# --- Generation -------------------------------------------------------------
@router.post("/sessions/{session_id}/quiz", response_model=QuizResponse)
async def generate_quiz(
    session_id: str,
    payload: QuizGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Quiz:
    session = await _session(db, session_id, user)
    ok, reason = await billing.check_quota(db, user, "quiz_generated")
    if not ok:
        raise HTTPException(402, detail={"error": "quota_exceeded", "reason": reason})

    subject = session.student_profile.get("subject", "the subject")
    query = payload.topic or session.student_profile.get("goal") or subject
    ctx = await _context_text(session, query)
    data = await quiz_generator.generate_full(
        ctx, _level_label(session), subject, payload.topic, payload.num_questions
    )
    quiz = Quiz(
        session_id=session.id,
        teacher_profile_id=session.teacher_profile_id,
        kind="full",
        questions=data["questions"],
    )
    db.add(quiz)
    await db.flush()
    await billing.log_usage(db, user.id, "quiz_generated")

    return QuizResponse(
        id=quiz.id, session_id=quiz.session_id, kind="full",
        questions=_strip_answers(quiz.questions), score=None,
        completed_at=None, created_at=quiz.created_at,
    )


@router.post("/sessions/{session_id}/checkpoint", response_model=QuizResponse)
async def generate_checkpoint(
    session_id: str,
    payload: CheckpointGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Quiz:
    session = await _session(db, session_id, user)

    concept = payload.concept
    if not concept:
        last = (
            await db.execute(
                select(Message)
                .where(Message.session_id == session.id, Message.role == "assistant")
                .order_by(Message.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        concept = (last.content[:200] if last else session.student_profile.get("goal", "the last topic"))

    subject = session.student_profile.get("subject", "the subject")
    ctx = await _context_text(session, concept)
    data = await quiz_generator.generate_checkpoint(
        ctx, _level_label(session), subject, concept, payload.num_questions
    )
    quiz = Quiz(
        session_id=session.id,
        teacher_profile_id=session.teacher_profile_id,
        kind="checkpoint",
        questions=data["questions"],
    )
    db.add(quiz)
    await db.flush()
    return QuizResponse(
        id=quiz.id, session_id=quiz.session_id, kind="checkpoint",
        questions=_strip_answers(quiz.questions), score=None,
        completed_at=None, created_at=quiz.created_at,
    )


# --- Grading ----------------------------------------------------------------
async def _grade(quiz: Quiz, answers: dict, level_label: str) -> tuple[float, dict, dict]:
    """Returns (score, results_by_qid, per_concept {concept: (correct, total)})."""
    results: dict = {}
    concept_stats: dict[str, list[int]] = {}
    total = 0.0
    for q in quiz.questions:
        qid = q.get("id")
        ans = answers.get(qid)
        if ans is None:
            continue
        if q.get("type") == "short_answer":
            r = await quiz_generator.grade_short_answer(q, str(ans), level_label)
        else:
            r = quiz_generator.grade_objective(q, ans)
        results[qid] = r
        total += r["score"]
        c = q.get("concept", "general")
        stat = concept_stats.setdefault(c, [0, 0])
        stat[1] += 1
        if r["is_correct"]:
            stat[0] += 1
    score = total / max(len(results), 1)
    return score, results, concept_stats


def _update_mastery(session: StudentSession, concept_stats: dict) -> tuple[list[str], list[str]]:
    mastery = {m["concept"]: m for m in (session.concept_mastery or [])}
    mastered, review = [], []
    now = datetime.now(timezone.utc).isoformat()
    for concept, (correct, total) in concept_stats.items():
        m = mastery.get(concept, {"concept": concept, "attempts": 0, "correct": 0, "state": "unseen"})
        m["attempts"] += total
        m["correct"] += correct
        ratio = correct / max(total, 1)
        m["state"] = "mastered" if ratio >= 0.8 else ("shaky" if ratio >= 0.5 else "review")
        m["last_seen_at"] = now
        mastery[concept] = m
        if m["state"] == "mastered":
            mastered.append(concept)
        elif m["state"] == "review":
            review.append(concept)
    session.concept_mastery = list(mastery.values())
    return mastered, review


@router.post("/quizzes/{quiz_id}/submit", response_model=QuizSubmitResponse)
async def submit_quiz(
    quiz_id: str,
    payload: QuizSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> QuizSubmitResponse:
    quiz = (
        await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    ).scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    session = await _session(db, str(quiz.session_id), user)

    score, results, _ = await _grade(quiz, payload.answers, _level_label(session))
    quiz.student_answers = payload.answers
    quiz.grading_results = results
    quiz.score = score
    quiz.completed_at = datetime.now(timezone.utc)
    await db.flush()

    await gamification.award_xp(db, user.id, "quiz_completed")
    if score >= 0.999:
        await gamification.award_xp(db, user.id, "perfect_quiz")
    await db.flush()

    return QuizSubmitResponse(score=score, results=results, completed_at=quiz.completed_at)


@router.post("/checkpoints/{quiz_id}/submit", response_model=CheckpointSubmitResponse)
async def submit_checkpoint(
    quiz_id: str,
    payload: QuizSubmitRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CheckpointSubmitResponse:
    quiz = (
        await db.execute(select(Quiz).where(Quiz.id == quiz_id))
    ).scalar_one_or_none()
    if not quiz or quiz.kind != "checkpoint":
        raise HTTPException(404, "Checkpoint not found")
    session = await _session(db, str(quiz.session_id), user)

    level_label = _level_label(session)
    score, results, concept_stats = await _grade(quiz, payload.answers, level_label)
    quiz.student_answers = payload.answers
    quiz.grading_results = results
    quiz.score = score
    quiz.completed_at = datetime.now(timezone.utc)

    mastered, review = _update_mastery(session, concept_stats)

    # Adapt the teacher based on performance.
    current = effective_level(session.student_profile, session.current_effective_level)
    if score >= 0.8:
        adapt = "deeper"
        session.current_effective_level = step_level(current, "deeper")
    elif score <= 0.4:
        adapt = "reteach"
        session.current_effective_level = step_level(current, "simpler")
    else:
        adapt = "hold"
        session.current_effective_level = current
    await db.flush()

    if score >= 0.6:
        await gamification.award_xp(db, user.id, "checkpoint_passed")
    await db.flush()

    return CheckpointSubmitResponse(
        score=score,
        results=results,
        adapt=adapt,
        updated_level=session.current_effective_level,
        mastered_concepts=mastered,
        review_concepts=review,
    )


@router.get("/quizzes/{quiz_id}/results", response_model=QuizResponse)
async def quiz_results(
    quiz_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Quiz:
    quiz = (await db.execute(select(Quiz).where(Quiz.id == quiz_id))).scalar_one_or_none()
    if not quiz:
        raise HTTPException(404, "Quiz not found")
    await _session(db, str(quiz.session_id), user)
    if not quiz.completed_at:
        raise HTTPException(400, "Quiz not completed yet")
    return quiz
