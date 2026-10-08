from __future__ import annotations

import uuid

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.db.types import GUID


class ChunkVector(Base):
    """Embedding store for the local (no-Qdrant) vector backend.

    One row per embedded chunk; retrieval does brute-force cosine similarity.
    Only used when VECTOR_BACKEND=local.
    """

    __tablename__ = "chunk_vectors"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True)
    teacher_profile_id: Mapped[uuid.UUID] = mapped_column(GUID, index=True)
    media_source_id: Mapped[uuid.UUID] = mapped_column(GUID, index=True)
    content_type: Mapped[str] = mapped_column(String, default="audio")
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(JSON)
