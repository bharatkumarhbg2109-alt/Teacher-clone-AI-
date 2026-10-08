from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy import JSON
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models._base import PkMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.org_member import OrgMember
    from app.models.teacher_profile import TeacherProfile
    from app.models.user import User


class Organization(Base, PkMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True, index=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), index=True
    )
    plan: Mapped[str] = mapped_column(String, default="institution")
    seat_limit: Mapped[int] = mapped_column(Integer, default=50)
    sso_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    sso_config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)

    owner: Mapped["User"] = relationship(foreign_keys=[owner_id])
    members: Mapped[list["OrgMember"]] = relationship(back_populates="organization")
    teacher_profiles: Mapped[list["TeacherProfile"]] = relationship(
        back_populates="organization"
    )
