"""Concept Extractor — LLM-powered concept & relationship extraction from ChromaDB chunks.

Uses local Ollama (llama3.1:8b) to extract structured educational concepts
and their relationships from text chunks, storing results in SQLite for
subsequent graph construction.
"""

import asyncio
import json
import logging
import os
import re
import sqlite3
import time
from typing import Optional

import chromadb
import httpx

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings

router = APIRouter()

log = logging.getLogger("concept_extractor")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "graph_db", "ingestor.db")
CHROMA_PATH = os.path.join(BASE_DIR, "graph_db", "chroma")


class ExtractConceptsRequest(BaseModel):
    batch_size: int = 5
    max_chunks: Optional[int] = None
    merge_duplicates: bool = True


@router.post("/extract-concepts")
async def extract_concepts(req: Optional[ExtractConceptsRequest] = None):
    """Extract concepts and relationships from text chunks via Ollama LLM."""
    try:
        extractor = ConceptExtractor()
        if extractor.collection.count() == 0:
            return {
                "error": "No documents found",
                "hint": "Pehle /upload-bulk chalao",
                "concepts_extracted": 0,
                "relationships": 0,
            }
        batch_size = req.batch_size if req else 5
        max_chunks = req.max_chunks if req else None
        result = await extractor.process_all_chunks(batch_size=batch_size, max_chunks=max_chunks)
        if not req or req.merge_duplicates:
            extractor.merge_duplicate_concepts()
        return result
    except Exception as e:
        log.error(f"Extract concepts error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class ConceptExtractor:
    """Extract educational concepts and relationships from text chunks via Ollama LLM."""

    def __init__(self):
        """Initialize Ollama client, ChromaDB collection, and SQLite tables."""
        ollama_base = getattr(settings, "OLLAMA_HOST", getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434"))
        self.ollama_url = f"{ollama_base.rstrip('/')}/api/generate"
        self.model = getattr(settings, "OLLAMA_MODEL", "llama3.1:8b")
        self.db_path = DB_PATH
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        self.collection = self.chroma_client.get_or_create_collection("documents")
        self.init_sqlite_tables()

    def init_sqlite_tables(self):
        """Create SQLite tables for concepts, relationships, and extraction log."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS concepts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                type TEXT CHECK(type IN ('topic','subtopic','concept')),
                source_pdf TEXT,
                chunk_id TEXT,
                importance_score REAL DEFAULT 1.0,
                mention_count INTEGER DEFAULT 1
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_concept TEXT NOT NULL,
                target_concept TEXT NOT NULL,
                relation_type TEXT CHECK(relation_type IN
                    ('prerequisite','related','part_of','example_of','contrasts_with')),
                weight REAL DEFAULT 0.5,
                source_chunk_id TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS extraction_log (
                chunk_id TEXT PRIMARY KEY,
                status TEXT,
                concepts_found INTEGER,
                relations_found INTEGER,
                timestamp TEXT
            )
        """)
        conn.commit()
        conn.close()

    def normalize_name(self, name: str) -> str:
        """Normalize a concept name: lowercase, depluralize, collapse whitespace."""
        name = name.strip().lower()
        # Basic depluralize: remove trailing 's' if word > 4 chars
        if len(name) > 4 and name.endswith("s") and not name.endswith("ss"):
            name = name[:-1]
        # Collapse multiple spaces
        name = re.sub(r"\s+", " ", name)
        return name

    def build_prompt(self, chunk_text: str) -> str:
        """Build the extraction prompt for the LLM."""
        return f"""You are an educational knowledge extractor. Extract structured information from the given educational text.

RULES:
- Only extract concepts actually present in the text
- Concepts must be meaningful educational terms (not common words like "the", "is", "and")
- Minimum 2 concepts, maximum 15 concepts per chunk
- Relationships must connect two concepts from your extracted list
- importance score: 1-3 for basic facts, 4-6 for core concepts, 7-10 for fundamental topics
- Respond ONLY with valid JSON, no explanation, no markdown

TEXT:
{chunk_text}

Respond in this exact JSON format:
{{
  "concepts": [
    {{"name": "concept name", "type": "topic", "importance": 7}},
    {{"name": "another concept", "type": "concept", "importance": 4}}
  ],
  "relationships": [
    {{"from": "concept name", "to": "another concept", "type": "prerequisite", "weight": 0.8}}
  ]
}}"""

    async def call_ollama(self, prompt: str) -> Optional[str]:
        """Send a prompt to Ollama and return the response text.

        Returns None on timeout or connection error.
        """
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 800,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(self.ollama_url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except (httpx.ConnectError, httpx.TimeoutException, Exception) as e:
            log.warning("Ollama call failed: %s", e)
            return None

    def parse_llm_response(
        self, response: str, chunk_id: str, pdf_name: str
    ) -> dict:
        """Parse the LLM's JSON response, with fallback recovery for malformed output."""
        if not response:
            return {"concepts": [], "relationships": [], "parse_error": True}

        # Strip whitespace and markdown code fences
        cleaned = response.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = cleaned.strip()

        # Try direct JSON parse
        try:
            parsed = json.loads(cleaned)
            if "concepts" in parsed and "relationships" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass

        # Fallback: find first { and last } and extract substring
        try:
            first_brace = cleaned.find("{")
            last_brace = cleaned.rfind("}")
            if first_brace != -1 and last_brace > first_brace:
                substring = cleaned[first_brace : last_brace + 1]
                parsed = json.loads(substring)
                if "concepts" in parsed and "relationships" in parsed:
                    return parsed
        except (json.JSONDecodeError, ValueError):
            pass

        return {"concepts": [], "relationships": [], "parse_error": True}

    def save_extraction(self, parsed: dict, chunk_id: str, pdf_name: str):
        """Save extracted concepts and relationships to SQLite.

        Updates mention counts for existing concepts, inserts new ones,
        and logs the extraction result.
        """
        ALLOWED_RELATIONS = {"prerequisite", "related", "part_of", "example_of", "contrasts_with"}
        ALLOWED_TYPES = {"topic", "subtopic", "concept"}

        concepts_found = 0
        relations_found = 0

        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")

            # Save concepts
            for concept in parsed.get("concepts", []):
                name = concept.get("name", "")
                if not name:
                    continue

                normalized = self.normalize_name(name)
                raw_type = str(concept.get("type", "concept")).lower().strip()
                concept_type = raw_type if raw_type in ALLOWED_TYPES else "concept"
                importance = concept.get("importance", 1.0)

                # Check if concept already exists
                existing = conn.execute(
                    "SELECT id, importance_score FROM concepts WHERE normalized_name = ?",
                    (normalized,),
                ).fetchone()

                if existing:
                    # Update: increment mention count, keep higher importance
                    conn.execute(
                        """UPDATE concepts
                           SET mention_count = mention_count + 1,
                               importance_score = MAX(importance_score, ?)
                           WHERE id = ?""",
                        (importance, existing[0]),
                    )
                else:
                    # Insert new concept
                    conn.execute(
                        """INSERT INTO concepts
                           (name, normalized_name, type, source_pdf, chunk_id,
                            importance_score, mention_count)
                           VALUES (?, ?, ?, ?, ?, ?, 1)""",
                        (name, normalized, concept_type, pdf_name, chunk_id, importance),
                    )
                concepts_found += 1

            # Save relationships
            for rel in parsed.get("relationships", []):
                source = rel.get("from", "")
                target = rel.get("to", "")
                raw_rel = str(rel.get("type", "related")).lower().strip()
                rel_type = raw_rel if raw_rel in ALLOWED_RELATIONS else "related"
                weight = rel.get("weight", 0.5)

                if not source or not target:
                    continue

                source_norm = self.normalize_name(source)
                target_norm = self.normalize_name(target)

                # Both concepts must exist in the concepts table
                src_exists = conn.execute(
                    "SELECT 1 FROM concepts WHERE normalized_name = ?",
                    (source_norm,),
                ).fetchone()
                tgt_exists = conn.execute(
                    "SELECT 1 FROM concepts WHERE normalized_name = ?",
                    (target_norm,),
                ).fetchone()

                if src_exists and tgt_exists:
                    # Check for duplicate relationship
                    dup = conn.execute(
                        """SELECT 1 FROM relationships
                           WHERE source_concept = ? AND target_concept = ?
                           AND relation_type = ?""",
                        (source_norm, target_norm, rel_type),
                    ).fetchone()

                    if not dup:
                        conn.execute(
                            """INSERT INTO relationships
                               (source_concept, target_concept, relation_type,
                                weight, source_chunk_id)
                               VALUES (?, ?, ?, ?, ?)""",
                            (source_norm, target_norm, rel_type, weight, chunk_id),
                        )
                        relations_found += 1

            # Log extraction
            conn.execute(
                """INSERT OR REPLACE INTO extraction_log
                   (chunk_id, status, concepts_found, relations_found, timestamp)
                   VALUES (?, ?, ?, ?, datetime('now'))""",
                (chunk_id, "success", concepts_found, relations_found),
            )
            conn.commit()

    async def process_all_chunks(
        self, batch_size: int = 5, max_chunks: Optional[int] = None
    ) -> dict:
        """Process all unprocessed chunks in ChromaDB through the LLM pipeline.

        Skips chunks already in extraction_log. Processes in batches with
        0.5s delay between calls to avoid overloading Ollama.
        """
        # Fetch all chunks from ChromaDB
        result = self.collection.get(include=["documents", "metadatas"])
        all_ids = result["ids"]
        all_docs = result["documents"]
        all_metas = result["metadatas"]

        if not all_ids:
            return {
                "total_chunks": 0,
                "processed": 0,
                "skipped": 0,
                "total_concepts": 0,
                "concepts_extracted": 0,
                "total_relationships": 0,
                "relationships": 0,
                "errors": 0,
            }

        # Get already-processed chunk IDs
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            processed_rows = conn.execute("SELECT chunk_id FROM extraction_log").fetchall()
            processed_ids = {row[0] for row in processed_rows}

        # Filter unprocessed chunks
        pending = []
        for i, chunk_id in enumerate(all_ids):
            if chunk_id not in processed_ids:
                pending.append((chunk_id, all_docs[i], all_metas[i]))

        if max_chunks is not None and max_chunks > 0:
            pending = pending[:max_chunks]

        skipped = len(all_ids) - len(pending)
        total_concepts = 0
        total_relations = 0
        errors = 0

        # Process in batches
        for batch_start in range(0, len(pending), batch_size):
            batch = pending[batch_start : batch_start + batch_size]

            for idx, (chunk_id, doc_text, meta) in enumerate(batch):
                global_idx = batch_start + idx + 1
                pdf_name = meta.get("pdf_name", "unknown") if meta else "unknown"

                # Truncate long chunks
                truncated_text = doc_text[:1200] if len(doc_text) > 1200 else doc_text

                # Build prompt and call Ollama
                prompt = self.build_prompt(truncated_text)
                response = await self.call_ollama(prompt)

                if response is None:
                    errors += 1
                    # Log the failure
                    with sqlite3.connect(self.db_path, timeout=30.0) as conn:
                        conn.execute("PRAGMA journal_mode=WAL")
                        conn.execute(
                            """INSERT OR REPLACE INTO extraction_log
                               (chunk_id, status, concepts_found, relations_found, timestamp)
                               VALUES (?, 'error', 0, 0, datetime('now'))""",
                            (chunk_id,),
                        )
                        conn.commit()
                    print(
                        f"Extracted {global_idx}/{len(pending)} — ERROR: Ollama returned None"
                    )
                    continue

                # Parse and save
                parsed = self.parse_llm_response(response, chunk_id, pdf_name)
                self.save_extraction(parsed, chunk_id, pdf_name)

                n_concepts = len(parsed.get("concepts", []))
                n_relations = len(parsed.get("relationships", []))
                total_concepts += n_concepts
                total_relations += n_relations

                print(
                    f"Extracted {global_idx}/{len(pending)} — "
                    f"concepts: {n_concepts}, relations: {n_relations}"
                )

                # Rate-limit: 0.5s between calls
                await asyncio.sleep(0.5)

        return {
            "total_chunks": len(all_ids),
            "processed": len(pending),
            "skipped": skipped,
            "total_concepts": total_concepts,
            "concepts_extracted": total_concepts,
            "total_relationships": total_relations,
            "relationships": total_relations,
            "errors": errors,
        }

    def merge_duplicate_concepts(self):
        """Merge concepts sharing the same normalized_name.

        Keeps the one with highest importance_score, updates all
        relationships to point to the keeper, deletes the rest.
        """
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")

            # Find duplicate groups
            dupes = conn.execute(
                """SELECT normalized_name, COUNT(*) as cnt
                   FROM concepts
                   GROUP BY normalized_name
                   HAVING cnt > 1"""
            ).fetchall()

            total_merged = 0

            for norm_name, count in dupes:
                # Get all rows for this normalized name, sorted by importance
                rows = conn.execute(
                    """SELECT id, name, importance_score
                       FROM concepts
                       WHERE normalized_name = ?
                       ORDER BY importance_score DESC""",
                    (norm_name,),
                ).fetchall()

                if len(rows) <= 1:
                    continue

                keeper_id = rows[0][0]
                keeper_name = rows[0][1]
                duplicate_ids = [r[0] for r in rows[1:]]
                duplicate_names = [r[1] for r in rows[1:]]

                # Update relationships pointing to duplicates → point to keeper
                for dup_name in duplicate_names:
                    dup_norm = self.normalize_name(dup_name)
                    conn.execute(
                        """UPDATE relationships
                           SET source_concept = ?
                           WHERE source_concept = ?""",
                        (norm_name, dup_norm),
                    )
                    conn.execute(
                        """UPDATE relationships
                           SET target_concept = ?
                           WHERE target_concept = ?""",
                        (norm_name, dup_norm),
                    )

                # Delete duplicate concept rows
                for dup_id in duplicate_ids:
                    conn.execute("DELETE FROM concepts WHERE id = ?", (dup_id,))
                    total_merged += 1

            # Clean up self-referencing relationships
            conn.execute(
                """DELETE FROM relationships
                   WHERE source_concept = target_concept"""
            )
            conn.commit()

        if total_merged > 0:
            print(f"Merged {total_merged} duplicate concepts")
        else:
            print("No duplicate concepts to merge")
