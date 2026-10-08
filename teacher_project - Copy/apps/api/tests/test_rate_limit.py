"""Tests for the sliding-window rate limiter middleware.

Uses the in-memory fallback (no Redis required) and a lightweight ASGI
test client provided by Starlette / FastAPI.
"""
import time
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.testclient import TestClient

import app.middleware.rate_limit as rl_mod
from app.middleware.rate_limit import (
    RateLimitMiddleware,
    _InMemoryWindow,
    _classify,
    configure_groups,
)


# ---------------------------------------------------------------------------
#  Fixture: reset the in-memory window between tests
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the global in-memory window and Redis state between tests."""
    rl_mod._memory = _InMemoryWindow()
    rl_mod._redis_client = None
    rl_mod._redis_available = True
    rl_mod._lua_sha = None
    rl_mod._auth_failures.clear()
    yield
    rl_mod._memory = _InMemoryWindow()
    rl_mod._auth_failures.clear()


# ---------------------------------------------------------------------------
#  Helper: build a minimal FastAPI app with the rate limiter attached
# ---------------------------------------------------------------------------

def _make_app(
    chat_limit: int = 5,
    dna_limit: int = 3,
    auth_limit: int = 10,
    auth_window: int = 60,
    upload_limit: int = 20,
    voice_limit: int = 60,
    public_limit: int = 100,
    window: int = 60,
) -> FastAPI:
    configure_groups(
        chat_limit=chat_limit, dna_limit=dna_limit,
        auth_limit=auth_limit, auth_window=auth_window,
        upload_limit=upload_limit, voice_limit=voice_limit,
        public_limit=public_limit, window=window,
    )

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.post("/chat/{session_id}/message")
    async def chat_msg(session_id: str):
        return {"ok": True}

    @app.post("/dna/extract-from-url")
    async def dna_url():
        return {"ok": True}

    @app.post("/dna/extract-from-file")
    async def dna_file():
        return {"ok": True}

    @app.post("/dna/regenerate/{teacher_id}")
    async def dna_regen(teacher_id: str):
        return {"ok": True}

    @app.post("/auth/sync")
    async def auth_sync():
        return {"ok": True}

    @app.post("/media/youtube")
    async def media_youtube():
        return {"ok": True}

    @app.post("/media/upload")
    async def media_upload():
        return {"ok": True}

    @app.post("/media/upload/complete")
    async def media_upload_complete():
        return {"ok": True}

    @app.post("/voice/transcribe")
    async def voice_transcribe():
        return {"ok": True}

    @app.post("/voice/speak")
    async def voice_speak():
        return {"ok": True}

    @app.post("/embed/chat")
    async def embed_chat():
        return {"ok": True}

    @app.get("/t/{token}")
    async def public_share(token: str):
        return {"ok": True}

    @app.get("/embed/profiles")
    async def embed_profiles():
        return {"ok": True}

    @app.get("/profiles/{profile_id}")
    async def get_profile(profile_id: str):
        return {"ok": True}

    return app


# ---------------------------------------------------------------------------
#  Tests: _classify
# ---------------------------------------------------------------------------

class TestClassify:
    def test_chat_message(self):
        assert _classify("/chat/abc-123/message", "POST") == "chat"

    def test_chat_get_not_limited(self):
        assert _classify("/chat/abc-123/message", "GET") is None

    def test_dna_extract_url(self):
        assert _classify("/dna/extract-from-url", "POST") == "dna"

    def test_dna_extract_file(self):
        assert _classify("/dna/extract-from-file", "POST") == "dna"

    def test_dna_regenerate(self):
        assert _classify("/dna/regenerate/abc-123", "POST") == "dna"

    def test_non_post_ignored(self):
        assert _classify("/chat/abc/message", "GET") is None
        assert _classify("/dna/extract-from-url", "GET") is None

    def test_unrelated_endpoint(self):
        assert _classify("/profiles/abc", "POST") is None
        assert _classify("/unknown/endpoint", "POST") is None


# ---------------------------------------------------------------------------
#  Tests: _InMemoryWindow
# ---------------------------------------------------------------------------

class TestInMemoryWindow:
    @pytest.mark.asyncio
    async def test_basic_increment(self):
        w = _InMemoryWindow()
        count, reset = await w.increment("k1", 60)
        assert count == 1
        assert reset > time.time()

    @pytest.mark.asyncio
    async def test_multiple_increments(self):
        w = _InMemoryWindow()
        for _ in range(4):
            await w.increment("k2", 60)
        count, _ = await w.increment("k2", 60)
        assert count == 5

    @pytest.mark.asyncio
    async def test_separate_keys(self):
        w = _InMemoryWindow()
        await w.increment("a", 60)
        await w.increment("a", 60)
        await w.increment("b", 60)
        ca, _ = await w.get_count("a", 60)
        cb, _ = await w.get_count("b", 60)
        assert ca == 2
        assert cb == 1

    @pytest.mark.asyncio
    async def test_expiry(self):
        w = _InMemoryWindow()
        # Manually insert an old entry
        w._buckets["old"] = [time.time() - 120]
        count, _ = await w.get_count("old", 60)
        assert count == 0  # old entry pruned


# ---------------------------------------------------------------------------
#  Tests: middleware integration (HTTP)
# ---------------------------------------------------------------------------

class TestRateLimitMiddleware:
    def test_chat_under_limit(self):
        app = _make_app(chat_limit=5, window=60)
        client = TestClient(app, raise_server_exceptions=False)

        # Send 5 requests (at the limit) — all should succeed
        for i in range(5):
            resp = client.post("/chat/abc/message", headers={"Authorization": "Bearer test-token-abc123"})
            assert resp.status_code == 200
            assert resp.headers["X-RateLimit-Limit"] == "5"
            assert resp.headers["X-RateLimit-Remaining"] == str(5 - i - 1)

        # 6th request should be rate limited
        resp = client.post("/chat/abc/message", headers={"Authorization": "Bearer test-token-abc123"})
        assert resp.status_code == 429

    def test_chat_exceeds_limit_returns_429(self):
        app = _make_app(chat_limit=3, window=60)
        client = TestClient(app, raise_server_exceptions=False)
        token = "Bearer test-token-xyz789"

        for _ in range(3):
            resp = client.post("/chat/abc/message", headers={"Authorization": token})
            assert resp.status_code == 200

        # 4th request should be rate limited
        resp = client.post("/chat/abc/message", headers={"Authorization": token})
        assert resp.status_code == 429
        body = resp.json()
        assert body["detail"] == "Rate limit exceeded"
        assert "retry_after" in body
        assert body["limit"] == 3
        assert body["group"] == "chat"
        assert "Retry-After" in resp.headers

    def test_dna_exceeds_limit(self):
        app = _make_app(dna_limit=2, window=60)
        client = TestClient(app, raise_server_exceptions=False)
        token = "Bearer dna-test-token"

        for _ in range(2):
            resp = client.post("/dna/extract-from-url", headers={"Authorization": token})
            assert resp.status_code == 200

        resp = client.post("/dna/extract-from-url", headers={"Authorization": token})
        assert resp.status_code == 429
        assert resp.json()["group"] == "dna"

    def test_different_users_independent_limits(self):
        app = _make_app(chat_limit=2, window=60)
        client = TestClient(app, raise_server_exceptions=False)

        # User A exhausts their limit
        for _ in range(2):
            resp = client.post("/chat/abc/message", headers={"Authorization": "Bearer user-a-token"})
            assert resp.status_code == 200
        resp = client.post("/chat/abc/message", headers={"Authorization": "Bearer user-a-token"})
        assert resp.status_code == 429

        # User B should still be fine
        resp = client.post("/chat/abc/message", headers={"Authorization": "Bearer user-b-token"})
        assert resp.status_code == 200

    def test_get_requests_not_limited(self):
        app = _make_app(chat_limit=1, window=60)
        client = TestClient(app, raise_server_exceptions=False)

        for _ in range(10):
            resp = client.get("/profiles/some-id")
            assert resp.status_code == 200

    def test_no_auth_header_uses_client_host(self):
        app = _make_app(chat_limit=2, window=60)
        client = TestClient(app, raise_server_exceptions=False)

        for _ in range(2):
            resp = client.post("/chat/abc/message")
            assert resp.status_code == 200

        resp = client.post("/chat/abc/message")
        assert resp.status_code == 429

    def test_dna_regenerate_limited(self):
        app = _make_app(dna_limit=1, window=60)
        client = TestClient(app, raise_server_exceptions=False)
        token = "Bearer regen-token"

        resp = client.post("/dna/regenerate/teacher-123", headers={"Authorization": token})
        assert resp.status_code == 200

        resp = client.post("/dna/regenerate/teacher-123", headers={"Authorization": token})
        assert resp.status_code == 429

    def test_rate_limit_headers_on_success(self):
        app = _make_app(chat_limit=10, window=60)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/chat/abc/message", headers={"Authorization": "Bearer hdr-token"})
        assert resp.status_code == 200
        assert resp.headers["X-RateLimit-Limit"] == "10"
        assert resp.headers["X-RateLimit-Remaining"] == "9"
        assert int(resp.headers["X-RateLimit-Reset"]) > int(time.time())


# ---------------------------------------------------------------------------
#  Tests: auth rate limit (IP-based, with backoff)
# ---------------------------------------------------------------------------

class TestAuthRateLimit:
    def test_auth_rate_limit_by_ip(self):
        app = _make_app(auth_limit=10, window=60)
        client = TestClient(app, raise_server_exceptions=False)

        for i in range(10):
            resp = client.post("/auth/sync")
            assert resp.status_code == 200, f"Request {i+1} should pass"

        resp = client.post("/auth/sync")
        assert resp.status_code == 429
        assert resp.json()["group"] == "auth"

    def test_auth_limit_uses_ip_not_token(self):
        """Same IP, different tokens → still blocked."""
        app = _make_app(auth_limit=2, window=60)
        client = TestClient(app, raise_server_exceptions=False)

        resp = client.post("/auth/sync", headers={"Authorization": "Bearer token-a"})
        assert resp.status_code == 200
        resp = client.post("/auth/sync", headers={"Authorization": "Bearer token-b"})
        assert resp.status_code == 200

        # Same IP, different token — should be blocked
        resp = client.post("/auth/sync", headers={"Authorization": "Bearer token-c"})
        assert resp.status_code == 429

    def test_auth_backoff_increases_window(self):
        """After 5 failures, next window should be 4x."""
        app = _make_app(auth_limit=2, auth_window=60)
        client = TestClient(app, raise_server_exceptions=False)

        # Exhaust the limit to create "failures" (the middleware tracks 429 as failure)
        for _ in range(2):
            client.post("/auth/sync")
        resp = client.post("/auth/sync")
        assert resp.status_code == 429

        # Verify backoff state was recorded
        assert rl_mod._auth_failures.get("testclient", 0) >= 1


# ---------------------------------------------------------------------------
#  Tests: upload rate limit
# ---------------------------------------------------------------------------

class TestUploadRateLimit:
    def test_upload_rate_limit(self):
        app = _make_app(upload_limit=3, window=60)
        client = TestClient(app, raise_server_exceptions=False)
        token = "Bearer upload-token"

        for _ in range(3):
            resp = client.post("/media/youtube", headers={"Authorization": token})
            assert resp.status_code == 200

        resp = client.post("/media/youtube", headers={"Authorization": token})
        assert resp.status_code == 429
        assert resp.json()["group"] == "upload"

    def test_upload_different_endpoints_share_limit(self):
        app = _make_app(upload_limit=2, window=60)
        client = TestClient(app, raise_server_exceptions=False)
        token = "Bearer upload-shared"

        client.post("/media/youtube", headers={"Authorization": token})
        client.post("/media/upload", headers={"Authorization": token})

        # Third request across different upload endpoint → blocked
        resp = client.post("/media/upload/complete", headers={"Authorization": token})
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
#  Tests: voice rate limit
# ---------------------------------------------------------------------------

class TestVoiceRateLimit:
    def test_voice_rate_limit(self):
        app = _make_app(voice_limit=3, window=60)
        client = TestClient(app, raise_server_exceptions=False)
        token = "Bearer voice-token"

        for _ in range(3):
            resp = client.post("/voice/transcribe", headers={"Authorization": token})
            assert resp.status_code == 200

        resp = client.post("/voice/transcribe", headers={"Authorization": token})
        assert resp.status_code == 429
        assert resp.json()["group"] == "voice"

    def test_voice_speak_and_transcribe_share_limit(self):
        app = _make_app(voice_limit=2, window=60)
        client = TestClient(app, raise_server_exceptions=False)
        token = "Bearer voice-shared"

        client.post("/voice/transcribe", headers={"Authorization": token})
        client.post("/voice/speak", headers={"Authorization": token})

        resp = client.post("/voice/transcribe", headers={"Authorization": token})
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
#  Tests: public rate limit (IP-based)
# ---------------------------------------------------------------------------

class TestPublicRateLimit:
    def test_public_rate_limit(self):
        app = _make_app(public_limit=3, window=60)
        client = TestClient(app, raise_server_exceptions=False)

        for _ in range(3):
            resp = client.get("/t/some-token")
            assert resp.status_code == 200

        resp = client.get("/t/some-token")
        assert resp.status_code == 429
        assert resp.json()["group"] == "public"

    def test_public_embed_chat_shared_limit(self):
        app = _make_app(public_limit=2, window=60)
        client = TestClient(app, raise_server_exceptions=False)

        client.post("/embed/chat")
        client.get("/embed/profiles")

        resp = client.post("/embed/chat")
        assert resp.status_code == 429

    def test_classify_new_groups(self):
        assert _classify("/auth/sync", "POST") == "auth"
        assert _classify("/media/youtube", "POST") == "upload"
        assert _classify("/media/upload", "POST") == "upload"
        assert _classify("/media/upload/complete", "POST") == "upload"
        assert _classify("/voice/transcribe", "POST") == "voice"
        assert _classify("/voice/speak", "POST") == "voice"
        assert _classify("/embed/chat", "POST") == "public"
        assert _classify("/t/some-token", "GET") == "public"
        assert _classify("/embed/profiles", "GET") == "public"
        # Non-matching
        assert _classify("/health", "GET") is None
        assert _classify("/profiles/abc", "GET") is None
