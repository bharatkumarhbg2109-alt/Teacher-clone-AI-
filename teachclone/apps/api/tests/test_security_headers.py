"""Tests for the security headers middleware."""
import pytest

pytestmark = pytest.mark.asyncio


class TestSecurityHeaders:
    """Verify security headers are present on every response."""

    async def test_content_security_policy_present(self, client):
        r = await client.get("/health")
        assert "content-security-policy" in r.headers
        csp = r.headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "script-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    async def test_csp_blocks_inline_scripts(self, client):
        """CSP must not allow 'unsafe-inline' for scripts."""
        csp = client.headers.get("content-security-policy", "")
        # The raw CSP string is on the response, not the request headers.
        # We need to actually make a request.
        r = await client.get("/health")
        csp = r.headers["content-security-policy"]
        # script-src should only be 'self', not 'unsafe-inline'
        script_directive = [d for d in csp.split(";") if "script-src" in d][0]
        assert "unsafe-inline" not in script_directive

    async def test_csp_blocks_external_script_sources(self, client):
        """CSP should not allow arbitrary external script sources."""
        r = await client.get("/health")
        csp = r.headers["content-security-policy"]
        assert "https:" not in csp.split("script-src")[1].split(";")[0]

    async def test_x_frame_options_deny(self, client):
        """X-Frame-Options DENY prevents clickjacking."""
        r = await client.get("/health")
        assert r.headers.get("x-frame-options") == "DENY"

    async def test_x_content_type_options_nosniff(self, client):
        """X-Content-Type-Options prevents MIME-type sniffing."""
        r = await client.get("/health")
        assert r.headers.get("x-content-type-options") == "nosniff"

    async def test_referrer_policy(self, client):
        """Referrer-Policy should restrict cross-origin referrer leakage."""
        r = await client.get("/health")
        rp = r.headers.get("referrer-policy", "")
        assert rp in ("strict-origin-when-cross-origin", "no-referrer")

    async def test_permissions_policy(self, client):
        """Permissions-Policy should disable unnecessary browser features."""
        r = await client.get("/health")
        pp = r.headers.get("permissions-policy", "")
        assert "camera=()" in pp
        assert "microphone=()" in pp
        assert "geolocation=()" in pp

    async def test_xss_protection_disabled(self, client):
        """X-XSS-Protection should be 0 (CSP replaces it)."""
        r = await client.get("/health")
        assert r.headers.get("x-xss-protection") == "0"

    async def test_hsts_not_set_in_dev_mode(self, client):
        """HSTS should NOT be set when DEV_MODE is true."""
        r = await client.get("/health")
        # In test env DEV_MODE=true, so no HSTS
        hsts = r.headers.get("strict-transport-security")
        assert hsts is None

    async def test_security_headers_on_404(self, client):
        """Security headers should be present even on error responses."""
        r = await client.get("/nonexistent-route")
        assert r.status_code == 404
        assert "content-security-policy" in r.headers
        assert r.headers.get("x-frame-options") == "DENY"
        assert r.headers.get("x-content-type-options") == "nosniff"

    async def test_security_headers_on_422(self, client, regular_user):
        """Security headers should be present on validation errors."""
        headers = {"Authorization": f"Bearer test_token_{regular_user.clerk_id}"}
        r = await client.post("/profiles", json={"name": ""}, headers=headers)
        assert r.status_code == 422
        assert "content-security-policy" in r.headers
        assert r.headers.get("x-frame-options") == "DENY"

    async def test_security_headers_on_401(self, client):
        """Security headers should be present on auth errors."""
        r = await client.get("/users/me")
        assert r.status_code == 401
        assert "content-security-policy" in r.headers
        assert r.headers.get("x-content-type-options") == "nosniff"

    async def test_security_headers_on_500(self, client):
        """Security headers should be present even on 500 responses."""
        r = await client.get("/health/db")  # May fail if DB issue
        # Whatever status we get, headers should be there
        assert "content-security-policy" in r.headers

    async def test_csp_img_allows_data_uris(self, client):
        """CSP img-src should allow data: URIs for inline images."""
        r = await client.get("/health")
        csp = r.headers["content-security-policy"]
        img_directive = [d for d in csp.split(";") if "img-src" in d][0]
        assert "data:" in img_directive

    async def test_csp_connect_src_self_only(self, client):
        """CSP connect-src should only allow same-origin (no external APIs)."""
        r = await client.get("/health")
        csp = r.headers["content-security-policy"]
        connect_directive = [d for d in csp.split(";") if "connect-src" in d][0]
        # Should only have 'self', not wildcards or external URLs
        sources = connect_directive.replace("connect-src", "").strip()
        assert sources == "'self'"

    async def test_csp_frame_src_none(self, client):
        """CSP frame-src should be 'none' — no iframe embedding."""
        r = await client.get("/health")
        csp = r.headers["content-security-policy"]
        frame_directive = [d for d in csp.split(";") if "frame-src" in d][0]
        assert "'none'" in frame_directive

    async def test_csp_object_src_none(self, client):
        """CSP object-src should be 'none' — no plugins."""
        r = await client.get("/health")
        csp = r.headers["content-security-policy"]
        object_directive = [d for d in csp.split(";") if "object-src" in d][0]
        assert "'none'" in object_directive

    async def test_csp_base_uri_self(self, client):
        """CSP base-uri should be 'self' — prevents base tag injection."""
        r = await client.get("/health")
        csp = r.headers["content-security-policy"]
        base_directive = [d for d in csp.split(";") if "base-uri" in d][0]
        assert "'self'" in base_directive

    async def test_csp_form_action_self(self, client):
        """CSP form-action should be 'self' — prevents form hijacking."""
        r = await client.get("/health")
        csp = r.headers["content-security-policy"]
        form_directive = [d for d in csp.split(";") if "form-action" in d][0]
        assert "'self'" in form_directive
