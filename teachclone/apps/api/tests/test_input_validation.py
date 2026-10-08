"""Tests for strict input validation across all Pydantic schemas.

Verifies that invalid inputs are REJECTED with 422/400 — never silently fixed.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.schemas.teacher_profile import (
    TeacherProfileCreate,
    TeacherProfileUpdate,
    ShareCreateRequest,
)
from app.schemas.media import (
    YouTubeIngestRequest,
    UploadInitiateRequest,
    MultipartPartRequest,
    UploadCompleteRequest,
)
from app.schemas.chat import ChatMessageRequest
from app.schemas.session import (
    SessionCreate,
    StudentProfileInput,
    AdjustLevelRequest,
)
from app.schemas.user import UserUpdate


# -----------------------------------------------------------------------
#  Helper: make a minimal FastAPI app that echoes validated schema back
# -----------------------------------------------------------------------
def _schema_app():
    app = FastAPI()

    @app.post("/profiles")
    async def create_profile(payload: TeacherProfileCreate):
        return {"ok": True, "name": payload.name}

    @app.put("/profiles/{pid}")
    async def update_profile(pid: str, payload: TeacherProfileUpdate):
        return {"ok": True}

    @app.post("/youtube")
    async def youtube(payload: YouTubeIngestRequest):
        return {"ok": True}

    @app.post("/upload/initiate")
    async def upload_init(payload: UploadInitiateRequest):
        return {"ok": True}

    @app.post("/upload/parts")
    async def upload_parts(payload: MultipartPartRequest):
        return {"ok": True}

    @app.post("/upload/complete")
    async def upload_complete(payload: UploadCompleteRequest):
        return {"ok": True}

    @app.post("/chat/message")
    async def chat(payload: ChatMessageRequest):
        return {"ok": True}

    @app.post("/sessions")
    async def create_session(payload: SessionCreate):
        return {"ok": True}

    @app.post("/sessions/{sid}/adjust-level")
    async def adjust_level(sid: str, payload: AdjustLevelRequest):
        return {"ok": True}

    @app.put("/user")
    async def update_user(payload: UserUpdate):
        return {"ok": True}

    @app.post("/share")
    async def create_share(payload: ShareCreateRequest):
        return {"ok": True}

    return app


@pytest.fixture(scope="module")
def client():
    return TestClient(_schema_app(), raise_server_exceptions=False)


# -----------------------------------------------------------------------
#  TeacherProfileCreate
# -----------------------------------------------------------------------
class TestTeacherProfileCreate:
    def test_empty_name_rejected(self, client):
        resp = client.post("/profiles", json={"name": "", "subject": "Math"})
        assert resp.status_code == 422

    def test_long_name_rejected(self, client):
        resp = client.post("/profiles", json={"name": "x" * 201, "subject": "Math"})
        assert resp.status_code == 422

    def test_long_description_rejected(self, client):
        resp = client.post("/profiles", json={"name": "Test", "description": "x" * 2001})
        assert resp.status_code == 422

    def test_script_tag_in_name_rejected(self, client):
        resp = client.post("/profiles", json={"name": "<script>alert(1)</script>", "subject": "Math"})
        assert resp.status_code == 422

    def test_script_tag_in_description_rejected(self, client):
        resp = client.post("/profiles", json={"name": "Test", "description": "javascript:void(0)"})
        assert resp.status_code == 422

    def test_invalid_visibility_rejected(self, client):
        resp = client.post("/profiles", json={"name": "Test", "visibility": "SUPER_PUBLIC"})
        assert resp.status_code == 422

    def test_valid_minimal(self, client):
        resp = client.post("/profiles", json={"name": "My Teacher"})
        assert resp.status_code == 200


# -----------------------------------------------------------------------
#  TeacherProfileUpdate
# -----------------------------------------------------------------------
class TestTeacherProfileUpdate:
    def test_empty_name_rejected(self, client):
        resp = client.put("/profiles/abc", json={"name": ""})
        assert resp.status_code == 422

    def test_script_tag_in_subject_rejected(self, client):
        resp = client.put("/profiles/abc", json={"subject": "<script>xss</script>"})
        assert resp.status_code == 422


# -----------------------------------------------------------------------
#  YouTubeIngestRequest
# -----------------------------------------------------------------------
class TestYouTubeIngestRequest:
    def test_invalid_youtube_url_rejected(self, client):
        resp = client.post("/youtube", json={"teacher_profile_id": "abc", "youtube_url": "http://google.com"})
        assert resp.status_code == 422

    def test_internal_url_rejected(self, client):
        resp = client.post("/youtube", json={
            "teacher_profile_id": "abc",
            "youtube_url": "http://192.168.1.1/admin"
        })
        assert resp.status_code == 422

    def test_valid_youtube_url(self, client):
        resp = client.post("/youtube", json={
            "teacher_profile_id": "abc",
            "youtube_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        })
        assert resp.status_code == 200

    def test_valid_youtu_be_url(self, client):
        resp = client.post("/youtube", json={
            "teacher_profile_id": "abc",
            "youtube_url": "https://youtu.be/dQw4w9WgXcQ"
        })
        assert resp.status_code == 200


# -----------------------------------------------------------------------
#  UploadInitiateRequest
# -----------------------------------------------------------------------
class TestUploadInitiateRequest:
    def test_zero_file_size_rejected(self, client):
        resp = client.post("/upload/initiate", json={
            "teacher_profile_id": "abc", "file_name": "test.pdf",
            "file_size": 0, "content_type": "application/pdf"
        })
        assert resp.status_code == 422

    def test_oversized_file_rejected(self, client):
        resp = client.post("/upload/initiate", json={
            "teacher_profile_id": "abc", "file_name": "test.pdf",
            "file_size": 3_000_000_000, "content_type": "application/pdf"
        })
        assert resp.status_code == 422

    def test_empty_filename_rejected(self, client):
        resp = client.post("/upload/initiate", json={
            "teacher_profile_id": "abc", "file_name": "",
            "file_size": 100, "content_type": "application/pdf"
        })
        assert resp.status_code == 422

    def test_long_content_type_rejected(self, client):
        resp = client.post("/upload/initiate", json={
            "teacher_profile_id": "abc", "file_name": "test.pdf",
            "file_size": 100, "content_type": "x" * 101
        })
        assert resp.status_code == 422


# -----------------------------------------------------------------------
#  ChatMessageRequest
# -----------------------------------------------------------------------
class TestChatMessageRequest:
    def test_empty_content_rejected(self, client):
        resp = client.post("/chat/message", json={"content": ""})
        assert resp.status_code == 422

    def test_too_long_content_rejected(self, client):
        resp = client.post("/chat/message", json={"content": "x" * 10001})
        assert resp.status_code == 422

    def test_script_tag_rejected(self, client):
        resp = client.post("/chat/message", json={"content": "<script>alert(1)</script>"})
        assert resp.status_code == 422

    def test_valid_content(self, client):
        resp = client.post("/chat/message", json={"content": "Hello teacher!"})
        assert resp.status_code == 200


# -----------------------------------------------------------------------
#  SessionCreate / StudentProfileInput
# -----------------------------------------------------------------------
class TestSessionCreate:
    def test_empty_profile_id_rejected(self, client):
        resp = client.post("/sessions", json={
            "teacher_profile_id": "",
            "student_profile": {"level": "undergrad", "subject": "Math"}
        })
        assert resp.status_code == 422

    def test_invalid_level_rejected(self, client):
        resp = client.post("/sessions", json={
            "teacher_profile_id": "abc",
            "student_profile": {"level": "elementary", "subject": "Math"}
        })
        assert resp.status_code == 422

    def test_invalid_stream_rejected(self, client):
        resp = client.post("/sessions", json={
            "teacher_profile_id": "abc",
            "student_profile": {"level": "undergrad", "stream": "philosophy", "subject": "Math"}
        })
        assert resp.status_code == 422

    def test_invalid_learning_style_rejected(self, client):
        resp = client.post("/sessions", json={
            "teacher_profile_id": "abc",
            "student_profile": {"level": "undergrad", "subject": "Math", "learning_style": "visual"}
        })
        assert resp.status_code == 422

    def test_script_in_goal_rejected(self, client):
        resp = client.post("/sessions", json={
            "teacher_profile_id": "abc",
            "student_profile": {"level": "undergrad", "subject": "Math", "goal": "<script>bad</script>"}
        })
        assert resp.status_code == 422


# -----------------------------------------------------------------------
#  AdjustLevelRequest
# -----------------------------------------------------------------------
class TestAdjustLevelRequest:
    def test_invalid_direction_rejected(self, client):
        resp = client.post("/sessions/abc/adjust-level", json={"direction": "up"})
        assert resp.status_code == 422

    def test_valid_direction(self, client):
        resp = client.post("/sessions/abc/adjust-level", json={"direction": "simpler"})
        assert resp.status_code == 200


# -----------------------------------------------------------------------
#  UserUpdate
# -----------------------------------------------------------------------
class TestUserUpdate:
    def test_long_name_rejected(self, client):
        resp = client.put("/user", json={"full_name": "x" * 201})
        assert resp.status_code == 422

    def test_empty_name_rejected(self, client):
        resp = client.put("/user", json={"full_name": ""})
        assert resp.status_code == 422

    def test_long_avatar_url_rejected(self, client):
        resp = client.put("/user", json={"avatar_url": "https://x.com/" + "a" * 500})
        assert resp.status_code == 422


# -----------------------------------------------------------------------
#  ShareCreateRequest
# -----------------------------------------------------------------------
class TestShareCreateRequest:
    def test_invalid_mode_rejected(self, client):
        resp = client.post("/share", json={"mode": "download"})
        assert resp.status_code == 422

    def test_valid_clone_mode(self, client):
        resp = client.post("/share", json={"mode": "clone"})
        assert resp.status_code == 200


# -----------------------------------------------------------------------
#  SQL injection strings should be rejected (if they hit script pattern)
# -----------------------------------------------------------------------
class TestSQLInjection:
    def test_sql_injection_in_profile_name(self, client):
        payload = {"name": "'; DROP TABLE users; --", "subject": "Math"}
        resp = client.post("/profiles", json=payload)
        # Should NOT return 500 — either 200 (harmless) or 422
        assert resp.status_code in (200, 422)

    def test_sql_injection_in_chat(self, client):
        resp = client.post("/chat/message", json={"content": "' OR 1=1 --"})
        # SQL in chat content is safe (parameterized queries), just ensure no 500
        assert resp.status_code in (200, 422)
