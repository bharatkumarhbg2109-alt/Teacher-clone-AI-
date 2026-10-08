from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clerk_id: str
    email: str
    full_name: str
    avatar_url: str | None = None
    plan: str
    created_at: datetime


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=200)
    avatar_url: str | None = Field(default=None, max_length=500)


class BadgeResponse(BaseModel):
    badge_id: str
    earned_at: datetime


class UserStatsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    xp_total: int
    level: int
    streak_days: int
    longest_streak: int
    sessions_completed: int
    quizzes_completed: int
    perfect_quizzes: int
    sources_processed: int
    badges: list[BadgeResponse] = []
