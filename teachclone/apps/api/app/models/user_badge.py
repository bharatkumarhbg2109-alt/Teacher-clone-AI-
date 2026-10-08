from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String, UniqueConstraint
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._base import CreatedAtMixin, PkMixin


class UserBadge(Base, PkMixin, CreatedAtMixin):
    __tablename__ = "user_badges"
    __table_args__ = (UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), index=True
    )
    badge_id: Mapped[str] = mapped_column(String)
