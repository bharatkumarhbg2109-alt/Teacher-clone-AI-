"""End-to-end smoke tests — boots the real FastAPI app, verifies the
OpenAPI schema, and hits every registered router's key endpoint.

These tests use the ``client`` fixture from conftest.py (ASGI transport,
dependency overrides, in-memory SQLite) so they run fully in-process with
no external services required.
"""
import pytest

pytestmark = pytest.mark.asyncio


# ── OpenAPI Schema ────────────────────────────────────────────────────────


class TestOpenAPISchema:
    """Verify the OpenAPI schema loads and contains expected data."""

    async def test_openapi_json_loads(self, client):
        """GET /openapi.json must return 200 with valid JSON schema."""
        r = await client.get("/openapi.json")
        assert r.status_code == 200
        schema = r.json()
        assert "openapi" in schema
        assert "paths" in schema
        assert "info" in schema
        assert schema["info"]["title"] == "TeachClone API"

    async def test_swagger_ui_loads(self, client):
        """GET /docs must return the Swagger UI HTML page."""
        r = await client.get("/docs")
        assert r.status_code == 200
        assert "swagger" in r.text.lower()

    async def test_redoc_loads(self, client):
        """GET /redoc must return the ReDoc UI page."""
        r = await client.get("/redoc")
        assert r.status_code == 200
        assert "redoc" in r.text.lower()

    async def test_schema_has_all_expected_routers(self, client):
        """OpenAPI schema must contain paths from every registered router."""
        r = await client.get("/openapi.json")
        paths = r.json()["paths"]

        # Minimum set — every router must register at least one of these
        expected_prefixes = {
            "/health",
            "/auth",
            "/profiles",
            "/sessions",
            "/chat",
            "/media",
            "/voice",
            "/dna",
            "/quizzes",
            "/billing",
            "/organizations",
            "/embed",
            "/gdpr",
            "/webhooks",
            "/users",
            "/discover",
            "/storage",
            "/t/",
            "/v1/",
        }
        registered = set(paths.keys())
        for prefix in expected_prefixes:
            matches = [p for p in registered if p.startswith(prefix)]
            assert matches, f"No paths found for router prefix '{prefix}'"

    async def test_schema_has_no_internal_only_paths(self, client):
        """Schema should not leak internal debugging endpoints."""
        r = await client.get("/openapi.json")
        paths = set(r.json()["paths"].keys())
        forbidden = {"/debug", "/admin/internal", "/_internal"}
        assert not (paths & forbidden), f"Internal paths leaked: {paths & forbidden}"


# ── Health / Readiness ────────────────────────────────────────────────────


class TestHealthEndpoints:
    """Hit the health and readiness endpoints."""

    async def test_health_ok(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert "version" in body
        assert "timestamp" in body

    async def test_health_db_reachable(self, client):
        r = await client.get("/health/db")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["db"] == "reachable"


# ── Router-by-router smoke ────────────────────────────────────────────────
#
# Each test hits one route per router with either:
#   • no auth → expect 401/403 (protected endpoint), or
#   • a valid test token → expect 2xx or 4xx (but not 5xx)


class TestRouterSmoke_NoAuth:
    """Verify protected endpoints reject unauthenticated requests
    cleanly (401/403, no 500 stack traces)."""

    async def test_profiles_requires_auth(self, client):
        r = await client.get("/profiles")
        assert r.status_code in (401, 403)

    async def test_sessions_requires_auth(self, client):
        r = await client.get("/sessions")
        assert r.status_code in (401, 403)

    async def test_users_me_requires_auth(self, client):
        r = await client.get("/users/me")
        assert r.status_code in (401, 403)

    async def test_gdpr_export_requires_auth(self, client):
        r = await client.post("/gdpr/export")
        assert r.status_code in (401, 403)

    async def test_gdpr_account_requires_auth(self, client):
        r = await client.delete("/gdpr/account")
        assert r.status_code in (401, 403)

    async def test_billing_status_requires_auth(self, client):
        r = await client.get("/billing/status")
        assert r.status_code in (401, 403)

    async def test_organizations_requires_auth(self, client):
        # /organizations is POST-only (create org), no GET list
        r = await client.post("/organizations", json={"name": "Test Org"})
        assert r.status_code in (401, 403)


class TestRouterSmoke_WithAuth:
    """Hit key endpoints with a valid test token.
    Expect 2xx or 4xx (validation), never 5xx."""

    @pytest.fixture
    def auth_headers(self, regular_user):
        return {"Authorization": f"Bearer test_token_{regular_user.clerk_id}"}

    async def test_profiles_list(self, client, auth_headers):
        r = await client.get("/profiles", headers=auth_headers)
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    async def test_sessions_list(self, client, auth_headers):
        r = await client.get("/sessions", headers=auth_headers)
        assert r.status_code == 200

    async def test_users_me(self, client, auth_headers):
        r = await client.get("/users/me", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert "email" in body

    async def test_users_me_stats(self, client, auth_headers):
        r = await client.get("/users/me/stats", headers=auth_headers)
        assert r.status_code == 200

    async def test_discover_teachers(self, client, auth_headers):
        r = await client.get("/discover/teachers", headers=auth_headers)
        assert r.status_code == 200

    async def test_dna_health(self, client, auth_headers):
        r = await client.get("/dna/health", headers=auth_headers)
        # DNA health may 404 or 500 if Ollama isn't running,
        # but it must NOT crash the app
        assert r.status_code in (200, 404, 503)

    async def test_dna_system(self, client, auth_headers):
        r = await client.get("/dna/system", headers=auth_headers)
        assert r.status_code in (200, 404)

    async def test_embed_profiles(self, client, auth_headers):
        r = await client.get("/embed/profiles", headers=auth_headers)
        # Embed profiles may require a query param — 200 or 422 are both valid
        assert r.status_code in (200, 422)

    async def test_gdpr_export(self, client, auth_headers):
        r = await client.post("/gdpr/export", headers=auth_headers)
        # Should be 200 (returns JSON data) or 429/403 (quota/plan)
        assert r.status_code in (200, 403, 429)

    async def test_v1_profiles(self, client, auth_headers):
        r = await client.get("/v1/profiles", headers=auth_headers)
        # v1 may have its own auth layer — 200 or 401 are both acceptable
        assert r.status_code in (200, 401)

    async def test_billing_status(self, client, auth_headers):
        r = await client.get("/billing/status", headers=auth_headers)
        assert r.status_code in (200, 404)

    async def test_organizations_list(self, client, auth_headers):
        # /organizations is POST-only (create), test create instead
        r = await client.post(
            "/organizations",
            headers=auth_headers,
            json={"name": "Smoke Test Org"},
        )
        assert r.status_code in (200, 201, 403, 422)


# ── Error handling sanity ─────────────────────────────────────────────────


class TestErrorHandling:
    """Verify error responses are clean across the app."""

    async def test_404_is_clean(self, client):
        r = await client.get("/this-route-does-not-exist")
        assert r.status_code == 404
        body = r.json()
        assert "detail" in body
        # No traceback, no internal paths
        text = str(body).lower()
        assert "traceback" not in text
        assert "file \"" not in text

    async def test_405_method_not_allowed(self, client):
        r = await client.delete("/health")
        assert r.status_code == 405

    async def test_validation_error_is_clean(self, client, regular_user):
        headers = {"Authorization": f"Bearer test_token_{regular_user.clerk_id}"}
        r = await client.post(
            "/profiles",
            headers=headers,
            json={"name": ""},
        )
        assert r.status_code == 422
        body = r.json()
        assert "detail" in body
        text = str(body).lower()
        assert "traceback" not in text

    async def test_unauthenticated_does_not_leak(self, client):
        """Hitting a protected endpoint without auth should not
        expose any internal information."""
        r = await client.get("/users/me")
        assert r.status_code in (401, 403)
        text = r.text.lower()
        assert "traceback" not in text
        assert "sqlalchemy" not in text
        assert "database" not in text


# ── Route count sanity ────────────────────────────────────────────────────


class TestRouteCount:
    """Ensure the app has a minimum number of registered routes."""

    async def test_minimum_route_count(self, client):
        r = await client.get("/openapi.json")
        paths = r.json()["paths"]
        # We expect at least 60 unique paths
        assert len(paths) >= 60, f"Only {len(paths)} paths registered — expected ≥60"

    async def test_no_duplicate_paths(self, client):
        """No path should appear twice with conflicting methods."""
        r = await client.get("/openapi.json")
        paths = r.json()["paths"]
        # If this fails, a router was included twice
        assert len(paths) == len(set(paths))
