from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models._base import CreatedAtMixin, PkMixin

if TYPE_CHECKING:
    from app.models.media_source import MediaSource


class TranscriptChunk(Base, PkMixin, CreatedAtMixin):
    """A retrievable knowledge chunk. Works for audio/video (timestamps),
    documents (page numbers), and visual content (diagrams/slides)."""

    __tablename__ = "transcript_chunks"
    __table_args__ = (
        Index("ix_chunk_source_index", "media_source_id", "chunk_index"),
    )

    media_source_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("media_sources.id"), index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)

    # Locators — timestamps for media, page for documents (nullable each).
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)

    speaker_label: Mapped[str | None] = mapped_column(String, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    embedding_id: Mapped[str | None] = mapped_column(String, nullable=True)
    # audio | document | visual
    content_type: Mapped[str] = mapped_column(String, default="audio")

    media_source: Mapped["MediaSource"] = relationship(back_populates="chunks")
