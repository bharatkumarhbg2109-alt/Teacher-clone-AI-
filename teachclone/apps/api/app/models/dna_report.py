from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy import JSON
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models._base import PkMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.teacher_profile import TeacherProfile


class DnaReport(Base, PkMixin, TimestampMixin):
    """A generated Teacher DNA report (7-layer analysis + system prompt).

    The latest report is also mirrored onto ``TeacherProfile.style_profile`` /
    ``TeacherProfile.system_prompt``; this table keeps the full history and the
    exact model/language used for each extraction.
    """

    __tablename__ = "dna_reports"

    teacher_profile_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("teacher_profiles.id"), index=True
    )
    teacher_name: Mapped[str] = mapped_column(String, default="")
    analyzed_videos: Mapped[int] = mapped_column(Integer, default=0)
    total_words: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    model_used: Mapped[str | None] = mapped_column(String, nullable=True)

    # Full 7-layer DNA report (JSON) + the generated ultra-detailed prompt.
    report: Mapped[dict] = mapped_column(JSON)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)

    teacher_profile: Mapped["TeacherProfile"] = relationship()
