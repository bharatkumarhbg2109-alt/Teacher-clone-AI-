"""
API Key Authentication Middleware for Local Backend (:8002)
Key is auto-generated on first launch, stored in SQLite, 
and exposed to Electron frontend via IPC.
"""
import os
import secrets
import sqlite3
from pathlib import Path
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

DB_PATH = Path(__file__).parent.parent / "graph_db" / "ingestor.db"
SKIP_PATHS = {"/", "/health", "/docs", "/openapi.json", "/redoc", "/auth/key"}


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.api_key = self._load_or_create_key()

    def _load_or_create_key(self) -> str:
        """Load existing key from SQLite or generate and store a new one."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        row = conn.execute(
            "SELECT value FROM app_config WHERE key = 'api_key'"
        ).fetchone()
        if row:
            conn.close()
            return row[0]
        new_key = "atc-" + secrets.token_hex(24)
        conn.execute(
            "INSERT INTO app_config (key, value) VALUES ('api_key', ?)",
            (new_key,)
        )
        conn.commit()
        conn.close()
        print(f"\n[AUTH] Generated new API key: {new_key}")
        print("[AUTH] This key is stored in ingestor.db and used by the frontend.\n")
        return new_key

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS" or request.url.path in SKIP_PATHS:
            return await call_next(request)

        # Accept key from header OR query param (for EventSource which can't set headers)
        provided = (
            request.headers.get("X-API-Key")
            or request.query_params.get("api_key")
        )
        if provided != self.api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing API key. Check X-API-Key header."}
            )
        return await call_next(request)


def get_api_key() -> str:
    """Helper to read current API key (used by Electron IPC handler)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)
    row = conn.execute(
        "SELECT value FROM app_config WHERE key = 'api_key'"
    ).fetchone()
    if not row:
        new_key = "atc-" + secrets.token_hex(24)
        conn.execute(
            "INSERT INTO app_config (key, value) VALUES ('api_key', ?)",
            (new_key,)
        )
        conn.commit()
        conn.close()
        return new_key
    conn.close()
    return row[0]
