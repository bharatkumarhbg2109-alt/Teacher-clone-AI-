from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "version": settings.VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dev_mode": settings.DEV_MODE,
    }


@router.get("/health/db")
async def health_db(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(text("SELECT 1"))
    return {"status": "ok", "db": "reachable"}


@router.get("/health/qdrant")
async def health_qdrant() -> dict:
    from app.services.vector_store import vector_store

    collections = await vector_store.client.get_collections()
    return {"status": "ok", "collections": [c.name for c in collections.collections]}
