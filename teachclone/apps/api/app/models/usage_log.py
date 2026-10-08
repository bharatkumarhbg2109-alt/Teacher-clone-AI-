from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy import JSON
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._base import CreatedAtMixin, PkMixin


class UsageLog(Base, PkMixin, CreatedAtMixin):
    """Event log for quota metering."""

    __tablename__ = "usage_logs"
    __table_args__ = (
        Index("ix_usage_user_event_period", "user_id", "event_type", "billing_period"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), index=True
    )
    # source_processed | session_started | message_sent | quiz_generated |
    # checkpoint_generated | export_created
    event_type: Mapped[str] = mapped_column(String)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    billing_period: Mapped[str] = mapped_column(String, index=True)  # "2026-07"
