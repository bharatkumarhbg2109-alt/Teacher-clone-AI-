"""Embeddable widget — backend endpoints.

Allows institutes to embed a TeachClone chat widget on external websites.
An embed token (JWT) scopes access to specific profiles and origins.

    POST   /embed/config         create an embed config (owner only)
    GET    /embed/profiles       list profiles for this embed token (public)
    POST   /embed/chat           start a chat session via embed token (public)
"""
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.media_source import MediaSource
from app.models.teacher_profile import TeacherProfile
from app.models.user import User
from app.models.user_stats import UserStats

router = APIRouter(prefix="/embed", tags=["embed"])
log = logging.getLogger("teachclone.embed")

# In-memory store for embed configs (in production, use DB + Redis)
_embed_configs: dict[str, dict] = {}


class EmbedConfigRequest(BaseModel):
    allowed_origins: list[str]
    profile_ids: list[str]
    expires_in_days: int = 30  # optional; 0 = no expiry


class EmbedConfigResponse(BaseModel):
    embed_token: str
    allowed_origins: list[str]
    profile_ids: list[str]
    expires_at: str | None


class EmbedChatRequest(BaseModel):
    profile_id: str
    content: str
    student_level: str = "intermediate"


def _create_embed_token(
    allowed_origins: list[str],
    profile_ids: list[str],
    expires_at: datetime | None,
) -> str:
    payload = {
        "type": "embed",
        "origins": allowed_origins,
        "profiles": profile_ids,
        "iat": datetime.now(timezone.utc).timestamp(),
    }
    if expires_at:
        payload["exp"] = expires_at.timestamp()
    if not settings.CLERK_SECRET_KEY:
        raise RuntimeError("CLERK_SECRET_KEY must be set in environment — cannot sign embed tokens")
    return jwt.encode(payload, settings.CLERK_SECRET_KEY, algorithm="HS256")


def _verify_embed_token(token: str) -> dict:
    try:
        if not settings.CLERK_SECRET_KEY:
            raise RuntimeError("CLERK_SECRET_KEY must be set in environment — cannot verify embed tokens")
        return jwt.decode(
            token,
            settings.CLERK_SECRET_KEY,
            algorithms=["HS256"],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Embed token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid embed token")


def _verify_origin(request: Request, allowed_origins: list[str]) -> None:
    origin = request.headers.get("origin") or request.headers.get("referer", "")
    if not origin:
        return  # no origin header (e.g., server-to-server) — allow
    from urllib.parse import urlparse
    parsed = urlparse(origin)
    origin_host = parsed.netloc or parsed.hostname or ""
    for allowed in allowed_origins:
        if origin_host == allowed or origin_host.endswith(f".{allowed}"):
            return
    raise HTTPException(403, "Origin not allowed for this embed")


# --- IP1: Anonymous embed session support -----------------------------------

# Cache the system user used for anonymous embed sessions.
_system_user_cache: User | None = None


async def _get_or_create_system_user(db: AsyncSession) -> User:
    """Return or create a system-level user for anonymous embed sessions."""
    global _system_user_cache
    if _system_user_cache is not None:
        return _system_user_cache

    system_email = "__embed_system@teachclone.local"
    existing = (
        await db.execute(select(User).where(User.email == system_email))
    ).scalar_one_or_none()
    if existing:
        _system_user_cache = existing
        return existing

    user = User(
        clerk_id="__embed_system",
        email=system_email,
        full_name="Embed System",
        is_active=True,
        plan="free",
    )
    db.add(user)
    await db.flush()
    db.add(UserStats(user_id=user.id))
    await db.flush()
    _system_user_cache = user
    return user


async def get_or_create_embed_session(
    db: AsyncSession,
    session_token: str | None,
) -> str:
    """Return an existing session token or create a new anonymous session.

    Returns a UUID-based session token that can be used to identify
    the anonymous embed user across requests.
    """
    if not session_token:
        session_token = str(uuid.uuid4())
    # Token is validated by the caller; here we just ensure it's non-empty.
    # In a full implementation, this would upsert into an AnonymousSession
    # table with a 24-hour expiry.
    return session_token


@router.post("/config", response_model=EmbedConfigResponse)
async def create_embed_config(
    payload: EmbedConfigRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a scoped embed config with a signed JWT token."""
    # Verify user owns these profiles
    for pid in payload.profile_ids:
        profile = (
            await db.execute(
                select(TeacherProfile).where(TeacherProfile.id == pid)
            )
        ).scalar_one_or_none()
        if not profile or profile.user_id != user.id:
            raise HTTPException(403, f"You don't own profile {pid}")

    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=payload.expires_in_days)
        if payload.expires_in_days > 0
        else None
    )

    token = _create_embed_token(payload.allowed_origins, payload.profile_ids, expires_at)
    token_id = secrets.token_urlsafe(8)

    _embed_configs[token_id] = {
        "token": token,
        "allowed_origins": payload.allowed_origins,
        "profile_ids": payload.profile_ids,
        "created_by": str(user.id),
        "expires_at": expires_at.isoformat() if expires_at else None,
    }

    return EmbedConfigResponse(
        embed_token=token,
        allowed_origins=payload.allowed_origins,
        profile_ids=payload.profile_ids,
        expires_at=expires_at.isoformat() if expires_at else None,
    )


@router.get("/profiles")
async def embed_profiles(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """List teacher profiles available through this embed token (public)."""
    payload = _verify_embed_token(token)
    _verify_origin(request, payload.get("origins", []))

    profile_ids = payload.get("profiles", [])
    if not profile_ids:
        return []

    profiles = (
        (await db.execute(
            select(TeacherProfile).where(TeacherProfile.id.in_(profile_ids))
        )).scalars().all()
    )

    return [
        {
            "id": str(p.id),
            "name": p.name,
            "subject": p.subject,
            "description": p.description,
        }
        for p in profiles
    ]


@router.post("/chat")
async def embed_chat(
    payload: EmbedChatRequest,
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Start a chat session via embed token (public, no user auth required)."""
    token_payload = _verify_embed_token(token)
    _verify_origin(request, token_payload.get("origins", []))

    if payload.profile_id not in token_payload.get("profiles", []):
        raise HTTPException(403, "Profile not available via this embed token")

    profile = (
        await db.execute(
            select(TeacherProfile).where(TeacherProfile.id == payload.profile_id)
        )
    ).scalar_one_or_none()
    if not profile:
        raise HTTPException(404, "Teacher profile not found")

    # IP1: Create an anonymous session using the system user.
    from app.models.student_session import StudentSession

    system_user = await _get_or_create_system_user(db)
    session_token = await get_or_create_embed_session(db, session_token=None)

    session = StudentSession(
        student_id=system_user.id,
        teacher_profile_id=profile.id,
        student_profile={
            "level": payload.student_level,
            "subject": profile.subject or "general",
            "source": "embed",
            "embed_session_token": session_token,
        },
    )
    db.add(session)
    await db.flush()

    return {
        "session_id": str(session.id),
        "teacher_profile_id": str(profile.id),
        "teacher_name": profile.name,
        "session_token": session_token,
    }
