"""Clone a teacher's knowledge base into a forked profile (re-embeds under the
fork's namespace so the copy is fully independent — 'holds the memory')."""
from sqlalchemy import select

from app.tasks._util import run
from app.worker import celery_app


@celery_app.task(name="ai.clone_teacher_knowledge", bind=True)
def clone_teacher_knowledge(self, src_profile_id: str, dst_profile_id: str):
    from app.db.session import AsyncSessionLocal
    from app.models.media_source import MediaSource
    from app.models.transcript_chunk import TranscriptChunk

    async def _impl():
        new_source_ids: list[str] = []
        async with AsyncSessionLocal() as db:
            sources = (
                (await db.execute(
                    select(MediaSource).where(MediaSource.teacher_profile_id == src_profile_id)
                )).scalars().all()
            )
            for src in sources:
                new_src = MediaSource(
                    teacher_profile_id=dst_profile_id,
                    uploaded_by=src.uploaded_by,
                    source_type=src.source_type,
                    original_url=src.original_url,
                    storage_key=src.storage_key,  # shared file reference (read-only reuse)
                    file_name=src.file_name,
                    file_size_bytes=src.file_size_bytes,
                    content_type=src.content_type,
                    duration_seconds=src.duration_seconds,
                    page_count=src.page_count,
                    status="completed",
                    transcript_chunks=src.transcript_chunks,
                )
                db.add(new_src)
                await db.flush()
                new_source_ids.append(str(new_src.id))

                chunks = (
                    (await db.execute(
                        select(TranscriptChunk)
                        .where(TranscriptChunk.media_source_id == src.id)
                        .order_by(TranscriptChunk.chunk_index)
                    )).scalars().all()
                )
                db.add_all(
                    [
                        TranscriptChunk(
                            media_source_id=new_src.id,
                            chunk_index=c.chunk_index,
                            text=c.text,
                            start_time=c.start_time,
                            end_time=c.end_time,
                            page=c.page,
                            speaker_label=c.speaker_label,
                            token_count=c.token_count,
                            content_type=c.content_type,
                        )
                        for c in chunks
                    ]
                )
            await db.commit()
        return new_source_ids

    new_ids = run(_impl())

    # Re-embed each copied source under the fork's namespace.
    from app.tasks.embedding_tasks import embed_and_store

    for sid in new_ids:
        embed_and_store.delay(sid)
