"""Request logging middleware for security monitoring.

Logs all 4xx/5xx responses with:
  - HTTP method and path
  - Status code
  - Response time (ms)
  - Client IP
  - User ID (from Bearer token, best-effort)
  - Request ID (unique per request)

2xx/3xx responses are logged at DEBUG level to avoid noise.
"""
from __future__ import annotations

import logging
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

log = logging.getLogger("teachclone.request")


def _extract_user_id(request: Request) -> str:
    """Best-effort user identification from Authorization header."""
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        return token[:16] + "..."
    return "anonymous"


def _extract_ip(request: Request) -> str:
    """Extract client IP, respecting proxy headers."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("x-real-ip", "")
    if xri:
        return xri.strip()
    return request.client.host if request.client else "unknown"


# Paths to exclude from logging (health checks, docs)
_SKIP_PATHS = frozenset({"/health", "/health/db", "/health/qdrant", "/docs", "/redoc", "/openapi.json"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request/response pair with timing and context.

    Error responses (4xx/5xx) are logged at WARNING level with full context.
    Success responses (2xx/3xx) are logged at DEBUG level.
    Health checks are skipped entirely to reduce noise.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Assign a unique request ID for correlation
        request_id = uuid.uuid4().hex[:12]
        request.state.request_id = request_id

        start = time.perf_counter()
        status_code = 500
        error_detail: str | None = None

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # Let the global exception handler deal with it
            raise
        finally:
            elapsed_ms = round((time.perf_counter() - start) * 1000, 1)
            path = request.url.path

            # Skip health check noise
            if path in _SKIP_PATHS:
                return response if status_code < 500 else None  # type: ignore[return-value]

            method = request.method
            ip = _extract_ip(request)
            user_id = _extract_user_id(request)

            log_context = (
                f"[{request_id}] {method} {path} → {status_code} "
                f"({elapsed_ms}ms) ip={ip} user={user_id}"
            )

            if status_code >= 500:
                log.error("ERROR %s", log_context)
            elif status_code >= 400:
                log.warning("CLIENT_ERR %s", log_context)
            else:
                log.debug("OK %s", log_context)

        return response  # type: ignore[return-value]
