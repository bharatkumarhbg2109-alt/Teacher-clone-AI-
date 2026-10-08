"""Open and start a shared teacher via its link.

- view mode  → the friend learns from the original teacher (read-only, zero-copy).
- clone mode → the friend gets a personal copy carrying the same knowledge/style/voice.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.teacher_profile import TeacherProfile
from app.models.teacher_share import TeacherShare
from app.models.user import User
from app.schemas.teacher_profile import TeacherProfileResponse

router = APIRouter(tags=["share"])


async def _resolve(db: AsyncSession, token: str) -> TeacherProfile:
    profile = (
        await db.execute(
            select(TeacherProfile).where(
                TeacherProfile.share_token == token,
                TeacherProfile.share_enabled.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "This share link is invalid or has been revoked")
    return profile


@router.get("/t/{token}", response_model=TeacherProfileResponse)
async def open_share(
    token: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeacherProfile:
    profile = await _resolve(db, token)
    share = (
        await db.execute(
            select(TeacherShare).where(
                TeacherShare.token == token, TeacherShare.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if share:
        share.open_count += 1
        await db.flush()
    return profile


@router.post("/t/{token}/start")
async def start_share(
    token: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    profile = await _resolve(db, token)

    # View mode: learn directly from the original teacher.
    if profile.share_mode == "view":
        return {"teacher_profile_id": str(profile.id), "mode": "view", "cloning": False}

    # Clone mode: fork a personal copy carrying the same memory.
    fork = TeacherProfile(
        user_id=user.id,
        name=f"{profile.name} (shared copy)",
        description=profile.description,
        subject=profile.subject,
        tts_voice=profile.tts_voice,
        style_profile=profile.style_profile,
        total_sources=profile.total_sources,
        visibility="private",
        forked_from_id=profile.id,
    )
    db.add(fork)
    await db.flush()

    share = (
        await db.execute(
            select(TeacherShare).where(
                TeacherShare.token == token, TeacherShare.is_active.is_(True)
            )
        )
    ).scalar_one_or_none()
    if share:
        share.fork_count += 1
    await db.commit()  # release the write lock before in-process cloning

    # Copy the knowledge base (and re-embed under the fork) in the background.
    from app.tasks.dispatch import dispatch
    from app.tasks.share_tasks import clone_teacher_knowledge

    await dispatch(clone_teacher_knowledge, str(profile.id), str(fork.id))

    return {"teacher_profile_id": str(fork.id), "mode": "clone", "cloning": True}
