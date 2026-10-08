from app.config import settings
from app.services.embedder import embedder
from app.services.vector_store import SearchResult, vector_store


async def retrieve_context(
    query: str,
    teacher_profile_id: str,
    top_k: int = 8,
    min_score: float | None = None,
) -> list[SearchResult]:
    """Retrieve top-k relevant chunks with score threshold to prevent noise."""
    dense = await embedder.embed_single(query)
    sparse = embedder.compute_sparse_vector(query)
    results = await vector_store.hybrid_search(dense, sparse, teacher_profile_id, top_k)
    threshold = min_score if min_score is not None else getattr(settings, "RAG_MIN_SCORE", 0.01)
    return [r for r in results if r.score >= threshold][:top_k]


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
