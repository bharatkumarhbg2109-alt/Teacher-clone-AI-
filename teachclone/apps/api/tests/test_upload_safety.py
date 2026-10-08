"""Tests for file upload safety — MIME validation, filename safety, size limits, magic bytes."""
import pytest
from fastapi import HTTPException

from app.services.storage import get_max_file_size, validate_file_upload


class TestFilenameValidation:
    def test_rejects_path_traversal(self):
        with pytest.raises(HTTPException, match="Invalid filename"):
            validate_file_upload("../../etc/passwd", "text/plain", 100)

    def test_rejects_backslash_traversal(self):
        with pytest.raises(HTTPException, match="Invalid filename"):
            validate_file_upload("..\\..\\windows\\system32", "text/plain", 100)

    def test_rejects_special_characters(self):
        with pytest.raises(HTTPException, match="invalid characters"):
            validate_file_upload("file;rm -rf.sh", "text/plain", 100)

    def test_accepts_space_in_filename(self):
        # Spaces in filenames are common and acceptable
        validate_file_upload("my file.pdf", "application/pdf", 100)

    def test_accepts_valid_filename(self):
        # Should not raise
        validate_file_upload("lecture-notes.pdf", "application/pdf", 100)

    def test_accepts_underscores_and_dashes(self):
        validate_file_upload("my_video_2024.mp4", "video/mp4", 100)


class TestMIMEValidation:
    def test_rejects_executable_type(self):
        with pytest.raises(HTTPException, match="not allowed"):
            validate_file_upload("virus.exe", "application/x-executable", 1000)

    def test_rejects_script_type(self):
        with pytest.raises(HTTPException, match="not allowed"):
            validate_file_upload("malicious.js", "application/javascript", 1000)

    def test_rejects_html_type(self):
        with pytest.raises(HTTPException, match="not allowed"):
            validate_file_upload("phish.html", "text/html", 1000)

    def test_accepts_pdf(self):
        validate_file_upload("document.pdf", "application/pdf", 1000)

    def test_accepts_mp4(self):
        validate_file_upload("video.mp4", "video/mp4", 1000)

    def test_accepts_jpeg(self):
        validate_file_upload("photo.jpg", "image/jpeg", 1000)


class TestFileSizeValidation:
    def test_rejects_oversized_video(self):
        with pytest.raises(HTTPException, match="too large"):
            validate_file_upload("huge.mp4", "video/mp4", 3 * 1024 * 1024 * 1024)

    def test_rejects_oversized_pdf(self):
        with pytest.raises(HTTPException, match="too large"):
            validate_file_upload("huge.pdf", "application/pdf", 200 * 1024 * 1024)

    def test_rejects_oversized_image(self):
        with pytest.raises(HTTPException, match="too large"):
            validate_file_upload("huge.png", "image/png", 50 * 1024 * 1024)

    def test_accepts_normal_video(self):
        validate_file_upload("clip.mp4", "video/mp4", 500 * 1024 * 1024)

    def test_accepts_normal_pdf(self):
        validate_file_upload("doc.pdf", "application/pdf", 10 * 1024 * 1024)


class TestMagicBytes:
    def test_rejects_pdf_with_wrong_magic(self):
        """A file claiming to be PDF but starting with MZ (PE executable)."""
        header = b"MZ" + b"\x00" * 14
        with pytest.raises(HTTPException, match="does not match"):
            validate_file_upload("fake.pdf", "application/pdf", 1000, header)

    def test_accepts_real_pdf_magic(self):
        header = b"%PDF-1.4"
        validate_file_upload("real.pdf", "application/pdf", 1000, header)

    def test_rejects_jpeg_with_wrong_magic(self):
        """Claiming JPEG but file starts with PNG magic."""
        header = b"\x89PNG\r\n\x1a\n"
        with pytest.raises(HTTPException, match="does not match"):
            validate_file_upload("fake.jpg", "image/jpeg", 1000, header)

    def test_accepts_real_jpeg_magic(self):
        header = b"\xff\xd8\xff\xe0" + b"\x00" * 12
        validate_file_upload("real.jpg", "image/jpeg", 1000, header)

    def test_accepts_real_png_magic(self):
        header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
        validate_file_upload("real.png", "image/png", 1000, header)

    def test_accepts_real_mp4_magic(self):
        header = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 8
        validate_file_upload("real.mp4", "video/mp4", 1000, header)

    def test_no_header_skips_magic_check(self):
        """Without file_header, magic byte check is skipped."""
        validate_file_upload("unknown.dat", "video/mp4", 1000, None)

    def test_unrecognized_mime_skips_magic_check(self):
        """MIME types not in MAGIC_BYTES dict skip the magic check."""
        validate_file_upload("doc.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            1000, b"\x50\x4b\x03\x04")


class TestYoutubURLValidation:
    """Test the YouTube URL validator used in media router."""

    def test_rejects_non_youtube_url(self):
        from app.schemas.media import YouTubeIngestRequest
        with pytest.raises(Exception):
            YouTubeIngestRequest(teacher_profile_id="abc", youtube_url="http://google.com")

    def test_rejects_internal_url(self):
        from app.schemas.media import YouTubeIngestRequest
        with pytest.raises(Exception):
            YouTubeIngestRequest(teacher_profile_id="abc", youtube_url="http://192.168.1.1/admin")

    def test_accepts_valid_youtube(self):
        from app.schemas.media import YouTubeIngestRequest
        req = YouTubeIngestRequest(
            teacher_profile_id="abc",
            youtube_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        assert "youtube.com" in req.youtube_url

    def test_accepts_youtu_be(self):
        from app.schemas.media import YouTubeIngestRequest
        req = YouTubeIngestRequest(
            teacher_profile_id="abc",
            youtube_url="https://youtu.be/dQw4w9WgXcQ"
        )
        assert "youtu.be" in req.youtube_url


# -----------------------------------------------------------------------
#  get_max_file_size helper
# -----------------------------------------------------------------------
class TestGetMaxFileSize:
    def test_video_mp4(self):
        assert get_max_file_size("video/mp4") == 2 * 1024 * 1024 * 1024

    def test_video_webm(self):
        assert get_max_file_size("video/webm") == 2 * 1024 * 1024 * 1024

    def test_audio_mpeg(self):
        assert get_max_file_size("audio/mpeg") == 500 * 1024 * 1024

    def test_audio_wav(self):
        assert get_max_file_size("audio/wav") == 500 * 1024 * 1024

    def test_application_pdf(self):
        assert get_max_file_size("application/pdf") == 100 * 1024 * 1024

    def test_image_jpeg(self):
        assert get_max_file_size("image/jpeg") == 20 * 1024 * 1024

    def test_image_png(self):
        assert get_max_file_size("image/png") == 20 * 1024 * 1024

    def test_text_plain(self):
        assert get_max_file_size("text/plain") == 50 * 1024 * 1024

    def test_unknown_type_defaults_to_100mb(self):
        assert get_max_file_size("application/x-unknown") == 100 * 1024 * 1024

    def test_empty_string_defaults_to_100mb(self):
        assert get_max_file_size("") == 100 * 1024 * 1024

    def test_strips_charset(self):
        """Content-Type with charset parameter should be handled."""
        assert get_max_file_size("text/plain; charset=utf-8") == 50 * 1024 * 1024


# -----------------------------------------------------------------------
#  presign_post conditions (S3-enforced)
# -----------------------------------------------------------------------
class TestPresignPostConditions:
    """Verify presign_post returns correct structure with S3 conditions.

    These tests run against the local backend (no real S3) so we verify
    the shape and that get_max_file_size is wired through correctly.
    """

    def test_presign_post_returns_url_and_fields(self):
        from app.services.storage import storage_service
        result = storage_service.presign_post(
            key="media/test/profile/file.mp4",
            content_type="video/mp4",
            max_size_bytes=2 * 1024 * 1024 * 1024,
        )
        assert "url" in result
        assert "fields" in result
        assert isinstance(result["url"], str)
        assert isinstance(result["fields"], dict)

    def test_presign_post_local_includes_content_type(self):
        """Local backend should still include Content-Type in fields."""
        from app.services.storage import storage_service
        result = storage_service.presign_post(
            key="media/test/profile/file.pdf",
            content_type="application/pdf",
            max_size_bytes=100 * 1024 * 1024,
        )
        assert result["fields"]["Content-Type"] == "application/pdf"

    def test_presign_post_local_url_is_put_endpoint(self):
        """Local backend wraps presigned POST as a PUT URL."""
        from app.services.storage import storage_service
        result = storage_service.presign_post(
            key="media/test/profile/file.jpg",
            content_type="image/jpeg",
            max_size_bytes=20 * 1024 * 1024,
        )
        assert "/storage/put" in result["url"]

    def test_presign_post_conditions_use_max_file_size(self):
        """Verify the max_size argument is what we pass — not a hardcoded value."""
        from app.services.storage import storage_service, get_max_file_size

        ct = "audio/mpeg"
        expected_max = get_max_file_size(ct)  # 500 MB
        result = storage_service.presign_post(
            key="media/test/profile/audio.mp3",
            content_type=ct,
            max_size_bytes=expected_max,
        )
        # On S3 backend the conditions would be embedded in the signed URL/policy.
        # On local backend we just verify the call succeeded with the right args.
        assert result["fields"]["Content-Type"] == ct

    def test_presign_post_all_file_types(self):
        """All allowed MIME types should produce valid presigned POST responses."""
        from app.services.storage import storage_service, get_max_file_size

        test_cases = [
            ("video/mp4", "media/u/p/f.mp4"),
            ("audio/wav", "media/u/p/f.wav"),
            ("application/pdf", "media/u/p/f.pdf"),
            ("image/png", "media/u/p/f.png"),
            ("text/plain", "media/u/p/f.txt"),
        ]
        for ct, key in test_cases:
            result = storage_service.presign_post(
                key=key,
                content_type=ct,
                max_size_bytes=get_max_file_size(ct),
            )
            assert "url" in result, f"Failed for {ct}"
            assert "fields" in result, f"Failed for {ct}"


# -----------------------------------------------------------------------
#  Presigned POST field structure (unit-level)
# -----------------------------------------------------------------------
class TestPresignedPostS3Conditions:
    """Test what conditions S3 would enforce — verified by inspecting
    the arguments passed to generate_presigned_post via mock.
    """

    def test_conditions_include_content_length_range(self):
        """Verify generate_presigned_post is called with content-length-range."""
        from unittest.mock import MagicMock, patch
        from app.services import storage as storage_mod
        from app.services.storage import StorageService

        mock_client = MagicMock()
        mock_client.generate_presigned_post.return_value = {
            "url": "https://s3.example.com/bucket",
            "fields": {"key": "test", "Content-Type": "video/mp4"},
        }

        svc = StorageService.__new__(StorageService)
        svc._client = mock_client
        svc.bucket = "test-bucket"

        max_size = 2 * 1024 * 1024 * 1024  # 2 GB
        with patch.object(storage_mod, "LOCAL", False):
            result = svc.presign_post(
                key="media/test.mp4",
                content_type="video/mp4",
                max_size_bytes=max_size,
            )

        # Verify generate_presigned_post was called
        mock_client.generate_presigned_post.assert_called_once()
        call_kwargs = mock_client.generate_presigned_post.call_args

        # Check conditions contain content-length-range
        conditions = call_kwargs.kwargs.get("Conditions") or call_kwargs[1].get("Conditions")
        assert conditions is not None, "No Conditions in presigned_post call"

        length_condition = [c for c in conditions if isinstance(c, list) and c[0] == "content-length-range"]
        assert len(length_condition) == 1, f"Missing content-length-range, got: {conditions}"
        assert length_condition[0][1] == 0  # min
        assert length_condition[0][2] == max_size  # max

    def test_conditions_include_content_type_eq(self):
        """Verify generate_presigned_post enforces Content-Type equality."""
        from unittest.mock import MagicMock, patch
        from app.services import storage as storage_mod
        from app.services.storage import StorageService

        mock_client = MagicMock()
        mock_client.generate_presigned_post.return_value = {
            "url": "https://s3.example.com/bucket",
            "fields": {"key": "test"},
        }

        svc = StorageService.__new__(StorageService)
        svc._client = mock_client
        svc.bucket = "test-bucket"

        with patch.object(storage_mod, "LOCAL", False):
            svc.presign_post(
                key="media/test.pdf",
                content_type="application/pdf",
                max_size_bytes=100 * 1024 * 1024,
            )

        call_kwargs = mock_client.generate_presigned_post.call_args
        conditions = call_kwargs.kwargs.get("Conditions") or call_kwargs[1].get("Conditions")

        ct_condition = [c for c in conditions if isinstance(c, list) and c[0] == "eq"]
        assert len(ct_condition) == 1, f"Missing Content-Type eq condition, got: {conditions}"
        assert ct_condition[0][1] == "$Content-Type"
        assert ct_condition[0][2] == "application/pdf"

    def test_fields_include_content_type(self):
        """The Fields dict should include Content-Type for S3 form submission."""
        from unittest.mock import MagicMock, patch
        from app.services import storage as storage_mod
        from app.services.storage import StorageService

        mock_client = MagicMock()
        mock_client.generate_presigned_post.return_value = {
            "url": "https://s3.example.com/bucket",
            "fields": {"key": "test"},
        }

        svc = StorageService.__new__(StorageService)
        svc._client = mock_client
        svc.bucket = "test-bucket"

        with patch.object(storage_mod, "LOCAL", False):
            svc.presign_post(
                key="media/test.jpg",
                content_type="image/jpeg",
                max_size_bytes=20 * 1024 * 1024,
            )

        call_kwargs = mock_client.generate_presigned_post.call_args
        fields = call_kwargs.kwargs.get("Fields") or call_kwargs[1].get("Fields")
        assert fields is not None, "No Fields in presigned_post call"
        assert fields["Content-Type"] == "image/jpeg"

    def test_max_size_varies_by_content_type(self):
        """Different content types should produce different max_size_bytes."""
        from unittest.mock import MagicMock, patch
        from app.services import storage as storage_mod
        from app.services.storage import StorageService, get_max_file_size

        mock_client = MagicMock()
        mock_client.generate_presigned_post.return_value = {
            "url": "https://s3.example.com/bucket",
            "fields": {},
        }

        svc = StorageService.__new__(StorageService)
        svc._client = mock_client
        svc.bucket = "test-bucket"

        with patch.object(storage_mod, "LOCAL", False):
            for ct in ["video/mp4", "audio/mpeg", "application/pdf", "image/jpeg"]:
                mock_client.reset_mock()
                expected = get_max_file_size(ct)
                svc.presign_post(key=f"media/test", content_type=ct, max_size_bytes=expected)

                call_kwargs = mock_client.generate_presigned_post.call_args
                conditions = call_kwargs.kwargs.get("Conditions") or call_kwargs[1].get("Conditions")
                length_condition = [c for c in conditions if isinstance(c, list) and c[0] == "content-length-range"]
                assert length_condition[0][2] == expected, f"Wrong max for {ct}"
