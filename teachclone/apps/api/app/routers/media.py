"""Media & document ingestion — links, and any-size uploads (multipart)."""
import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.dependencies import get_current_user, get_db
from app.models.audit_log import AuditLog
from app.models.media_source import MediaSource
from app.models.teacher_profile import TeacherProfile
from app.models.user import User
from app.schemas.media import (
    MediaSourceResponse,
    MultipartPartRequest,
    MultipartPartUrl,
    UploadCompleteRequest,
    UploadInitiateRequest,
    UploadInitiateResponse,
    YouTubeIngestRequest,
)
from app.services import billing
from app.services.storage import get_max_file_size, storage_service, validate_file_upload

router = APIRouter(prefix="/media", tags=["media"])

_YT = re.compile(r"(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)")

_DOC_TYPES = {"pdf_upload", "doc_upload", "image_upload"}


def _infer_source_type(content_type: str, file_name: str) -> str:
    ct = (content_type or "").lower()
    name = (file_name or "").lower()
    if ct.startswith("video/") or name.endswith((".mp4", ".mov", ".webm", ".mkv", ".avi")):
        return "video_upload"
    if ct.startswith("audio/") or name.endswith((".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac")):
        return "audio_upload"
    if ct == "application/pdf" or name.endswith(".pdf"):
        return "pdf_upload"
    if ct.startswith("image/") or name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff")):
        return "image_upload"
    return "doc_upload"  # docx / pptx / txt / md


async def _check_source_quota(db: AsyncSession, user: User) -> None:
    ok, reason = await billing.check_quota(db, user, "source_processed")
    if not ok:
        raise HTTPException(402, detail={"error": "quota_exceeded", "reason": reason, "upgrade_url": "/pricing"})


async def _get_owned_source(
    db: AsyncSession, media_source_id: str, user: User
) -> MediaSource:
    """Return a source only when its teacher profile belongs to the caller."""
    source = (
        await db.execute(select(MediaSource).where(MediaSource.id == media_source_id))
    ).scalar_one_or_none()
    if not source:
        raise HTTPException(404, "Media source not found")

    profile_owner_id = (
        await db.execute(
            select(TeacherProfile.user_id).where(TeacherProfile.id == source.teacher_profile_id)
        )
    ).scalar_one_or_none()
    if profile_owner_id != user.id:
        raise HTTPException(403, "Not your teacher profile")
    return source


async def _require_owned_profile(
    db: AsyncSession, teacher_profile_id: str, user: User
) -> None:
    owner_id = (
        await db.execute(
            select(TeacherProfile.user_id).where(TeacherProfile.id == teacher_profile_id)
        )
    ).scalar_one_or_none()
    if owner_id is None:
        raise HTTPException(404, "Teacher profile not found")
    if owner_id != user.id:
        raise HTTPException(403, "Not your teacher profile")


@router.post("/youtube", response_model=MediaSourceResponse, status_code=201)
async def ingest_youtube(
    payload: YouTubeIngestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MediaSource:
    if not _YT.search(payload.youtube_url):
        raise HTTPException(400, "Invalid YouTube URL")
    await _check_source_quota(db, user)
    source = MediaSource(
        teacher_profile_id=payload.teacher_profile_id,
        uploaded_by=user.id,
        source_type="youtube_url",
        original_url=payload.youtube_url,
        status="pending",
    )
    db.add(source)
    await db.flush()
    await billing.log_usage(db, user.id, "source_processed", {"type": "youtube"})
    await db.commit()  # release the write lock before in-process processing

    from app.tasks.dispatch import dispatch
    from app.tasks.media_tasks import process_media

    await dispatch(process_media, str(source.id))
    return source


@router.post("/upload/initiate", response_model=UploadInitiateResponse)
async def upload_initiate(
    payload: UploadInitiateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UploadInitiateResponse:
    # Validate file metadata before initiating upload
    validate_file_upload(
        filename=payload.file_name,
        content_type=payload.content_type,
        file_size=payload.file_size,
    )
    await _check_source_quota(db, user)
    source_type = _infer_source_type(payload.content_type, payload.file_name)
    key = storage_service.generate_key(str(user.id), payload.teacher_profile_id, payload.file_name)

    source = MediaSource(
        teacher_profile_id=payload.teacher_profile_id,
        uploaded_by=user.id,
        source_type=source_type,
        storage_key=key,
        file_name=payload.file_name,
        file_size_bytes=payload.file_size,
        content_type=payload.content_type,
        status="pending",
    )
    db.add(source)
    await db.flush()

    expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    # Large files -> multipart ("any size"). Local storage always single-shot.
    if settings.STORAGE_BACKEND != "local" and payload.file_size >= settings.MULTIPART_THRESHOLD_BYTES:
        upload_id = storage_service.create_multipart(key, payload.content_type)
        part_size = settings.MULTIPART_PART_SIZE_BYTES
        part_count = (payload.file_size + part_size - 1) // part_size
        return UploadInitiateResponse(
            media_source_id=str(source.id),
            upload_key=key,
            multipart_upload_id=upload_id,
            part_size=part_size,
            part_count=part_count,
            expires_at=expires_at,
        )

    # Use presigned POST with S3-enforced conditions (size + Content-Type).
    # For local backend this falls back to a presigned PUT wrapper.
    max_size = get_max_file_size(payload.content_type)
    post = storage_service.presign_post(key, payload.content_type, max_size)
    return UploadInitiateResponse(
        media_source_id=str(source.id),
        upload_url=post["url"],
        upload_fields=post["fields"],
        upload_key=key,
        expires_at=expires_at,
    )


@router.post("/upload/parts", response_model=list[MultipartPartUrl])
async def upload_parts(
    payload: MultipartPartRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MultipartPartUrl]:
    source = await _get_owned_source(db, payload.media_source_id, user)
    if source.storage_key != payload.upload_key:
        raise HTTPException(400, "Upload key does not match media source")
    return [
        MultipartPartUrl(
            part_number=n,
            url=storage_service.presign_part(payload.upload_key, payload.multipart_upload_id, n),
        )
        for n in payload.part_numbers
    ]


@router.post("/upload/complete", response_model=MediaSourceResponse)
async def upload_complete(
    payload: UploadCompleteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MediaSource:
    source = (
        await db.execute(select(MediaSource).where(MediaSource.id == payload.media_source_id))
    ).scalar_one_or_none()
    if not source or source.uploaded_by != user.id:
        raise HTTPException(404, "Media source not found")

    if payload.multipart_upload_id and payload.parts:
        storage_service.complete_multipart(payload.storage_key, payload.multipart_upload_id, payload.parts)
    elif not storage_service.object_exists(payload.storage_key):
        raise HTTPException(400, "Uploaded object not found in storage")

    source.storage_key = payload.storage_key
    source.file_size_bytes = storage_service.object_size(payload.storage_key) or source.file_size_bytes
    source.status = "pending"
    await db.flush()
    await billing.log_usage(db, user.id, "source_processed", {"type": source.source_type})
    await db.commit()  # release the write lock before in-process processing

    from app.tasks.dispatch import dispatch

    if source.source_type in _DOC_TYPES:
        from app.tasks.doc_tasks import process_document

        await dispatch(process_document, str(source.id))
    else:
        from app.tasks.media_tasks import process_media

        await dispatch(process_media, str(source.id))
    return source


@router.get("/{media_source_id}/status", response_model=MediaSourceResponse)
async def media_status(
    media_source_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MediaSource:
    return await _get_owned_source(db, media_source_id, user)


@router.get("/{media_source_id}/progress")
async def media_progress(
    media_source_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Server-Sent Events stream of processing status."""
    await _get_owned_source(db, media_source_id, user)

    async def event_gen():
        from app.db.session import AsyncSessionLocal

        for _ in range(300):  # ~10 min max
            async with AsyncSessionLocal() as db:
                source = (
                    await db.execute(
                        select(MediaSource).where(MediaSource.id == media_source_id)
                    )
                ).scalar_one_or_none()
            if not source:
                yield {"data": json.dumps({"status": "failed", "stage": "not_found"})}
                return
            yield {
                "data": json.dumps(
                    {
                        "status": source.status,
                        "transcript_chunks": source.transcript_chunks,
                        "stage": source.status,
                    }
                )
            }
            if source.status in ("completed", "failed"):
                return
            await asyncio.sleep(2)

    return EventSourceResponse(event_gen())


@router.delete("/{media_source_id}")
async def delete_media(
    media_source_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    source = (
        await db.execute(select(MediaSource).where(MediaSource.id == media_source_id))
    ).scalar_one_or_none()
    if not source or source.uploaded_by != user.id:
        raise HTTPException(404, "Media source not found")

    from app.services.vector_store import vector_store

    try:
        await vector_store.delete_by_media_source(str(source.id))
    except Exception as e:
        logger.warning("Vector cleanup failed for media source %s: %s. Manual cleanup may be needed.", source.id, e)
    if source.storage_key:
        storage_service.delete_object(source.storage_key)
    await db.delete(source)
    AuditLog.write(db, user.id, user.email, "media.deleted", "media_source", media_source_id)
    await db.flush()
    return {"success": True}


@router.get("/profile/{teacher_profile_id}", response_model=list[MediaSourceResponse])
async def list_profile_media(
    teacher_profile_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MediaSource]:
    await _require_owned_profile(db, teacher_profile_id, user)
    rows = (
        (await db.execute(
            select(MediaSource)
            .where(MediaSource.teacher_profile_id == teacher_profile_id)
            .order_by(MediaSource.created_at.desc())
        )).scalars().all()
    )
    return list(rows)
