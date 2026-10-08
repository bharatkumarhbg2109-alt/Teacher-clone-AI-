"""Local file storage endpoints (used only when STORAGE_BACKEND=local).

The browser PUTs uploads here (in place of a presigned S3 URL) and GETs cached
audio from here. Unauthenticated — local dev only.
"""
import mimetypes

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from app.services.storage import storage_service

router = APIRouter(prefix="/storage", tags=["storage"])


@router.put("/put")
async def put_object(key: str, request: Request) -> dict:
    body = await request.body()
    storage_service.write_local(key, body)
    return {"ok": True, "bytes": len(body)}


@router.get("/get")
async def get_object(key: str):
    if not storage_service.object_exists(key):
        raise HTTPException(404, "Not found")
    data = storage_service.get_bytes(key)
    media_type = mimetypes.guess_type(key)[0] or "application/octet-stream"
    return Response(content=data, media_type=media_type)
