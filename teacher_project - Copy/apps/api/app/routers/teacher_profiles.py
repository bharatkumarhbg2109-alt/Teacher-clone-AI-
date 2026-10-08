"""Teacher profile CRUD + style + share-link management."""
import logging
import secrets
import uuid

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.audit_log import AuditLog
from app.models.media_source import MediaSource
from app.models.teacher_profile import TeacherProfile
from app.models.teacher_share import TeacherShare
from app.models.user import User
from app.schemas.teacher_profile import (
    ShareCreateRequest,
    ShareResponse,
    TeacherProfileCreate,
    TeacherProfileResponse,
    TeacherProfileUpdate,
)

router = APIRouter(tags=["profiles"])


async def get_owned_profile(db: AsyncSession, profile_id: str, user: User) -> TeacherProfile:
    profile = (
        await db.execute(select(TeacherProfile).where(TeacherProfile.id == profile_id))
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Teacher profile not found")
    if profile.user_id != user.id:
        raise HTTPException(403, "Not your teacher profile")
    return profile


@router.post("", response_model=TeacherProfileResponse, status_code=201)
async def create_profile(
    payload: TeacherProfileCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeacherProfile:
    profile = TeacherProfile(
        user_id=user.id,
        org_id=uuid.UUID(payload.org_id) if payload.org_id else None,
        name=payload.name,
        description=payload.description,
        subject=payload.subject,
        tts_voice=payload.tts_voice,
        visibility=payload.visibility,
    )
    db.add(profile)
    await db.flush()
    return profile


@router.get("", response_model=list[TeacherProfileResponse])
async def list_profiles(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TeacherProfile]:
    rows = (
        (await db.execute(
            select(TeacherProfile)
            .where(TeacherProfile.user_id == user.id)
            .order_by(TeacherProfile.created_at.desc())
        )).scalars().all()
    )
    return list(rows)


@router.get("/{profile_id}", response_model=TeacherProfileResponse)
async def get_profile(
    profile_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeacherProfile:
    profile = (
        await db.execute(select(TeacherProfile).where(TeacherProfile.id == profile_id))
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Teacher profile not found")
    # Owner, public, or unlisted (link) profiles are viewable.
    if profile.user_id != user.id and profile.visibility == "private":
        raise HTTPException(403, "This teacher profile is private")
    return profile


@router.put("/{profile_id}", response_model=TeacherProfileResponse)
async def update_profile(
    profile_id: str,
    payload: TeacherProfileUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TeacherProfile:
    profile = await get_owned_profile(db, profile_id, user)
    for field in ("name", "description", "subject", "tts_voice", "visibility"):
        val = getattr(payload, field)
        if val is not None:
            setattr(profile, field, val)
    await db.flush()
    return profile


@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    profile = await get_owned_profile(db, profile_id, user)
    # Clean up vectors + stored files.
    from app.services.storage import storage_service
    from app.services.vector_store import vector_store

    try:
        await vector_store.delete_by_teacher_profile(str(profile.id))
    except Exception as e:
        logger.warning("Vector cleanup failed for profile %s: %s. Manual cleanup may be needed.", profile.id, e)
    sources = (
        (await db.execute(
            select(MediaSource).where(MediaSource.teacher_profile_id == profile.id)
        )).scalars().all()
    )
    for s in sources:
        if s.storage_key:
            storage_service.delete_object(s.storage_key)
    await db.delete(profile)
    AuditLog.write(db, user.id, user.email, "profile.deleted", "teacher_profile", profile_id)
    await db.flush()
    return {"success": True}


@router.get("/{profile_id}/style")
async def get_style(
    profile_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    profile = await get_profile(profile_id, user, db)
    if not profile.style_profile:
        raise HTTPException(404, "Style not extracted yet")
    return profile.style_profile


# --- Sharing ----------------------------------------------------------------
@router.post("/{profile_id}/share", response_model=ShareResponse)
async def create_share(
    profile_id: str,
    payload: ShareCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShareResponse:
    profile = await get_owned_profile(db, profile_id, user)
    if not profile.share_token:
        profile.share_token = secrets.token_urlsafe(9)
    profile.share_enabled = True
    profile.share_mode = payload.mode
    if profile.visibility == "private":
        profile.visibility = "unlisted"
    db.add(
        TeacherShare(
            teacher_profile_id=profile.id,
            token=profile.share_token,
            mode=payload.mode,
            created_by=user.id,
            include_history=payload.include_history,
        )
    )
    await db.flush()
    return ShareResponse(
        share_token=profile.share_token,
        share_url=f"{settings.APP_URL}/t/{profile.share_token}",
        mode=profile.share_mode,
    )


@router.delete("/{profile_id}/share")
async def revoke_share(
    profile_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    profile = await get_owned_profile(db, profile_id, user)
    profile.share_enabled = False
    profile.share_token = None
    if profile.visibility == "unlisted":
        profile.visibility = "private"
    await db.flush()
    return {"success": True}
