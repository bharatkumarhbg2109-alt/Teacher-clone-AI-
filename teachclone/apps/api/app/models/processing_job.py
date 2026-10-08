from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import JSON
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models._base import CreatedAtMixin, PkMixin

if TYPE_CHECKING:
    from app.models.media_source import MediaSource


class ProcessingJob(Base, PkMixin, CreatedAtMixin):
    __tablename__ = "processing_jobs"

    media_source_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("media_sources.id"), index=True
    )
    # transcription | extraction | embedding | style_extraction | frame_analysis
    job_type: Mapped[str] = mapped_column(String)
    celery_task_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(
        String, default="queued", index=True
    )  # queued|running|completed|failed
    progress: Mapped[int] = mapped_column(Integer, default=0)
    result_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    media_source: Mapped["MediaSource"] = relationship(back_populates="jobs")
