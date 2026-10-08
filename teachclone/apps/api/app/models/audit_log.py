from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy import JSON
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._base import CreatedAtMixin, PkMixin


class AuditLog(Base, PkMixin, CreatedAtMixin):
    """Immutable action log for enterprise / compliance."""

    __tablename__ = "audit_logs"

    org_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("organizations.id"), nullable=True, index=True
    )
    actor_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("users.id"))
    actor_email: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String, index=True)
    resource_type: Mapped[str] = mapped_column(String)
    resource_id: Mapped[str] = mapped_column(String)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String, nullable=True)

    @classmethod
    def write(
        cls,
        db,
        user_id: uuid.UUID,
        actor_email: str,
        action: str,
        resource_type: str = "",
        resource_id: str = "",
        meta: dict | None = None,
        org_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        """Create and commit an audit log entry."""
        record = cls(
            actor_id=user_id,
            actor_email=actor_email,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            meta=meta or {},
            org_id=org_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(record)
