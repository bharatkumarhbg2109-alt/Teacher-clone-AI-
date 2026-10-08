from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.models.user_badge import UserBadge
from app.models.user_stats import UserStats
from app.schemas.user import UserResponse, UserStatsResponse, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)) -> User:
    return user


@router.put("/me", response_model=UserResponse)
async def update_me(
    payload: UserUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.avatar_url is not None:
        user.avatar_url = payload.avatar_url
    await db.flush()
    return user


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_my_stats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserStatsResponse:
    stats = (
        await db.execute(select(UserStats).where(UserStats.user_id == user.id))
    ).scalar_one_or_none()
    if not stats:
        stats = UserStats(user_id=user.id)
        db.add(stats)
        await db.flush()

    badges = (
        (await db.execute(select(UserBadge).where(UserBadge.user_id == user.id)))
        .scalars()
        .all()
    )
    resp = UserStatsResponse.model_validate(stats)
    resp.badges = [
        {"badge_id": b.badge_id, "earned_at": b.created_at} for b in badges
    ]
    return resp
