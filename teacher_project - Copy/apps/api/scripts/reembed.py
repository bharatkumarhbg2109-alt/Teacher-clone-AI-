"""Backfill embeddings for any chunks that don't have one yet.

Useful after changing EMBEDDING_PROVIDER, or if ingestion embedded nothing.
Run:  python -m scripts.reembed
"""
import asyncio
import traceback

from sqlalchemy import select

from app.db.init import init_models
from app.db.session import AsyncSessionLocal
from app.models.media_source import MediaSource
from app.models.transcript_chunk import TranscriptChunk
from app.services.embedder import embedder
from app.services.vector_store import ChunkPoint, vector_store


async def main() -> None:
    await init_models()
    await vector_store.ensure_collection()

    async with AsyncSessionLocal() as db:
        rows = (
            (await db.execute(
                select(TranscriptChunk, MediaSource)
                .join(MediaSource, TranscriptChunk.media_source_id == MediaSource.id)
                .where(TranscriptChunk.embedding_id.is_(None))
            )).all()
        )

    if not rows:
        print("Nothing to embed — all chunks already have embeddings.")
        return

    print(f"Embedding {len(rows)} chunk(s)...")
    texts = [c.text for c, _ in rows]
    vecs = await embedder.embed_texts(texts)

    points = [
        ChunkPoint(
            id=str(c.id),
            dense_vector=v,
            sparse_vector=embedder.compute_sparse_vector(c.text),
            payload={
                "text": c.text,
                "media_source_id": str(c.media_source_id),
                "teacher_profile_id": str(src.teacher_profile_id),
                "start_time": c.start_time,
                "end_time": c.end_time,
                "page": c.page,
                "chunk_index": c.chunk_index,
                "content_type": c.content_type,
            },
        )
        for (c, src), v in zip(rows, vecs)
    ]
    n = await vector_store.upsert_chunks(points)
    print(f"Upserted {n} vector(s).")

    # Mark them embedded.
    async with AsyncSessionLocal() as db:
        for c, _ in rows:
            obj = await db.get(TranscriptChunk, c.id)
            if obj:
                obj.embedding_id = str(c.id)
        await db.commit()
    print("Done.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        traceback.print_exc()
