"""Security headers middleware for FastAPI.

Adds HTTP security headers to every response:

  Content-Security-Policy  — Restricts sources for scripts, styles, images,
                             fonts, frames, and connections. Prevents XSS.
  X-Frame-Options          — DENY (prevents clickjacking).
  X-Content-Type-Options   — nosniff (prevents MIME-type sniffing).
  Referrer-Policy           — strict-origin-when-cross-origin.
  Permissions-Policy        — Disables unnecessary browser features.
  Strict-Transport-Security — max-age=63072000; includeSubDomains (prod only).
  X-XSS-Protection          — 0 (modern browsers; CSP replaces this).

The CSP is intentionally strict for an API that serves JSON.  The frontend
(Next.js on a separate origin) applies its own CSP via next.config.js.
"""
from __future__ import annotations

import os

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

# --- CSP directives --------------------------------------------------------
# Strict default that only allows same-origin requests.
# - script-src 'self': only scripts from our own origin
# - style-src 'self' 'unsafe-inline': inline styles needed for some UI libs
# - img-src 'self' data: blob:: data URIs and blob URLs for previews
# - connect-src 'self': XHR/fetch to our own API only
# - frame-ancestors 'none': equivalent to X-Frame-Options DENY
# - default-src 'self': fallback for any directive not listed
_CSP_DIRECTIVES = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self'",
    "connect-src 'self'",
    "media-src 'self' blob:",
    "object-src 'none'",
    "frame-src 'none'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "form-action 'self'",
]

# Allow the frontend origin to embed the API in production
_extra_connect = os.getenv("CSP_CONNECT_EXTRA", "")
if _extra_connect:
    _CSP_DIRECTIVES.append(f"connect-src 'self' {_extra_connect}")

CSP_POLICY = "; ".join(_CSP_DIRECTIVES)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Injects security headers into every response."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        # Skip headers for streaming/SSE responses (they set their own headers)
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return response

        response.headers["Content-Security-Policy"] = CSP_POLICY
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["X-XSS-Protection"] = "0"

        # HSTS only in production (HTTPS)
        if not os.getenv("DEV_MODE", "true").lower() == "true":
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )

        return response
