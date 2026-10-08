from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models._base import CreatedAtMixin, PkMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class OrgMember(Base, PkMixin, CreatedAtMixin):
    __tablename__ = "org_members"
    __table_args__ = (UniqueConstraint("org_id", "user_id", name="uq_org_member"),)

    org_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("organizations.id"), index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), index=True
    )
    role: Mapped[str] = mapped_column(String, default="student")  # admin|teacher|student

    organization: Mapped["Organization"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="org_memberships")
