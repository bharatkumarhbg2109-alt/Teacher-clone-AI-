from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String
from app.db.types import GUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models._base import PkMixin, TimestampMixin


class TeacherShare(Base, PkMixin, TimestampMixin):
    """A shareable link to a teacher profile.

    The link itself lives on ``TeacherProfile.share_token``; this table records
    each share (mode, creator, access stats) so links can be audited/revoked
    and we can tell who forked what.
    """

    __tablename__ = "teacher_shares"

    teacher_profile_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("teacher_profiles.id"), index=True
    )
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    mode: Mapped[str] = mapped_column(String, default="clone")  # clone|view
    created_by: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("users.id"), index=True
    )
    # Optional: also carry the sharer's session history/notes into the copy.
    include_history: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    open_count: Mapped[int] = mapped_column(Integer, default=0)
    fork_count: Mapped[int] = mapped_column(Integer, default=0)
