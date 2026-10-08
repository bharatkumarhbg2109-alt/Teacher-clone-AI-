"""In-process vector store backed by the SQL DB (no Qdrant server).

Selected when VECTOR_BACKEND=local. Brute-force cosine similarity — fine for
local dev / small teachers.
"""
import uuid

import numpy as np
from sqlalchemy import delete, select

from app.db.session import AsyncSessionLocal
from app.models.chunk_vector import ChunkVector
from app.services.vector_store import ChunkPoint, SearchResult


def _uuid(v) -> uuid.UUID:
    return v if isinstance(v, uuid.UUID) else uuid.UUID(str(v))


class LocalVectorStore:
    async def ensure_collection(self) -> None:  # table created by init_models
        return None

    async def upsert_chunks(self, chunks: list[ChunkPoint]) -> int:
        async with AsyncSessionLocal() as db:
            for c in chunks:
                p = c.payload
                cid = _uuid(c.id)
                existing = await db.get(ChunkVector, cid)
                if existing:
                    existing.embedding = c.dense_vector
                    existing.text = p.get("text", "")
                else:
                    db.add(
                        ChunkVector(
                            id=cid,
                            teacher_profile_id=_uuid(p["teacher_profile_id"]),
                            media_source_id=_uuid(p["media_source_id"]),
                            content_type=p.get("content_type", "audio"),
                            page=p.get("page"),
                            start_time=p.get("start_time"),
                            end_time=p.get("end_time"),
                            text=p.get("text", ""),
                            embedding=c.dense_vector,
                        )
                    )
            await db.commit()
        return len(chunks)

    async def hybrid_search(
        self, query_dense, query_sparse, teacher_profile_id, top_k: int = 8
    ) -> list[SearchResult]:
        async with AsyncSessionLocal() as db:
            rows = (
                (await db.execute(
                    select(ChunkVector).where(
                        ChunkVector.teacher_profile_id == _uuid(teacher_profile_id)
                    )
                )).scalars().all()
            )
        if not rows:
            return []
        q = np.asarray(query_dense, dtype=float)
        qn = np.linalg.norm(q) or 1.0
        scored = []
        for r in rows:
            v = np.asarray(r.embedding, dtype=float)
            vn = np.linalg.norm(v) or 1.0
            score = float(np.dot(q, v) / (qn * vn))
            scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            SearchResult(
                id=str(r.id),
                score=s,
                text=r.text,
                start_time=r.start_time,
                end_time=r.end_time,
                page=r.page,
                media_source_id=str(r.media_source_id),
                content_type=r.content_type,
            )
            for s, r in scored[:top_k]
        ]

    async def delete_by_media_source(self, media_source_id: str) -> None:
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(ChunkVector).where(
                    ChunkVector.media_source_id == _uuid(media_source_id)
                )
            )
            await db.commit()

    async def delete_by_teacher_profile(self, teacher_profile_id: str) -> None:
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(ChunkVector).where(
                    ChunkVector.teacher_profile_id == _uuid(teacher_profile_id)
                )
            )
            await db.commit()
