import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.teacher_profile import TeacherProfileResponse

_LEVEL_CHOICES = Literal[
    "class_6_8", "class_9_10", "class_11_12", "undergrad", "postgrad", "professional"
]
_STREAM_CHOICES = Literal[
    "science", "commerce", "arts", "engineering", "medical", "law", "business", "other", None
]
_LEARNING_STYLE = Literal["examples", "theory", "qa", "storytelling"]


def _no_injection(value: str | None, field_name: str) -> str | None:
    if value is None:
        return value
    pattern = re.compile(r"<script|javascript:|data:text/html|on\w+\s*=", re.IGNORECASE)
    if pattern.search(value):
        raise ValueError(f"{field_name} contains disallowed content")
    return value


class StudentProfileInput(BaseModel):
    level: _LEVEL_CHOICES = "undergrad"
    stream: Literal["science", "commerce", "arts", "engineering", "medical", "law", "business", "other"] | None = None
    subject: str = Field(default="General", min_length=1, max_length=100)
    goal: str = Field(default="", max_length=500)
    learning_style: _LEARNING_STYLE = "examples"
    prior_knowledge: str = Field(default="", max_length=1000)
    learn_ahead: bool = False
    target_level: _LEVEL_CHOICES | None = None

    @field_validator("subject", "goal", "prior_knowledge")
    @classmethod
    def no_script_tags(cls, v: str | None) -> str | None:
        return _no_injection(v, "subject/goal/prior_knowledge")


class SessionCreate(BaseModel):
    teacher_profile_id: str = Field(min_length=1, max_length=100)
    student_profile: StudentProfileInput


class MessagePreview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    citations: list = []
    audio_url: str | None = None
    created_at: datetime


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teacher_profile_id: UUID
    student_profile: dict
    current_effective_level: str | None = None
    concept_mastery: list = []
    message_count: int
    created_at: datetime
    teacher_profile: TeacherProfileResponse | None = None
    messages: list[MessagePreview] | None = None


class SessionListItem(BaseModel):
    """Lightweight session row (no relationships — safe for async listing)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teacher_profile_id: UUID
    student_profile: dict
    current_effective_level: str | None = None
    message_count: int
    created_at: datetime


class AdjustLevelRequest(BaseModel):
    direction: Literal["simpler", "deeper"]


class AdjustLevelResponse(BaseModel):
    level: str
