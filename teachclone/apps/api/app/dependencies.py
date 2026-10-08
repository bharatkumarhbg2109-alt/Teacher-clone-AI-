"""FastAPI dependencies: DB session, auth, plan gating, API-key auth.

When ``settings.DEV_MODE`` is true, auth is bypassed and a local dev user is
used, so the product runs without Clerk. Set DEV_MODE=false for real auth.
"""
import hashlib
from datetime import datetime
from typing import AsyncGenerator

import httpx
import jwt
from cachetools import TTLCache
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.models.api_key import ApiKey
from app.models.user import User
from app.models.user_stats import UserStats


# ----------------------------------------------------------------------------
#  DB session
# ----------------------------------------------------------------------------
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ----------------------------------------------------------------------------
#  Clerk JWT verification (used when DEV_MODE is off)
# ----------------------------------------------------------------------------
_jwks_cache: TTLCache = TTLCache(maxsize=1, ttl=3600)


async def _get_jwks() -> dict:
    if "jwks" not in _jwks_cache:
        async with httpx.AsyncClient() as client:
            resp = await client.get(settings.CLERK_JWKS_URL)
            resp.raise_for_status()
            _jwks_cache["jwks"] = resp.json()
    return _jwks_cache["jwks"]


async def verify_clerk_token(authorization: str) -> str:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid authorization header")
    token = authorization.split(" ", 1)[1]
    try:
        jwks = await _get_jwks()
        header = jwt.get_unverified_header(token)
        key_data = next(
            (k for k in jwks["keys"] if k["kid"] == header.get("kid")), None
        )
        if not key_data:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown signing key")
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(key_data)
        payload = jwt.decode(
            token, public_key, algorithms=["RS256"], options={"verify_aud": False}
        )
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


# ----------------------------------------------------------------------------
#  Current user
# ----------------------------------------------------------------------------
async def _get_or_create_dev_user(db: AsyncSession) -> User:
    result = await db.execute(select(User).where(User.email == settings.DEV_USER_EMAIL))
    user = result.scalar_one_or_none()
    if user:
        return user
    user = User(
        clerk_id="dev_local_user",
        email=settings.DEV_USER_EMAIL,
        full_name=settings.DEV_USER_NAME,
        plan="creator",  # generous plan for local dev
    )
    db.add(user)
    await db.flush()
    db.add(UserStats(user_id=user.id))
    await db.flush()
    return user


async def get_current_user(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(default=""),
) -> User:
    if settings.DEV_MODE:
        return await _get_or_create_dev_user(db)

    clerk_id = await verify_clerk_token(authorization)
    result = await db.execute(
        select(User).where(User.clerk_id == clerk_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "User not found. Please re-authenticate."
        )
    return user


async def get_current_user_optional(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(default=""),
) -> User | None:
    if settings.DEV_MODE:
        return await _get_or_create_dev_user(db)
    if not authorization.startswith("Bearer "):
        return None
    try:
        clerk_id = await verify_clerk_token(authorization)
        result = await db.execute(select(User).where(User.clerk_id == clerk_id))
        return result.scalar_one_or_none()
    except Exception:
        return None


# ----------------------------------------------------------------------------
#  Plan gating
# ----------------------------------------------------------------------------
PLAN_RANK = {"free": 0, "pro": 1, "creator": 2, "institution": 3}


def require_plan(required: str):
    async def check(user: User = Depends(get_current_user)) -> User:
        if PLAN_RANK.get(user.plan, 0) < PLAN_RANK.get(required, 0):
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "upgrade_required",
                    "required_plan": required,
                    "upgrade_url": "/pricing",
                },
            )
        return user

    return check


# ----------------------------------------------------------------------------
#  API-key auth (for /v1/* public API)
# ----------------------------------------------------------------------------
async def check_api_key(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(...),
) -> User:
    if not authorization.startswith("Bearer tc_live_"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid API key format")
    raw_key = authorization.split(" ", 1)[1]
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    result = await db.execute(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    api_key = result.scalar_one_or_none()
    if not api_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or revoked API key")
    await db.execute(
        update(ApiKey)
        .where(ApiKey.id == api_key.id)
        .values(last_used_at=datetime.utcnow(), requests_today=ApiKey.requests_today + 1)
    )
    user_result = await db.execute(select(User).where(User.id == api_key.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


# ------------------------------------------------------------------------------
#  Admin gating
# ------------------------------------------------------------------------------
async def get_admin_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Require the caller to be an admin user."""
    if not current_user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return current_user
