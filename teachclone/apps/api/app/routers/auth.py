from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.user_stats import UserStats
from app.schemas.user import UserResponse
from sqlalchemy import select

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/sync", response_model=UserResponse)
async def sync_user(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Ensure the authenticated user (and their stats row) exists in the DB.

    Called by the frontend after sign-in. In DEV_MODE this returns the local
    dev user. Under Clerk, the webhook usually creates the user first; this is
    an idempotent safety net.
    """
    stats = (
        await db.execute(select(UserStats).where(UserStats.user_id == user.id))
    ).scalar_one_or_none()
    if not stats:
        db.add(UserStats(user_id=user.id))
        await db.flush()
    AuditLog.write(db, user.id, user.email, "user.login", "user", str(user.id))
    return user
