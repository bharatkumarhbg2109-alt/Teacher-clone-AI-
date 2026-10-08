"""Document ingestion: PDF / DOCX / PPTX / TXT / image -> chunks -> AI pipeline."""
import datetime
import os
import tempfile

from sqlalchemy import select

from app.tasks._util import run
from app.worker import celery_app


@celery_app.task(name="media.process_document", bind=True, max_retries=3, default_retry_delay=60)
def process_document(self, media_source_id: str):
    from app.db.session import AsyncSessionLocal
    from app.models.media_source import MediaSource
    from app.models.transcript_chunk import TranscriptChunk
    from app.services.doc_extractor import doc_extractor
    from app.services.storage import storage_service

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
                    self.update_state(state="PROGRESS", meta={"progress": 20, "stage": "downloading"})
                    raw = os.path.join(tmp, source.file_name or "document.bin")
                    storage_service.download_to_path(source.storage_key, raw)

                    self.update_state(state="PROGRESS", meta={"progress": 50, "stage": "extracting"})
                    chunks = doc_extractor.extract(raw, source.source_type)
                    if source.source_type == "pdf_upload":
                        source.page_count = doc_extractor.page_count(raw)

                self.update_state(state="PROGRESS", meta={"progress": 80, "stage": "saving"})
                db.add_all(
                    [
                        TranscriptChunk(
                            media_source_id=source.id,
                            chunk_index=c.chunk_index,
                            text=c.text,
                            page=c.page,
                            token_count=c.token_count,
                            content_type=c.content_type,
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

    from app.tasks.embedding_tasks import embed_and_store

    embed_and_store.delay(media_source_id)
