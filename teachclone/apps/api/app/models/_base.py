"""Shared column mixins for ORM models."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column


class PkMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        GUID, primary_key=True, default=uuid.uuid4
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
