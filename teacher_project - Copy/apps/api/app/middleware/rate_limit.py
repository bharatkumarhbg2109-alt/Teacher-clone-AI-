"""Sliding-window rate limiter middleware for FastAPI.

Uses Redis when available (falling back to an in-memory sliding window when
Redis is unreachable).  Applied per-user (from the Bearer token / client IP)
with separate budgets for different endpoint groups.

Groups:
    chat    — POST /chat/{session_id}/message (per-user token, 30/60s)
    dna     — POST /dna/extract-* and /dna/regenerate/* (per-user token, 5/60s)
    auth    — POST /auth/sync (per-IP, 10/60s with exponential backoff)
    upload  — POST /media/youtube, /media/upload, /media/upload/complete (per-user, 20/60s)
    voice   — POST /voice/transcribe, /voice/speak (per-user, 60/60s)
    public  — GET /t/{token}, POST /embed/*, GET /embed/* (per-IP, 100/60s)

Headers returned on every response:
    X-RateLimit-Limit     — max requests in the current window
    X-RateLimit-Remaining — requests left in the current window
    X-RateLimit-Reset     — UTC epoch seconds when the window resets

On 429:
    Retry-After — seconds until the client should retry
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

log = logging.getLogger("teachclone.ratelimit")

# ---------------------------------------------------------------------------
#  Endpoint group → (limit, window) mapping
# ---------------------------------------------------------------------------

# Populated at startup from settings; can be overridden for tests.
_groups: dict[str, tuple[int, int]] = {}

# Auth backoff state: {ip: [(failure_count, window_multiplier)]}
_auth_failures: dict[str, int] = {}


def configure_groups(
    chat_limit: int,
    dna_limit: int,
    auth_limit: int = 10,
    auth_window: int = 60,
    upload_limit: int = 20,
    voice_limit: int = 60,
    public_limit: int = 100,
    window: int = 60,
    backoff_base: int = 60,
    backoff_max: int = 900,
) -> None:
    """Set rate-limit budgets for each endpoint group."""
    global _groups
    _groups = {
        "chat": (chat_limit, window),
        "dna": (dna_limit, window),
        "auth": (auth_limit, auth_window),
        "upload": (upload_limit, window),
        "voice": (voice_limit, window),
        "public": (public_limit, window),
    }


def _classify(path: str, method: str) -> str | None:
    """Return the rate-limit group name for a request, or None to skip."""
    # ── Public GET endpoints ──────────────────────────────────────────────
    if method == "GET":
        # GET /t/{token} — public share view
        parts = path.split("/")
        if len(parts) == 3 and parts[1] == "t":
            return "public"
        # GET /embed/profiles
        if path.startswith("/embed/"):
            return "public"
        return None

    if method != "POST":
        return None

    # ── Auth ──────────────────────────────────────────────────────────────
    if path == "/auth/sync":
        return "auth"

    # ── Upload ────────────────────────────────────────────────────────────
    if path.startswith("/media/"):
        if path in ("/media/youtube", "/media/upload", "/media/upload/complete"):
            return "upload"
        return None

    # ── Voice ─────────────────────────────────────────────────────────────
    if path in ("/voice/transcribe", "/voice/speak"):
        return "voice"

    # ── Embed chat (public, IP-based) ─────────────────────────────────────
    if path == "/embed/chat":
        return "public"

    # ── Chat messages: POST /chat/{session_id}/message ────────────────────
    if path.startswith("/chat/") and path.endswith("/message"):
        return "chat"

    # ── DNA extraction: POST /dna/extract-* and /dna/regenerate/* ─────────
    if path.startswith("/dna/"):
        for suffix in ("/extract-from-url", "/extract-from-file"):
            if path.endswith(suffix):
                return "dna"
        parts = path.split("/")
        if len(parts) == 4 and parts[2] == "regenerate":
            return "dna"

    return None


# ---------------------------------------------------------------------------
#  Auth backoff logic (exponential window escalation)
# ---------------------------------------------------------------------------

def _get_auth_backoff_window(ip: str, base_window: int, max_window: int) -> tuple[int, int]:
    """Return (effective_window, failure_count) for the given IP.
    Escalates: 3 failures → 2x, 5 failures → 4x, 10 failures → max_window."""
    failures = _auth_failures.get(ip, 0)
    if failures >= 10:
        return max_window, failures
    elif failures >= 5:
        return base_window * 4, failures
    elif failures >= 3:
        return base_window * 2, failures
    return base_window, failures


def _record_auth_failure(ip: str) -> None:
    """Increment the failure counter for an IP."""
    _auth_failures[ip] = _auth_failures.get(ip, 0) + 1


def _reset_auth_failures(ip: str) -> None:
    """Clear the failure counter (on successful auth)."""
    _auth_failures.pop(ip, None)


# ---------------------------------------------------------------------------
#  Sliding window counters (in-memory fallback)
# ---------------------------------------------------------------------------

class _InMemoryWindow:
    """Thread-safe sliding window counter using a dict of {key: [timestamps]}."""

    def __init__(self) -> None:
        self._buckets: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def increment(self, key: str, window: int) -> tuple[int, float]:
        """Increment the counter and return (count_in_window, reset_epoch)."""
        now = time.time()
        cutoff = now - window
        async with self._lock:
            # Prune old entries
            self._buckets[key] = [
                ts for ts in self._buckets[key] if ts > cutoff
            ]
            self._buckets[key].append(now)
            count = len(self._buckets[key])
            # Reset time = oldest entry + window, or now + window if empty
            reset = (self._buckets[key][0] + window) if self._buckets[key] else now + window
        return count, reset

    async def get_count(self, key: str, window: int) -> tuple[int, float]:
        """Read the current count without incrementing."""
        now = time.time()
        cutoff = now - window
        async with self._lock:
            self._buckets[key] = [
                ts for ts in self._buckets[key] if ts > cutoff
            ]
            count = len(self._buckets[key])
            reset = (self._buckets[key][0] + window) if self._buckets[key] else now + window
        return count, reset


_memory = _InMemoryWindow()

# ---------------------------------------------------------------------------
#  Redis-backed sliding window (Lua script for atomicity)
# ---------------------------------------------------------------------------

_SLIDING_WINDOW_SCRIPT = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local now = tonumber(ARGV[2])

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)

-- Count current entries
local count = redis.call('ZCARD', key)

-- Add the new request
redis.call('ZADD', key, now, now .. '-' .. math.random(100000))
redis.call('EXPIRE', key, window)

return {count + 1, now + window}
"""

_redis_client = None
_redis_available = True
_lua_sha: str | None = None


def _get_redis():
    """Lazily create a Redis connection from the app's REDIS_URL."""
    global _redis_client, _redis_available
    if not _redis_available:
        return None
    try:
        import redis.asyncio as aioredis
        from app.config import settings

        if _redis_client is None:
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
        return _redis_client
    except Exception:
        _redis_available = False
        return None


async def _redis_increment(key: str, window: int) -> tuple[int, float] | None:
    """Try Redis sliding window; return None on failure."""
    global _lua_sha
    r = _get_redis()
    if r is None:
        return None
    try:
        now_ms = int(time.time() * 1000)
        now_s = time.time()

        if _lua_sha is None:
            _lua_sha = await r.script_load(_SLIDING_WINDOW_SCRIPT)

        result = await r.evalsha(_lua_sha, 1, key, window * 1000, now_ms)
        count = int(result[0])
        reset = float(result[1]) / 1000.0
        return count, reset
    except Exception as exc:
        # Redis failure — fall back to in-memory
        log.debug("Redis rate-limit fallback (%s): %s", key, exc)
        _redis_client = None  # force reconnect on next attempt
        return None


# ---------------------------------------------------------------------------
#  FastAPI middleware
# ---------------------------------------------------------------------------

def _extract_user_id(request: Request) -> str:
    """Best-effort user identification from the request state or auth header.

    In DEV_MODE the dependency injects a dev user into the DB session but
    the middleware runs before dependencies.  We use the raw Authorization
    header as the identity key; in DEV_MODE all requests share the same
    anonymous key so they share the budget (which is fine for local dev).
    """
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        token = auth.split(" ", 1)[1]
        # Use first 16 chars of token as stable key (avoids storing full token)
        return token[:16]
    return request.client.host if request.client else "anonymous"


def _extract_ip(request: Request) -> str:
    """Extract client IP for IP-based rate limiting (auth, public)."""
    # Check X-Forwarded-For for proxied requests
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    xri = request.headers.get("x-real-ip", "")
    if xri:
        return xri.strip()
    return request.client.host if request.client else "anonymous"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter applied to chat, DNA, auth, upload, voice, and public endpoints."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        group = _classify(request.url.path, request.method)
        if group is None:
            return await call_next(request)

        # IP-based groups use client IP; token-based groups use Bearer token
        if group in ("auth", "public"):
            rate_key = _extract_ip(request)
        else:
            rate_key = _extract_user_id(request)

        # Auth group has dynamic window via exponential backoff
        if group == "auth":
            from app.config import settings
            base_window = _groups.get("auth", (10, 60))[1]
            effective_window, failures = _get_auth_backoff_window(
                rate_key, settings.RATE_LIMIT_BACKOFF_BASE, settings.RATE_LIMIT_BACKOFF_MAX
            )
            limit = _groups.get("auth", (10, 60))[0]
            window = effective_window
        else:
            limit, window = _groups.get(group, (100, 60))

        cache_key = f"rl:{group}:{rate_key}"

        # Try Redis first, fall back to in-memory
        result = await _redis_increment(cache_key, window)
        if result is None:
            count, reset = await _memory.increment(cache_key, window)
        else:
            count, reset = result

        remaining = max(0, limit - count)
        reset_epoch = int(reset)

        if count > limit:
            # Record auth failures even on 429 for backoff escalation
            if group == "auth":
                _record_auth_failure(rate_key)
            retry_after = max(1, reset_epoch - int(time.time()))
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": retry_after,
                    "limit": limit,
                    "window": window,
                    "group": group,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_epoch),
                },
            )

        response = await call_next(request)

        # Track auth success/failure for backoff
        if group == "auth":
            if response.status_code >= 400:
                _record_auth_failure(rate_key)
            else:
                _reset_auth_failures(rate_key)

        # Attach rate-limit headers to successful responses too
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_epoch)

        return response
