from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models._base import PkMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.processing_job import ProcessingJob
    from app.models.teacher_profile import TeacherProfile
    from app.models.transcript_chunk import TranscriptChunk


class MediaSource(Base, PkMixin, TimestampMixin):
    __tablename__ = "media_sources"

    teacher_profile_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("teacher_profiles.id"), index=True
    )
    uploaded_by: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), index=True
    )
    # youtube_url | video_upload | audio_upload | pdf_upload | doc_upload | image_upload
    source_type: Mapped[str] = mapped_column(String)
    original_url: Mapped[str | None] = mapped_column(String, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String, nullable=True)
    file_name: Mapped[str | None] = mapped_column(String, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)

    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    status: Mapped[str] = mapped_column(
        String, default="pending", index=True
    )  # pending|processing|completed|failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_chunks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    processing_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    teacher_profile: Mapped["TeacherProfile"] = relationship(
        back_populates="media_sources"
    )
    chunks: Mapped[list["TranscriptChunk"]] = relationship(
        back_populates="media_source", cascade="all, delete-orphan"
    )
    jobs: Mapped[list["ProcessingJob"]] = relationship(
        back_populates="media_source", cascade="all, delete-orphan"
    )
