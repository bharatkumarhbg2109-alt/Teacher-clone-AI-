from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class QuizGenerateRequest(BaseModel):
    topic: str | None = None
    num_questions: int = Field(default=5, ge=1, le=20)


class CheckpointGenerateRequest(BaseModel):
    concept: str | None = None
    num_questions: int = Field(default=2, ge=1, le=4)


class QuizSubmitRequest(BaseModel):
    answers: dict[str, Any]  # question_id -> answer


class GradingResultResponse(BaseModel):
    is_correct: bool
    score: float
    feedback: str
    correct_answer: Any | None = None


class QuizResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    kind: str
    questions: list
    score: float | None = None
    completed_at: datetime | None = None
    created_at: datetime


class QuizSubmitResponse(BaseModel):
    score: float
    results: dict[str, GradingResultResponse]
    completed_at: datetime | None = None


class CheckpointSubmitResponse(BaseModel):
    score: float
    results: dict[str, GradingResultResponse]
    # Adaptation the teacher applies next.
    adapt: str  # simpler|deeper|reteach|hold
    updated_level: str
    mastered_concepts: list[str] = []
    review_concepts: list[str] = []
