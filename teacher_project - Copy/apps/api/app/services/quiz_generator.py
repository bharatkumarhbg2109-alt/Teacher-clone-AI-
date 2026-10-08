"""Quiz + checkpoint generation and grading.

- ``generate_full``: a student-triggered quiz (mix of MCQ / TF / short answer).
- ``generate_checkpoint``: a tiny inline mid-lecture check (1-2 quick questions)
  that drives adaptation.
Grading is auto for objective questions and Claude-graded for short answers.
"""
import uuid

from app.services import llm

_QUESTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "type": {"type": "string", "enum": ["mcq", "true_false", "short_answer"]},
        "concept": {"type": "string"},
        "question": {"type": "string"},
        "options": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "A": {"type": "string"},
                "B": {"type": "string"},
                "C": {"type": "string"},
                "D": {"type": "string"},
            },
        },
        "correct_answer": {"type": "string"},  # "A".."D" or "true"/"false"
        "sample_answer": {"type": "string"},
        "key_concepts": {"type": "array", "items": {"type": "string"}},
        "explanation": {"type": "string"},
        "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
        "source_page": {"type": "integer"},
    },
    "required": ["type", "question", "explanation", "concept"],
}

_QUIZ_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "questions": {"type": "array", "items": _QUESTION_SCHEMA},
    },
    "required": ["title", "questions"],
}

_GRADE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "score": {"type": "number"},
        "is_correct": {"type": "boolean"},
        "feedback": {"type": "string"},
    },
    "required": ["score", "is_correct", "feedback"],
}


def _normalize(quiz: dict) -> dict:
    for i, q in enumerate(quiz.get("questions", []), 1):
        q.setdefault("id", f"q{i}")
    return quiz


class QuizGenerator:
    async def generate_full(
        self, context_text: str, level_label: str, subject: str, topic: str | None, num: int
    ) -> dict:
        prompt = (
            f"Generate a {num}-question quiz for a {level_label} student studying {subject}"
            f"{f' on: {topic}' if topic else ''}.\n\n"
            f"CONTENT TO TEST (answer only from this):\n{context_text}\n\n"
            "Mix: ~60% MCQ (options A-D, one correct), ~20% true/false "
            "(correct_answer 'true'/'false'), ~20% short answer (give a sample_answer and "
            "key_concepts). Calibrate difficulty and vocabulary to the student's level. "
            "Tag each question with the 'concept' it tests."
        )
        return _normalize(await llm.complete_json(prompt, _QUIZ_SCHEMA, max_tokens=3000))

    async def generate_checkpoint(
        self, context_text: str, level_label: str, subject: str, concept: str, num: int = 2
    ) -> dict:
        prompt = (
            f"The student ({level_label}, studying {subject}) was just taught: {concept}.\n"
            f"Create a {num}-question quick checkpoint to verify understanding — prefer MCQ / "
            "true-false (fast to answer). Keep it tightly on that concept.\n\n"
            f"REFERENCE:\n{context_text}\n\nTag each question's 'concept'."
        )
        return _normalize(await llm.complete_json(prompt, _QUIZ_SCHEMA, max_tokens=1200))

    def grade_objective(self, question: dict, answer) -> dict:
        correct = str(question.get("correct_answer", "")).strip().lower()
        given = str(answer).strip().lower()
        is_correct = given == correct
        return {
            "is_correct": is_correct,
            "score": 1.0 if is_correct else 0.0,
            "feedback": question.get("explanation", ""),
            "correct_answer": question.get("correct_answer"),
        }

    async def grade_short_answer(self, question: dict, answer: str, level_label: str) -> dict:
        prompt = (
            f"Grade this {level_label} student's short answer.\n\n"
            f"QUESTION: {question.get('question')}\n"
            f"SAMPLE ANSWER: {question.get('sample_answer', '')}\n"
            f"KEY CONCEPTS: {', '.join(question.get('key_concepts', []))}\n\n"
            f"STUDENT ANSWER: {answer}\n\n"
            "Return score 0-1, is_correct (score>=0.7), and 1-2 sentences of feedback at "
            "the student's level."
        )
        try:
            res = await llm.complete_json(prompt, _GRADE_SCHEMA, max_tokens=500)
            res["correct_answer"] = question.get("sample_answer")
            return res
        except Exception:
            return {"is_correct": False, "score": 0.0, "feedback": "Could not grade.", "correct_answer": None}


quiz_generator = QuizGenerator()
