"""Qdrant vector store — hybrid dense + sparse search, isolated per teacher.

Sharing a teacher = granting a learner's session query access to that teacher's
``teacher_profile_id`` namespace; search always filters by that id so knowledge
never leaks between teachers.
"""
from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HnswConfigDiff,
    MatchValue,
    OptimizersConfigDiff,
    PointStruct,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from app.config import settings


@dataclass
class ChunkPoint:
    id: str
    dense_vector: list[float]
    sparse_vector: dict[int, float]
    payload: dict


@dataclass
class SearchResult:
    id: str
    score: float
    text: str
    start_time: float | None
    end_time: float | None
    page: int | None
    media_source_id: str
    content_type: str


class VectorStore:
    COLLECTION = settings.QDRANT_COLLECTION
    DIM = settings.EMBEDDING_DIM

    def __init__(self) -> None:
        self.client = AsyncQdrantClient(url=settings.QDRANT_URL)

    async def ensure_collection(self) -> None:
        existing = [c.name for c in (await self.client.get_collections()).collections]
        if self.COLLECTION in existing:
            return
        await self.client.create_collection(
            collection_name=self.COLLECTION,
            vectors_config={"dense": VectorParams(size=self.DIM, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams()},
            hnsw_config=HnswConfigDiff(m=16, ef_construct=100),
            optimizers_config=OptimizersConfigDiff(indexing_threshold=20000),
        )
        for field in ["teacher_profile_id", "media_source_id", "content_type"]:
            await self.client.create_payload_index(self.COLLECTION, field, "keyword")

    async def upsert_chunks(self, chunks: list[ChunkPoint]) -> int:
        BATCH = 100
        total = 0
        for i in range(0, len(chunks), BATCH):
            batch = chunks[i : i + BATCH]
            points = [
                PointStruct(
                    id=c.id,
                    vector={
                        "dense": c.dense_vector,
                        "sparse": SparseVector(
                            indices=list(c.sparse_vector.keys()),
                            values=list(c.sparse_vector.values()),
                        ),
                    },
                    payload=c.payload,
                )
                for c in batch
            ]
            await self.client.upsert(collection_name=self.COLLECTION, points=points)
            total += len(points)
        return total

    async def hybrid_search(
        self,
        query_dense: list[float],
        query_sparse: dict[int, float],
        teacher_profile_id: str,
        top_k: int = 8,
    ) -> list[SearchResult]:
        filt = Filter(
            must=[
                FieldCondition(
                    key="teacher_profile_id", match=MatchValue(value=teacher_profile_id)
                )
            ]
        )
        dense_res = await self.client.search(
            self.COLLECTION,
            query_vector=("dense", query_dense),
            query_filter=filt,
            limit=top_k * 2,
        )
        sparse_res = await self.client.search(
            self.COLLECTION,
            query_vector=(
                "sparse",
                SparseVector(
                    indices=list(query_sparse.keys()),
                    values=list(query_sparse.values()),
                ),
            ),
            query_filter=filt,
            limit=top_k * 2,
        )
        # Reciprocal Rank Fusion (k=60).
        scores: dict[str, float] = {}
        for rank, hit in enumerate(dense_res):
            scores[str(hit.id)] = scores.get(str(hit.id), 0) + 1 / (61 + rank)
        for rank, hit in enumerate(sparse_res):
            scores[str(hit.id)] = scores.get(str(hit.id), 0) + 1 / (61 + rank)
        all_hits = {str(h.id): h for h in list(dense_res) + list(sparse_res)}
        top_ids = sorted(scores, key=scores.__getitem__, reverse=True)[:top_k]

        results: list[SearchResult] = []
        for pid in top_ids:
            h = all_hits.get(pid)
            if not h:
                continue
            p = h.payload or {}
            results.append(
                SearchResult(
                    id=pid,
                    score=scores[pid],
                    text=p.get("text", ""),
                    start_time=p.get("start_time"),
                    end_time=p.get("end_time"),
                    page=p.get("page"),
                    media_source_id=p.get("media_source_id", ""),
                    content_type=p.get("content_type", "audio"),
                )
            )
        return results

    async def delete_by_media_source(self, media_source_id: str) -> None:
        await self.client.delete(
            self.COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="media_source_id", match=MatchValue(value=media_source_id)
                    )
                ]
            ),
        )

    async def delete_by_teacher_profile(self, teacher_profile_id: str) -> None:
        await self.client.delete(
            self.COLLECTION,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="teacher_profile_id",
                        match=MatchValue(value=teacher_profile_id),
                    )
                ]
            ),
        )


if settings.VECTOR_BACKEND == "local":
    from app.services.vector_store_local import LocalVectorStore

    vector_store = LocalVectorStore()
else:
    vector_store = VectorStore()
