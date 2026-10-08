import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _no_injection(value: str | None, field_name: str) -> str | None:
    """Reject inputs containing obvious injection patterns."""
    if value is None:
        return value
    pattern = re.compile(r"<script|javascript:|data:text/html|on\w+\s*=", re.IGNORECASE)
    if pattern.search(value):
        raise ValueError(f"{field_name} contains disallowed content")
    return value


class TeacherProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    subject: str | None = Field(default=None, max_length=100)
    tts_voice: str = Field(default="nova", max_length=50)
    visibility: Literal["private", "unlisted", "public"] = "private"
    org_id: str | None = Field(default=None, max_length=100)

    @field_validator("name", "description", "subject")
    @classmethod
    def no_script_tags(cls, v: str | None) -> str | None:
        return _no_injection(v, "name/description/subject")


class TeacherProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    subject: str | None = Field(default=None, max_length=100)
    tts_voice: str | None = Field(default=None, max_length=50)
    visibility: Literal["private", "unlisted", "public"] | None = None

    @field_validator("name", "description", "subject")
    @classmethod
    def no_script_tags(cls, v: str | None) -> str | None:
        return _no_injection(v, "name/description/subject")


class TeacherProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None = None
    org_id: UUID | None = None
    name: str
    description: str | None = None
    subject: str | None = None
    tts_voice: str
    style_profile: dict | None = None
    total_sources: int
    visibility: str
    share_token: str | None = None
    share_enabled: bool
    share_mode: str
    forked_from_id: UUID | None = None
    session_count: int
    unique_learners: int
    created_at: datetime


class ShareCreateRequest(BaseModel):
    mode: Literal["clone", "view"] = "clone"
    include_history: bool = False


class ShareResponse(BaseModel):
    share_token: str
    share_url: str
    mode: str
