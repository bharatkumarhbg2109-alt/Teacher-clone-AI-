"""Integration tests for DNA extraction endpoint admin authorization.

These tests use a real (in-memory SQLite) database and the full FastAPI
stack to verify that:

1. Non-admin users receive 403 on extraction endpoints (extract-from-url,
   extract-from-file, regenerate).
2. Admin users can reach the extraction endpoints (background task starts).
3. Ownership checks work — a user who doesn't own the teacher profile gets 403.
4. Read-only DNA endpoints (report, system-prompt) work for any authenticated
   user who owns the profile.
"""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.teacher_profile import TeacherProfile
from app.models.user import User


# ── Helpers ───────────────────────────────────────────────────────────────

def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer test_token_{user.clerk_id}"}


# ══════════════════════════════════════════════════════════════════════════
#  POST /dna/extract-from-url
# ══════════════════════════════════════════════════════════════════════════

class TestExtractFromUrl:
    """Authorization tests for POST /dna/extract-from-url."""

    async def test_non_admin_gets_403(self, client: AsyncClient, regular_user: User, teacher_profile: TeacherProfile):
        """A non-admin user should be rejected with 403."""
        resp = await client.post(
            "/dna/extract-from-url",
            json={
                "teacher_id": str(teacher_profile.id),
                "youtube_urls": ["https://youtube.com/watch?v=abc123"],
            },
            headers=_auth(regular_user),
        )
        assert resp.status_code == 403
        assert "admin" in resp.json()["detail"].lower()

    async def test_admin_can_start_extraction(
        self, client: AsyncClient, admin_user: User, admin_teacher_profile: TeacherProfile
    ):
        """An admin user who owns the profile should get 200 (job starts)."""
        with patch("app.routers.dna_router._run_url_job", new_callable=AsyncMock):
            resp = await client.post(
                "/dna/extract-from-url",
                json={
                    "teacher_id": str(admin_teacher_profile.id),
                    "youtube_urls": ["https://youtube.com/watch?v=abc123"],
                },
                headers=_auth(admin_user),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "running"

    async def test_admin_cannot_extract_other_users_profile(
        self, client: AsyncClient, admin_user: User, teacher_profile: TeacherProfile
    ):
        """An admin who doesn't own the teacher profile gets 403 (ownership check)."""
        resp = await client.post(
            "/dna/extract-from-url",
            json={
                "teacher_id": str(teacher_profile.id),
                "youtube_urls": ["https://youtube.com/watch?v=abc123"],
            },
            headers=_auth(admin_user),
        )
        # 403 because _owned_teacher checks user_id != admin_user.id
        assert resp.status_code == 403

    async def test_nonexistent_profile_returns_404(self, client: AsyncClient, admin_user: User):
        """A valid admin requesting a non-existent profile gets 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.post(
            "/dna/extract-from-url",
            json={
                "teacher_id": fake_id,
                "youtube_urls": ["https://youtube.com/watch?v=abc123"],
            },
            headers=_auth(admin_user),
        )
        assert resp.status_code == 404

    async def test_empty_urls_returns_400(self, client: AsyncClient, admin_user: User, admin_teacher_profile: TeacherProfile):
        """An admin with empty URL list gets 400."""
        resp = await client.post(
            "/dna/extract-from-url",
            json={
                "teacher_id": str(admin_teacher_profile.id),
                "youtube_urls": [],
            },
            headers=_auth(admin_user),
        )
        assert resp.status_code == 400

    async def test_no_auth_returns_401(self, client: AsyncClient, admin_teacher_profile: TeacherProfile):
        """Request without Authorization header gets 401."""
        resp = await client.post(
            "/dna/extract-from-url",
            json={
                "teacher_id": str(admin_teacher_profile.id),
                "youtube_urls": ["https://youtube.com/watch?v=abc123"],
            },
        )
        assert resp.status_code in (401, 422)


# ══════════════════════════════════════════════════════════════════════════
#  POST /dna/extract-from-file
# ══════════════════════════════════════════════════════════════════════════

class TestExtractFromFile:
    """Authorization tests for POST /dna/extract-from-file."""

    async def test_non_admin_gets_403(self, client: AsyncClient, regular_user: User, teacher_profile: TeacherProfile):
        """A non-admin user should be rejected with 403."""
        resp = await client.post(
            "/dna/extract-from-file",
            data={"teacher_id": str(teacher_profile.id)},
            files={"file": ("test.mp3", b"fake-audio-data", "audio/mpeg")},
            headers=_auth(regular_user),
        )
        assert resp.status_code == 403
        assert "admin" in resp.json()["detail"].lower()

    async def test_admin_can_upload(
        self, client: AsyncClient, admin_user: User, admin_teacher_profile: TeacherProfile
    ):
        """An admin who owns the profile should get 200 (job starts)."""
        with patch("app.routers.dna_router._run_file_job", new_callable=AsyncMock):
            resp = await client.post(
                "/dna/extract-from-file",
                data={"teacher_id": str(admin_teacher_profile.id)},
                files={"file": ("lecture.mp3", b"fake-audio-data", "audio/mpeg")},
                headers=_auth(admin_user),
            )
        assert resp.status_code == 200
        body = resp.json()
        assert "job_id" in body
        assert body["status"] == "running"

    async def test_admin_cannot_extract_other_users_profile(
        self, client: AsyncClient, admin_user: User, teacher_profile: TeacherProfile
    ):
        """An admin who doesn't own the profile gets 403."""
        resp = await client.post(
            "/dna/extract-from-file",
            data={"teacher_id": str(teacher_profile.id)},
            files={"file": ("test.mp3", b"fake-audio-data", "audio/mpeg")},
            headers=_auth(admin_user),
        )
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════
#  POST /dna/regenerate/{teacher_id}
# ══════════════════════════════════════════════════════════════════════════

class TestRegenerate:
    """Authorization tests for POST /dna/regenerate/{teacher_id}."""

    async def test_non_admin_gets_403(self, client: AsyncClient, regular_user: User, teacher_profile: TeacherProfile):
        """A non-admin user should be rejected with 403."""
        resp = await client.post(
            f"/dna/regenerate/{teacher_profile.id}",
            headers=_auth(regular_user),
        )
        assert resp.status_code == 403
        assert "admin" in resp.json()["detail"].lower()

    async def test_admin_can_regenerate(
        self, client: AsyncClient, admin_user: User, admin_teacher_profile: TeacherProfile
    ):
        """An admin who owns the profile and has transcripts should get 200."""
        # The regenerate endpoint checks for stored transcripts; with none
        # it returns 400.  We test authorization (403 vs not-403) here.
        resp = await client.post(
            f"/dna/regenerate/{admin_teacher_profile.id}",
            headers=_auth(admin_user),
        )
        # 400 = no transcripts (expected), but NOT 403 (auth passed)
        assert resp.status_code != 403

    async def test_admin_cannot_regenerate_other_users_profile(
        self, client: AsyncClient, admin_user: User, teacher_profile: TeacherProfile
    ):
        """An admin who doesn't own the profile gets 403."""
        resp = await client.post(
            f"/dna/regenerate/{teacher_profile.id}",
            headers=_auth(admin_user),
        )
        assert resp.status_code == 403

    async def test_nonexistent_profile_returns_404(self, client: AsyncClient, admin_user: User):
        """A valid admin requesting a non-existent profile gets 404."""
        fake_id = str(uuid.uuid4())
        resp = await client.post(
            f"/dna/regenerate/{fake_id}",
            headers=_auth(admin_user),
        )
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
#  Read-only DNA endpoints (any authenticated user with ownership)
# ══════════════════════════════════════════════════════════════════════════

class TestReadOnlyDnaEndpoints:
    """Verify that read-only endpoints use get_current_user (not admin)."""

    async def test_report_owner_can_read(self, client: AsyncClient, regular_user: User, teacher_profile: TeacherProfile):
        """The profile owner (non-admin) can read the report endpoint."""
        resp = await client.get(
            f"/dna/report/{teacher_profile.id}",
            headers=_auth(regular_user),
        )
        # 404 = no report yet (expected), but NOT 403 (auth passed)
        assert resp.status_code != 403

    async def test_report_non_owner_gets_403(self, client: AsyncClient, other_user: User, teacher_profile: TeacherProfile):
        """A user who doesn't own the profile gets 403 on report."""
        resp = await client.get(
            f"/dna/report/{teacher_profile.id}",
            headers=_auth(other_user),
        )
        assert resp.status_code == 403

    async def test_system_prompt_owner_can_read(self, client: AsyncClient, regular_user: User, teacher_profile: TeacherProfile):
        """The profile owner (non-admin) can read the system prompt endpoint."""
        resp = await client.get(
            f"/dna/system-prompt/{teacher_profile.id}",
            headers=_auth(regular_user),
        )
        # 404 = no prompt yet (expected), but NOT 403 (auth passed)
        assert resp.status_code != 403

    async def test_system_prompt_non_owner_gets_403(self, client: AsyncClient, other_user: User, teacher_profile: TeacherProfile):
        """A user who doesn't own the profile gets 403 on system-prompt."""
        resp = await client.get(
            f"/dna/system-prompt/{teacher_profile.id}",
            headers=_auth(other_user),
        )
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════
#  Cross-cutting: unauthenticated access
# ══════════════════════════════════════════════════════════════════════════

class TestUnauthenticated:
    """All DNA extraction endpoints must require authentication."""

    @pytest.mark.parametrize("method,path", [
        ("POST", "/dna/extract-from-url"),
        ("POST", "/dna/extract-from-file"),
        ("POST", f"/dna/regenerate/{uuid.uuid4()}"),
        ("GET", f"/dna/report/{uuid.uuid4()}"),
        ("GET", f"/dna/system-prompt/{uuid.uuid4()}"),
    ])
    async def test_no_auth_rejected(self, client: AsyncClient, method: str, path: str):
        """Requests without auth should get 401 or 422."""
        if method == "POST" and "file" in path:
            resp = await client.request(method, path)
        elif method == "POST":
            resp = await client.request(method, path, json={})
        else:
            resp = await client.request(method, path)
        assert resp.status_code in (401, 403, 422)
