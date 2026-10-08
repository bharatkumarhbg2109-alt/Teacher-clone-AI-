from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Integer
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserStats(Base):
    """One-to-one gamification stats per user."""

    __tablename__ = "user_stats"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), primary_key=True
    )
    xp_total: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_session_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    sessions_completed: Mapped[int] = mapped_column(Integer, default=0)
    quizzes_completed: Mapped[int] = mapped_column(Integer, default=0)
    perfect_quizzes: Mapped[int] = mapped_column(Integer, default=0)
    sources_processed: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="stats")
