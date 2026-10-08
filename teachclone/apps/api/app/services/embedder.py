"""Embeddings — dense (OpenAI or local) + a lightweight sparse vector for
hybrid keyword search. Provider is chosen by EMBEDDING_PROVIDER.

Note: if you switch to the local provider (e.g. BGE, dim 1024), set
EMBEDDING_DIM to match and recreate the Qdrant collection.
"""
import numpy as np

from app.config import settings

_openai_client = None
_local_model = None


def _openai():
    global _openai_client
    if _openai_client is None:
        from openai import AsyncOpenAI

        _openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    return _openai_client


class Embedder:
    BATCH = 100

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if settings.EMBEDDING_PROVIDER == "hash":
            return [self._embed_hash(t) for t in texts]
        if settings.EMBEDDING_PROVIDER == "local":
            return self._embed_local(texts)
        return await self._embed_openai(texts)

    def _embed_hash(self, text: str) -> list[float]:
        """Deterministic, dependency-free embedding (bag-of-hashed-tokens).

        Low quality vs. real embeddings, but lets local mode do RAG with only
        an Anthropic key — no embedding API needed.
        """
        import hashlib

        dim = settings.EMBEDDING_DIM
        v = np.zeros(dim, dtype=float)
        for tok in text.lower().split():
            tok = tok.strip(".,!?;:\"'()[]{}")
            if not tok:
                continue
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            v[h % dim] += 1.0
        n = np.linalg.norm(v)
        if n > 0:
            v = v / n
        return v.tolist()

    async def embed_single(self, text: str) -> list[float]:
        return (await self.embed_texts([text]))[0]

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        client = _openai()
        for i in range(0, len(texts), self.BATCH):
            batch = [t.replace("\n", " ").strip() or " " for t in texts[i : i + self.BATCH]]
            resp = await client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=batch,
                dimensions=settings.EMBEDDING_DIM,
            )
            out.extend(item.embedding for item in resp.data)
        return out

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        global _local_model
        if _local_model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "EMBEDDING_PROVIDER=local requires `pip install sentence-transformers`"
                ) from exc
            _local_model = SentenceTransformer(settings.LOCAL_EMBEDDING_MODEL)
        vecs = _local_model.encode(texts, normalize_embeddings=True)
        return [v.tolist() for v in vecs]

    def compute_sparse_vector(self, text: str) -> dict[int, float]:
        """TF-weighted sparse vector (BM25-ish) for keyword matching."""
        words = text.lower().split()
        freq: dict[str, int] = {}
        for w in words:
            w = w.strip(".,!?;:\"'()[]{}")
            if len(w) > 2:
                freq[w] = freq.get(w, 0) + 1
        total = max(len(words), 1)
        result: dict[int, float] = {}
        for word, count in freq.items():
            idx = abs(hash(word)) % 100_000
            tf = count / total
            result[idx] = round(tf * (1 + np.log(count + 1)), 4)
        return result


embedder = Embedder()
