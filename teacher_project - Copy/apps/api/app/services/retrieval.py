"""Hybrid retrieval + context formatting for the teaching prompt."""
from app.services.embedder import embedder
from app.services.vector_store import SearchResult, vector_store


async def retrieve_context(
    query: str, teacher_profile_id: str, top_k: int = 8
) -> list[SearchResult]:
    dense = await embedder.embed_single(query)
    sparse = embedder.compute_sparse_vector(query)
    return await vector_store.hybrid_search(dense, sparse, teacher_profile_id, top_k)


def _locator(r: SearchResult) -> str:
    if r.page is not None:
        return f"p.{r.page}"
    if r.start_time is not None:
        m, s = int(r.start_time // 60), int(r.start_time % 60)
        return f"{m}:{s:02d}"
    return "?"


def format_context_chunks(results: list[SearchResult]) -> str:
    if not results:
        return "(No relevant content found in the knowledge base)"
    lines = []
    for i, r in enumerate(results, 1):
        tag = "VISUAL " if r.content_type == "visual" else ""
        lines.append(f"[{i}] ({_locator(r)}) {tag}— {r.text.strip()}")
    return "\n".join(lines)
