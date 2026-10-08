"""Tests for the request logging middleware."""
import logging

import pytest

pytestmark = pytest.mark.asyncio


class TestRequestLoggingMiddleware:
    """Verify the RequestLoggingMiddleware logs correctly."""

    async def test_200_not_logged_as_error(self, client, caplog):
        """Successful requests should NOT appear in warning/error logs."""
        with caplog.at_level(logging.WARNING, logger="teachclone.request"):
            await client.get("/health")

        error_logs = [r for r in caplog.records if "teachclone.request" in r.name]
        assert len(error_logs) == 0

    async def test_404_logged_as_warning(self, client, caplog):
        """404 responses should be logged as CLIENT_ERR at WARNING level."""
        with caplog.at_level(logging.WARNING, logger="teachclone.request"):
            await client.get("/this-does-not-exist")

        request_logs = [r for r in caplog.records if "teachclone.request" in r.name]
        assert len(request_logs) >= 1
        record = request_logs[-1]
        assert record.levelno == logging.WARNING
        assert "CLIENT_ERR" in record.message
        assert "404" in record.message
        assert "/this-does-not-exist" in record.message

    async def test_422_logged_as_warning(self, client, regular_user, caplog):
        """422 validation errors should be logged as CLIENT_ERR."""
        headers = {"Authorization": f"Bearer test_token_{regular_user.clerk_id}"}
        with caplog.at_level(logging.WARNING, logger="teachclone.request"):
            await client.post("/profiles", json={"name": ""}, headers=headers)

        request_logs = [r for r in caplog.records if "teachclone.request" in r.name]
        assert len(request_logs) >= 1
        record = request_logs[-1]
        assert record.levelno == logging.WARNING
        assert "CLIENT_ERR" in record.message
        assert "422" in record.message

    async def test_401_logged_as_warning(self, client, caplog):
        """401 unauthorized should be logged as CLIENT_ERR."""
        with caplog.at_level(logging.WARNING, logger="teachclone.request"):
            await client.get("/users/me")

        request_logs = [r for r in caplog.records if "teachclone.request" in r.name]
        assert len(request_logs) >= 1
        record = request_logs[-1]
        assert record.levelno == logging.WARNING
        assert "CLIENT_ERR" in record.message
        assert "401" in record.message

    async def test_log_contains_timing(self, client, caplog):
        """Log message should contain response time in milliseconds."""
        with caplog.at_level(logging.WARNING, logger="teachclone.request"):
            await client.get("/nonexistent-route")

        request_logs = [r for r in caplog.records if "teachclone.request" in r.name]
        assert len(request_logs) >= 1
        record = request_logs[-1]
        assert "ms)" in record.message

    async def test_log_contains_request_id(self, client, caplog):
        """Log message should contain a unique request ID."""
        with caplog.at_level(logging.WARNING, logger="teachclone.request"):
            await client.get("/nonexistent-route")

        request_logs = [r for r in caplog.records if "teachclone.request" in r.name]
        assert len(request_logs) >= 1
        record = request_logs[-1]
        # Request ID is a 12-char hex string in brackets
        assert "[" in record.message and "]" in record.message

    async def test_log_contains_method_and_path(self, client, caplog):
        """Log should include HTTP method and path."""
        with caplog.at_level(logging.WARNING, logger="teachclone.request"):
            await client.post("/nonexistent-endpoint", json={})

        request_logs = [r for r in caplog.records if "teachclone.request" in r.name]
        assert len(request_logs) >= 1
        record = request_logs[-1]
        assert "POST" in record.message
        assert "/nonexistent-endpoint" in record.message

    async def test_log_contains_user_id_from_token(self, client, regular_user, caplog):
        """When authenticated, log should include the user token prefix."""
        headers = {"Authorization": f"Bearer test_token_{regular_user.clerk_id}"}
        with caplog.at_level(logging.WARNING, logger="teachclone.request"):
            await client.get("/nonexistent-path", headers=headers)

        request_logs = [r for r in caplog.records if "teachclone.request" in r.name]
        assert len(request_logs) >= 1
        record = request_logs[-1]
        # User ID should be the first 16 chars of the token + "..."
        token_prefix = f"test_token_{regular_user.clerk_id}"[:16]
        assert token_prefix in record.message

    async def test_log_contains_ip_address(self, client, caplog):
        """Log should include the client IP."""
        with caplog.at_level(logging.WARNING, logger="teachclone.request"):
            await client.get("/nonexistent-path")

        request_logs = [r for r in caplog.records if "teachclone.request" in r.name]
        assert len(request_logs) >= 1
        record = request_logs[-1]
        assert "ip=" in record.message

    async def test_health_checks_not_logged(self, client, caplog):
        """Health check endpoints should be skipped entirely."""
        with caplog.at_level(logging.DEBUG, logger="teachclone.request"):
            await client.get("/health")
            await client.get("/health/db")

        request_logs = [r for r in caplog.records if "teachclone.request" in r.name]
        assert len(request_logs) == 0

    async def test_openapi_not_logged(self, client, caplog):
        """OpenAPI/docs endpoints should be skipped."""
        with caplog.at_level(logging.DEBUG, logger="teachclone.request"):
            await client.get("/openapi.json")

        request_logs = [r for r in caplog.records if "teachclone.request" in r.name]
        assert len(request_logs) == 0

    async def test_request_id_is_unique_per_request(self, client, caplog):
        """Each request should get a unique request ID."""
        ids = []
        with caplog.at_level(logging.WARNING, logger="teachclone.request"):
            await client.get("/nonexistent-1")
            await client.get("/nonexistent-2")

        request_logs = [r for r in caplog.records if "teachclone.request" in r.name]
        for record in request_logs:
            # Extract request ID between first [ and ]
            start = record.message.index("[") + 1
            end = record.message.index("]")
            ids.append(record.message[start:end])

        assert len(ids) >= 2
        assert ids[0] != ids[1], "Request IDs should be unique"

    async def test_405_logged_as_warning(self, client, caplog):
        """405 Method Not Allowed should be logged."""
        with caplog.at_level(logging.WARNING, logger="teachclone.request"):
            await client.delete("/users/me")

        request_logs = [r for r in caplog.records if "teachclone.request" in r.name]
        assert len(request_logs) >= 1
        record = request_logs[-1]
        assert "CLIENT_ERR" in record.message
        assert "405" in record.message
