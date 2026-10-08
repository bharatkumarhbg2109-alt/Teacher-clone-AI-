from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy import JSON
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models._base import PkMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.message import Message
    from app.models.quiz import Quiz
    from app.models.teacher_profile import TeacherProfile
    from app.models.user import User


class StudentSession(Base, PkMixin, TimestampMixin):
    __tablename__ = "student_sessions"

    student_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), index=True
    )
    teacher_profile_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("teacher_profiles.id"), index=True
    )

    # {level, stream, subject, goal, learning_style, prior_knowledge,
    #  learn_ahead, target_level}
    student_profile: Mapped[dict] = mapped_column(JSON)
    # May drift from the stated level as checkpoints reveal understanding.
    current_effective_level: Mapped[str | None] = mapped_column(String, nullable=True)

    # Per-concept mastery, updated by inline checkpoints (drives spaced review).
    concept_mastery: Mapped[list] = mapped_column(JSON, default=list)

    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    session_notes: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    student: Mapped["User"] = relationship(back_populates="sessions")
    teacher_profile: Mapped["TeacherProfile"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    quizzes: Mapped[list["Quiz"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
