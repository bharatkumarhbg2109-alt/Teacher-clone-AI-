"""Integration tests for GDPR export and deletion endpoints."""
from __future__ import annotations

import json
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.media_source import MediaSource
from app.models.message import Message
from app.models.quiz import Quiz
from app.models.student_session import StudentSession
from app.models.teacher_profile import TeacherProfile
from app.models.user import User
from app.models.user_badge import UserBadge


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer test_token_{user.clerk_id}"}


# ---------------------------------------------------------------------------
#  Helpers to seed test data
# ---------------------------------------------------------------------------

async def _seed_full_user_data(
    db: AsyncSession,
    user: User,
    profile: TeacherProfile,
) -> dict[str, str]:
    """Create a session, message, quiz, badge, and media for the given user.
    Returns a dict of created IDs for assertions."""
    session = StudentSession(
        student_id=user.id,
        teacher_profile_id=profile.id,
        student_profile={"level": "beginner", "stream": "science"},
        current_effective_level="beginner",
        concept_mastery=[{"concept": "algebra", "state": "learning"}],
        message_count=2,
    )
    db.add(session)
    await db.flush()

    message = Message(
        session_id=session.id,
        role="assistant",
        content="Hello, let's learn algebra!",
        tokens_used=50,
    )
    db.add(message)

    quiz = Quiz(
        session_id=session.id,
        teacher_profile_id=profile.id,
        kind="full",
        questions=[{"q": "What is 2+2?", "a": "4"}],
        score=0.8,
    )
    db.add(quiz)

    badge = UserBadge(user_id=user.id, badge_id="first_quiz")
    db.add(badge)

    media = MediaSource(
        teacher_profile_id=profile.id,
        uploaded_by=user.id,
        source_type="video_upload",
        file_name="lecture.mp4",
        file_size_bytes=1024000,
        status="completed",
    )
    db.add(media)

    await db.commit()

    return {
        "session_id": str(session.id),
        "message_id": str(message.id),
        "quiz_id": str(quiz.id),
        "badge_id": "first_quiz",
        "media_id": str(media.id),
    }


# ══════════════════════════════════════════════════════════════════════════
#  POST /gdpr/export
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_export_returns_all_user_data(
    client: AsyncClient,
    regular_user: User,
    teacher_profile: TeacherProfile,
    db: AsyncSession,
):
    """Export should return a JSON blob containing every key data category."""
    ids = await _seed_full_user_data(db, regular_user, teacher_profile)

    resp = await client.post("/gdpr/export", headers=_auth(regular_user))
    assert resp.status_code == 200
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert "my_data_export.json" in resp.headers.get("content-disposition", "")

    body = resp.json()
    for key in ("user", "profiles", "sessions", "messages",
                 "media", "quizzes", "stats", "badges"):
        assert key in body, f"Missing top-level key: {key}"

    # Spot-check that our seeded IDs appear
    profile_ids = {p["id"] for p in body["profiles"]}
    assert str(teacher_profile.id) in profile_ids

    session_ids = {s["id"] for s in body["sessions"]}
    assert ids["session_id"] in session_ids

    message_ids = {m["id"] for m in body["messages"]}
    assert ids["message_id"] in message_ids

    quiz_ids = {q["id"] for q in body["quizzes"]}
    assert ids["quiz_id"] in quiz_ids

    badge_ids = {b["badge_id"] for b in body["badges"]}
    assert ids["badge_id"] in badge_ids

    media_ids = {m["id"] for m in body["media"]}
    assert ids["media_id"] in media_ids


@pytest.mark.asyncio
async def test_export_requires_auth(client: AsyncClient):
    """Unauthenticated request should be rejected."""
    resp = await client.post("/gdpr/export")
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_export_only_returns_own_data(
    client: AsyncClient,
    regular_user: User,
    other_user: User,
    teacher_profile: TeacherProfile,
    db: AsyncSession,
):
    """User A's export must not contain User B's data."""
    other_profile = TeacherProfile(
        user_id=other_user.id,
        name="Other Teacher",
        subject="history",
        description="B's profile",
        visibility="private",
    )
    db.add(other_profile)
    await db.commit()
    await db.refresh(other_profile)

    resp = await client.post("/gdpr/export", headers=_auth(regular_user))
    assert resp.status_code == 200
    body = resp.json()

    all_profile_ids = {p["id"] for p in body["profiles"]}
    assert str(other_profile.id) not in all_profile_ids
    assert str(teacher_profile.id) in all_profile_ids


# ══════════════════════════════════════════════════════════════════════════
#  DELETE /gdpr/account
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
async def test_delete_account_removes_all_data(
    client: AsyncClient,
    regular_user: User,
    teacher_profile: TeacherProfile,
    db: AsyncSession,
):
    """Deleting should remove the user and all owned rows."""
    await _seed_full_user_data(db, regular_user, teacher_profile)

    user_id = regular_user.id
    profile_id = teacher_profile.id

    resp = await client.delete("/gdpr/account", headers=_auth(regular_user))
    assert resp.status_code == 200
    assert resp.json()["message"] == "Account deleted"

    # Verify user is gone
    result = await db.execute(select(User).where(User.id == user_id))
    assert result.scalar_one_or_none() is None

    # Verify profile is gone
    result = await db.execute(select(TeacherProfile).where(TeacherProfile.id == profile_id))
    assert result.scalar_one_or_none() is None

    # Verify sessions are gone
    result = await db.execute(select(StudentSession).where(StudentSession.student_id == user_id))
    assert result.scalars().all() == []

    # Verify messages are gone (join through sessions)
    result = await db.execute(select(Message).join(StudentSession).where(StudentSession.student_id == user_id))
    assert result.scalars().all() == []

    # Verify quizzes are gone
    result = await db.execute(select(Quiz).join(StudentSession).where(StudentSession.student_id == user_id))
    assert result.scalars().all() == []

    # Verify badges are gone
    result = await db.execute(select(UserBadge).where(UserBadge.user_id == user_id))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_delete_requires_auth(client: AsyncClient):
    """Unauthenticated request should be rejected."""
    resp = await client.delete("/gdpr/account")
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_delete_only_affects_own_data(
    client: AsyncClient,
    regular_user: User,
    other_user: User,
    teacher_profile: TeacherProfile,
    db: AsyncSession,
):
    """Deleting User A must leave User B's data intact."""
    other_profile = TeacherProfile(
        user_id=other_user.id,
        name="Other Teacher",
        subject="history",
        description="B's profile",
        visibility="private",
    )
    db.add(other_profile)
    await db.commit()
    await db.refresh(other_profile)

    await _seed_full_user_data(db, regular_user, teacher_profile)

    other_user_id = other_user.id
    other_profile_id = other_profile.id

    # Delete regular_user
    resp = await client.delete("/gdpr/account", headers=_auth(regular_user))
    assert resp.status_code == 200

    # regular_user is gone
    result = await db.execute(select(User).where(User.id == regular_user.id))
    assert result.scalar_one_or_none() is None

    # other_user still exists
    result = await db.execute(select(User).where(User.id == other_user_id))
    assert result.scalar_one_or_none() is not None

    # other_user's profile still exists
    result = await db.execute(select(TeacherProfile).where(TeacherProfile.id == other_profile_id))
    assert result.scalar_one_or_none() is not None
