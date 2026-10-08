from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy import JSON
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models._base import CreatedAtMixin, PkMixin

if TYPE_CHECKING:
    from app.models.student_session import StudentSession


class Quiz(Base, PkMixin, CreatedAtMixin):
    __tablename__ = "quizzes"

    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("student_sessions.id"), index=True
    )
    teacher_profile_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("teacher_profiles.id"), index=True
    )
    # full = student-triggered quiz; checkpoint = quick inline mid-lecture check
    kind: Mapped[str] = mapped_column(String, default="full")
    questions: Mapped[list] = mapped_column(JSON)
    student_answers: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    grading_results: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    session: Mapped["StudentSession"] = relationship(back_populates="quizzes")
