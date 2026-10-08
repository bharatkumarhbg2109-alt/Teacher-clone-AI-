from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy import JSON
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models._base import CreatedAtMixin, PkMixin

if TYPE_CHECKING:
    from app.models.student_session import StudentSession


class Message(Base, PkMixin, CreatedAtMixin):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_message_session_created", "session_id", "created_at"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("student_sessions.id"), index=True
    )
    role: Mapped[str] = mapped_column(String)  # user|assistant
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    # Cached TTS rendering of the assistant message (audio output).
    audio_url: Mapped[str | None] = mapped_column(String, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String, nullable=True)

    session: Mapped["StudentSession"] = relationship(back_populates="messages")
