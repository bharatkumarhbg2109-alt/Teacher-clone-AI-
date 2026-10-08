"""Shared test fixtures — in-memory SQLite + full FastAPI app.

Key design: fixtures ``commit()`` + ``refresh()`` their data so the
dependency-overridden session (used by the ASGI test client) can see it.
The ``db`` fixture rolls back after each test for isolation.
"""
import uuid
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from fastapi import Depends, Header, HTTPException, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ── Patch settings BEFORE any app import ──────────────────────────────────
import app.config as _cfg

_cfg.settings = _cfg.Settings(
    DATABASE_URL="sqlite+aiosqlite:///:memory:",
    DEV_MODE=True,
    ENV="local",
    DEBUG=False,
    REDIS_URL="",
    ANTHROPIC_API_KEY="",
    OPENAI_API_KEY="",
    EMBEDDING_PROVIDER="openai",
    CLERK_SECRET_KEY="",
    CLERK_JWKS_URL="https://example.com/jwks",
    # Disable rate limiting for tests
    RATE_LIMIT_CHAT=100_000,
    RATE_LIMIT_DNA=100_000,
    RATE_LIMIT_AUTH=100_000,
    RATE_LIMIT_AUTH_WINDOW=3600,
    RATE_LIMIT_UPLOAD=100_000,
    RATE_LIMIT_VOICE=100_000,
    RATE_LIMIT_PUBLIC=100_000,
    RATE_LIMIT_WINDOW=3600,
)

# ── Import all models so Base.metadata knows every table ──────────────────
import app.db.base  # noqa: F401

from app.db.session import Base  # noqa: E402
from app.models.teacher_profile import TeacherProfile  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.user_stats import UserStats  # noqa: E402

# ── Engine + session factory (in-memory SQLite) ──────────────────────────
_test_engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
_TestSession = async_sessionmaker(
    _test_engine, class_=AsyncSession, expire_on_commit=False
)


# ---------------------------------------------------------------------------
#  Schema
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def _create_schema():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await _test_engine.dispose()


# ---------------------------------------------------------------------------
#  DB session (committed so other sessions see it, rolled back for cleanup)
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db(_create_schema) -> AsyncGenerator[AsyncSession, None]:
    async with _TestSession() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
#  Helper: commit a user, refresh to populate id, then add UserStats
# ---------------------------------------------------------------------------

async def _make_user(
    db: AsyncSession,
    *,
    clerk_id: str,
    email: str,
    full_name: str,
    is_admin: bool = False,
    plan: str = "free",
) -> User:
    """Create a User, commit it, refresh (so .id is populated), then
    add a UserStats row and commit again."""
    user = User(
        clerk_id=clerk_id,
        email=email,
        full_name=full_name,
        is_admin=is_admin,
        is_active=True,
        plan=plan,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)  # now user.id is guaranteed to be populated

    stats = UserStats(user_id=user.id)
    db.add(stats)
    await db.commit()
    await db.refresh(user)  # refresh relationship
    return user


# ---------------------------------------------------------------------------
#  User factories
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def regular_user(db: AsyncSession) -> User:
    return await _make_user(
        db,
        clerk_id=f"user_{uuid.uuid4().hex[:12]}",
        email=f"user_{uuid.uuid4().hex[:8]}@test.local",
        full_name="Test User",
        is_admin=False,
    )


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession) -> User:
    return await _make_user(
        db,
        clerk_id=f"admin_{uuid.uuid4().hex[:12]}",
        email=f"admin_{uuid.uuid4().hex[:8]}@test.local",
        full_name="Test Admin",
        is_admin=True,
        plan="creator",
    )


@pytest_asyncio.fixture
async def other_user(db: AsyncSession) -> User:
    return await _make_user(
        db,
        clerk_id=f"other_{uuid.uuid4().hex[:12]}",
        email=f"other_{uuid.uuid4().hex[:8]}@test.local",
        full_name="Other User",
        is_admin=False,
    )


@pytest_asyncio.fixture
async def teacher_profile(db: AsyncSession, regular_user: User) -> TeacherProfile:
    profile = TeacherProfile(
        user_id=regular_user.id,
        name="Test Teacher",
        subject="mathematics",
        description="A test teacher profile",
        visibility="private",
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@pytest_asyncio.fixture
async def admin_teacher_profile(
    db: AsyncSession, admin_user: User
) -> TeacherProfile:
    profile = TeacherProfile(
        user_id=admin_user.id,
        name="Admin Teacher",
        subject="physics",
        description="Admin-owned teacher profile",
        visibility="private",
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


# ---------------------------------------------------------------------------
#  Auth helper
# ---------------------------------------------------------------------------

def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer test_token_{user.clerk_id}"}


# ---------------------------------------------------------------------------
#  Async HTTP client with dependency overrides
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def client(
    _create_schema,
    db: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    from app.dependencies import get_admin_user, get_current_user, get_db
    from app.main import create_app

    app = create_app()

    async def _override_get_db():
        try:
            yield db
        except Exception:
            raise

    async def _override_get_current_user(
        authorization: str = Header(default=""),
    ) -> User:
        # Strip Bearer prefix, then check for test_token_
        token = authorization
        if token.startswith("Bearer "):
            token = token[len("Bearer "):]
        prefix = "test_token_"
        if not token.startswith(prefix):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid test token")
        clerk_id = token[len(prefix):]
        # Query the SAME session that fixtures committed to
        result = await db.execute(
            sa_select(User).where(
                User.clerk_id == clerk_id, User.is_active.is_(True)
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED, "User not found"
            )
        return user

    async def _override_get_admin_user(
        current_user: User = Depends(_override_get_current_user),
    ) -> User:
        if not current_user.is_admin:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Admin access required"
            )
        return current_user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_admin_user] = _override_get_admin_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
