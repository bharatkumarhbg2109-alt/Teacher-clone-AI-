"""Hybrid Retriever — Combines ChromaDB vector search with knowledge graph traversal.

Replaces ChromaDB-only RAG with a richer system that extracts concepts
from queries, expands via graph neighbors, warns about prerequisites,
and assembles a unified context for LLM generation.
"""

import asyncio
import hashlib
import json
import logging
import re
from typing import List, Optional

import chromadb
import httpx

from app.config import settings
from app.graph.graph_service import KnowledgeGraphService

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()

log = logging.getLogger("hybrid_retrieval")


class HybridQueryRequest(BaseModel):
    query: str


@router.post("/query-hybrid")
async def query_hybrid(req: HybridQueryRequest):
    """Hybrid retrieval combining ChromaDB vector search + graph expansion + prerequisites."""
    retriever = HybridRetriever()
    return await retriever.assemble_context(req.query)


import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CHROMA_PATH = os.path.join(BASE_DIR, "graph_db", "chroma")


class HybridRetriever:
    """Hybrid retrieval combining vector search + knowledge graph traversal."""

    def __init__(self):
        """Initialize ChromaDB client, knowledge graph, and Ollama config."""
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        self.collection = self.chroma_client.get_or_create_collection("documents")
        self.graph_svc = KnowledgeGraphService()
        self.graph_svc.load_graph()
        self.G = self.graph_svc.graph
        ollama_base = getattr(settings, "OLLAMA_HOST", getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"))
        self.ollama_url = f"{ollama_base.rstrip('/')}/api/generate"
        self.model = getattr(settings, "OLLAMA_MODEL", "llama3.1:8b")

    def vector_search(self, query: str, n_results: int = 5) -> List[dict]:
        """Search ChromaDB for chunks semantically similar to the query.

        Returns list of dicts with text, metadata, distance, and source="vector".
        """
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                include=["documents", "metadatas", "distances"],
            )
        except Exception as e:
            log.warning("Vector search failed: %s", e)
            return []

        if not results or not results.get("documents") or not results["documents"][0]:
            return []

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]

        return [
            {
                "text": doc,
                "metadata": meta,
                "distance": dist,
                "source": "vector",
            }
            for doc, meta, dist in zip(docs, metas, dists)
        ]

    async def extract_query_concepts(self, query: str) -> List[str]:
        """Use Ollama to extract 2-3 key educational concepts from a query.

        Only returns concepts that exist as nodes in the knowledge graph.
        """
        prompt = (
            f"Extract 2-3 key educational concepts from this question. "
            f"Return ONLY a JSON array of strings.\n"
            f"Question: {query}\n"
            f'Example response: ["Newton\'s Laws", "Force", "Acceleration"]\n'
            f"Response:"
        )

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    self.ollama_url,
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.0, "num_predict": 100},
                    },
                )
                response.raise_for_status()
                raw = response.json().get("response", "")

                # Parse JSON array from response
                cleaned = raw.strip()
                cleaned = cleaned.removeprefix("```json").removesuffix("```").strip()

                # Find array in response
                first_bracket = cleaned.find("[")
                last_bracket = cleaned.rfind("]")
                if first_bracket != -1 and last_bracket > first_bracket:
                    concepts_list = json.loads(cleaned[first_bracket : last_bracket + 1])

                    # Normalize and filter to concepts in graph
                    matched = []
                    for c in concepts_list:
                        if isinstance(c, str):
                            normalized = self.graph_svc._normalize_name(c)
                            if normalized in self.G.nodes:
                                matched.append(c)
                    return matched

        except Exception as e:
            log.warning("Concept extraction failed: %s", e)

        return []

    def graph_expand(self, concept_names: List[str], depth: int = 2) -> List[dict]:
        """Expand query concepts via knowledge graph neighbors into additional chunks.

        For each concept, finds graph neighbors, then searches ChromaDB
        for chunks mentioning those neighbors. Returns up to 5 unique chunks.
        """
        if not concept_names or self.G.number_of_nodes() == 0:
            return []

        # Collect all neighbor names from graph
        neighbor_names = set()
        for concept in concept_names:
            result = self.graph_svc.get_concept_neighbors(concept, depth=depth)
            for n in result.get("neighbors", []):
                neighbor_names.add(n["name"].lower())

        if not neighbor_names:
            return []

        # Search ChromaDB for chunks mentioning these neighbors
        # Get all chunks and filter in Python for content matching
        try:
            all_chunks = self.collection.get(
                include=["documents", "metadatas"],
            )
        except Exception as e:
            log.warning("ChromaDB get failed for graph expansion: %s", e)
            return []

        if not all_chunks or not all_chunks.get("documents"):
            return []

        expanded = []
        seen_hashes = set()

        for doc, meta in zip(all_chunks["documents"], all_chunks["metadatas"]):
            doc_lower = doc.lower()
            # Check if any neighbor concept is mentioned in the chunk
            for neighbor in neighbor_names:
                if neighbor in doc_lower:
                    h = hashlib.md5(doc.encode()).hexdigest()
                    if h not in seen_hashes:
                        seen_hashes.add(h)
                        expanded.append({
                            "text": doc,
                            "metadata": meta,
                            "distance": None,
                            "source": "graph",
                        })
                    break

            if len(expanded) >= 5:
                break

        return expanded[:5]

    def get_prerequisite_warning(self, concept_names: List[str]) -> Optional[str]:
        """Check if query concepts have unmet prerequisites.

        Returns a formatted warning string if prerequisites exist,
        or None if no prerequisites are found.
        """
        if not concept_names:
            return None

        all_prereqs = []
        for concept in concept_names:
            chain = self.graph_svc.get_prerequisite_chain(concept)
            all_prereqs.extend(chain)

        # Deduplicate while preserving order
        seen = set()
        unique_prereqs = []
        for p in all_prereqs:
            if p not in seen:
                seen.add(p)
                unique_prereqs.append(p)

        if not unique_prereqs:
            return None

        prereq_list = ", ".join(unique_prereqs)
        return f"📚 Prerequisite Topics: {prereq_list}"

    async def assemble_context(self, query: str) -> dict:
        """Full hybrid retrieval pipeline: vector search + graph expansion + prerequisites.

        Returns a dict with primary_chunks, graph_chunks, all_chunks,
        query_concepts, concept_map, prerequisite_warning, and context_text.
        """
        # Step 1: Vector search
        primary_chunks = self.vector_search(query, n_results=5)

        # Step 2: Extract concepts and expand via graph
        query_concepts = await self.extract_query_concepts(query)
        graph_chunks = self.graph_expand(query_concepts, depth=2)

        # Step 3: Prerequisite warning
        prereq_warning = self.get_prerequisite_warning(query_concepts)

        # Step 4: Merge and deduplicate
        all_chunks_raw = primary_chunks + graph_chunks
        seen_hashes = set()
        unique_chunks = []
        for chunk in all_chunks_raw:
            h = hashlib.md5(chunk["text"].encode()).hexdigest()
            if h not in seen_hashes:
                seen_hashes.add(h)
                unique_chunks.append(chunk)

        # Step 5: Build concept map (concept → neighbors)
        concept_map = {}
        for c in query_concepts:
            result = self.graph_svc.get_concept_neighbors(c)
            concept_map[c] = [n["name"] for n in result.get("neighbors", [])]

        # Step 6: Assemble context text
        top_chunks = unique_chunks[:8]
        context_text = "\n\n".join([c["text"] for c in top_chunks])

        return {
            "primary_chunks": primary_chunks,
            "graph_chunks": graph_chunks,
            "all_chunks": top_chunks,
            "query_concepts": query_concepts,
            "concept_map": concept_map,
            "prerequisite_warning": prereq_warning,
            "context_text": context_text,
        }
