from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models._base import PkMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.api_key import ApiKey
    from app.models.org_member import OrgMember
    from app.models.student_session import StudentSession
    from app.models.teacher_profile import TeacherProfile
    from app.models.user_stats import UserStats


class User(Base, PkMixin, TimestampMixin):
    __tablename__ = "users"

    clerk_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String, default="")
    avatar_url: Mapped[str | None] = mapped_column(String, nullable=True)
    plan: Mapped[str] = mapped_column(String, default="free")  # free|pro|creator|institution
    stripe_customer_id: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    teacher_profiles: Mapped[list["TeacherProfile"]] = relationship(
        back_populates="user", foreign_keys="TeacherProfile.user_id"
    )
    sessions: Mapped[list["StudentSession"]] = relationship(back_populates="student")
    org_memberships: Mapped[list["OrgMember"]] = relationship(back_populates="user")
    stats: Mapped["UserStats | None"] = relationship(
        back_populates="user", uselist=False
    )
    api_keys: Mapped[list["ApiKey"]] = relationship(back_populates="user")
