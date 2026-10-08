"""Discovery — the 'most used teacher' directory for students with no material."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.teacher_profile import TeacherProfile
from app.models.user import User
from app.schemas.teacher_profile import TeacherProfileResponse

router = APIRouter(prefix="/discover", tags=["discover"])


@router.get("/teachers", response_model=list[TeacherProfileResponse])
async def popular_teachers(
    sort: str = Query(default="most_used", max_length=20),
    subject: str | None = Query(default=None, max_length=100),
    q: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=24, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TeacherProfile]:
    query = select(TeacherProfile).where(TeacherProfile.visibility == "public")
    if subject:
        query = query.where(TeacherProfile.subject.ilike(f"%{subject}%"))
    if q:
        query = query.where(
            or_(TeacherProfile.name.ilike(f"%{q}%"), TeacherProfile.description.ilike(f"%{q}%"))
        )
    if sort == "newest":
        query = query.order_by(TeacherProfile.created_at.desc())
    else:  # most_used
        query = query.order_by(
            TeacherProfile.unique_learners.desc(), TeacherProfile.session_count.desc()
        )
    rows = (await db.execute(query.limit(limit))).scalars().all()
    return list(rows)
