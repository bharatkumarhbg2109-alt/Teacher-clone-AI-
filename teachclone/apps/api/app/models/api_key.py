from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models._base import CreatedAtMixin, PkMixin

if TYPE_CHECKING:
    from app.models.user import User


class ApiKey(Base, PkMixin, CreatedAtMixin):
    __tablename__ = "api_keys"

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), index=True
    )
    key_hash: Mapped[str] = mapped_column(String(64), unique=True)
    key_prefix: Mapped[str] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    requests_today: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped["User"] = relationship(back_populates="api_keys")
