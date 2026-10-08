"""Public API key generation / verification (SHA-256 hashed at rest)."""
import base64
import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_key import ApiKey


def generate_api_key() -> tuple[str, str, str]:
    raw = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode().rstrip("=")
    full_key = f"tc_live_{raw}"
    key_hash = hashlib.sha256(full_key.encode()).hexdigest()
    return full_key, key_hash, full_key[:16]


async def create_api_key(db: AsyncSession, user_id, name: str) -> tuple[ApiKey, str]:
    full_key, key_hash, prefix = generate_api_key()
    record = ApiKey(user_id=user_id, key_hash=key_hash, key_prefix=prefix, name=name)
    db.add(record)
    await db.flush()
    return record, full_key  # full_key shown once


async def revoke_api_key(db: AsyncSession, key_id, user_id) -> bool:
    key = (
        await db.execute(
            select(ApiKey).where(ApiKey.id == key_id, ApiKey.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not key:
        return False
    key.is_active = False
    await db.flush()
    return True
