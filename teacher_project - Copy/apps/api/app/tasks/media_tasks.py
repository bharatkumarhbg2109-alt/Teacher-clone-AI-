"""Media ingestion: link / video / audio -> transcript chunks -> AI pipeline."""
import datetime
import os
import tempfile

from sqlalchemy import select

from app.tasks._util import run
from app.worker import celery_app


@celery_app.task(name="media.process_media", bind=True, max_retries=3, default_retry_delay=60)
def process_media(self, media_source_id: str):
    from app.db.session import AsyncSessionLocal
    from app.models.media_source import MediaSource
    from app.models.transcript_chunk import TranscriptChunk
    from app.services.audio_extractor import audio_extractor
    from app.services.storage import storage_service
    from app.services.transcriber import transcriber

    async def _impl():
        async with AsyncSessionLocal() as db:
            source = (
                await db.execute(select(MediaSource).where(MediaSource.id == media_source_id))
            ).scalar_one()
            try:
                source.status = "processing"
                source.processing_started_at = datetime.datetime.utcnow()
                await db.commit()

                with tempfile.TemporaryDirectory() as tmp:
                    self.update_state(state="PROGRESS", meta={"progress": 15, "stage": "downloading"})
                    if source.source_type == "youtube_url":
                        audio_path = await audio_extractor.from_youtube_url(source.original_url, tmp)
                    else:
                        raw = os.path.join(tmp, source.file_name or "media.bin")
                        storage_service.download_to_path(source.storage_key, raw)
                        audio_path = await audio_extractor.from_video_file(raw, tmp)

                    source.duration_seconds = int(await audio_extractor.get_duration(audio_path))
                    await db.commit()

                    self.update_state(state="PROGRESS", meta={"progress": 45, "stage": "transcribing"})
                    chunks = transcriber.transcribe(audio_path)

                self.update_state(state="PROGRESS", meta={"progress": 75, "stage": "saving"})
                db.add_all(
                    [
                        TranscriptChunk(
                            media_source_id=source.id,
                            chunk_index=c.chunk_index,
                            text=c.text,
                            start_time=c.start_time,
                            end_time=c.end_time,
                            token_count=c.token_count,
                            content_type="audio",
                        )
                        for c in chunks
                    ]
                )
                source.transcript_chunks = len(chunks)
                source.status = "completed"
                source.processing_completed_at = datetime.datetime.utcnow()
                await db.commit()
            except Exception as exc:
                source.status = "failed"
                source.error_message = str(exc)[:500]
                await db.commit()
                raise self.retry(exc=exc)

    run(_impl())

    # Kick off the AI pipeline (embed -> style; + vision for uploaded video).
    from app.tasks.embedding_tasks import embed_and_store

    embed_and_store.delay(media_source_id)

    from app.db.session import AsyncSessionLocal as _S

    async def _needs_vision() -> bool:
        async with _S() as db:
            src = (
                await db.execute(select(MediaSource).where(MediaSource.id == media_source_id))
            ).scalar_one()
            return src.source_type == "video_upload" and bool(src.storage_key)

    if run(_needs_vision()):
        from app.tasks.vision_tasks import analyze_frames

        analyze_frames.delay(media_source_id)
