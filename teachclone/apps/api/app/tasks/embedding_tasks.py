"""Embed a source's chunks into Qdrant, then trigger style extraction."""
from sqlalchemy import select

from app.tasks._util import run
from app.worker import celery_app


@celery_app.task(name="ai.embed_and_store", bind=True, max_retries=2)
def embed_and_store(self, media_source_id: str):
    from app.db.session import AsyncSessionLocal
    from app.models.media_source import MediaSource
    from app.models.transcript_chunk import TranscriptChunk
    from app.services.embedder import embedder
    from app.services.vector_store import ChunkPoint, vector_store

    async def _impl():
        async with AsyncSessionLocal() as db:
            source = (
                await db.execute(select(MediaSource).where(MediaSource.id == media_source_id))
            ).scalar_one()
            profile_id = str(source.teacher_profile_id)

            chunks = (
                (await db.execute(
                    select(TranscriptChunk)
                    .where(
                        TranscriptChunk.media_source_id == media_source_id,
                        TranscriptChunk.embedding_id.is_(None),
                    )
                    .order_by(TranscriptChunk.chunk_index)
                )).scalars().all()
            )
            if not chunks:
                return

            self.update_state(state="PROGRESS", meta={"progress": 30, "stage": "embedding"})
            dense_vecs = await embedder.embed_texts([c.text for c in chunks])

            self.update_state(state="PROGRESS", meta={"progress": 80, "stage": "storing"})
            await vector_store.ensure_collection()
            points = []
            for chunk, dense in zip(chunks, dense_vecs):
                points.append(
                    ChunkPoint(
                        id=str(chunk.id),
                        dense_vector=dense,
                        sparse_vector=embedder.compute_sparse_vector(chunk.text),
                        payload={
                            "text": chunk.text,
                            "media_source_id": media_source_id,
                            "teacher_profile_id": profile_id,
                            "start_time": chunk.start_time,
                            "end_time": chunk.end_time,
                            "page": chunk.page,
                            "chunk_index": chunk.chunk_index,
                            "content_type": chunk.content_type,
                        },
                    )
                )
                chunk.embedding_id = str(chunk.id)
            await vector_store.upsert_chunks(points)
            await db.commit()

    run(_impl())

    from app.tasks.style_tasks import extract_style

    extract_style.delay(media_source_id)
    return {"status": "done", "media_source_id": media_source_id}
