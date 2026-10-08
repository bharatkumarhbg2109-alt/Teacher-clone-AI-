"""Bulk PDF Ingestor — Parallel PDF processing pipeline with ChromaDB storage.

Processes 1000+ PDFs in parallel, chunks them smartly, deduplicates via
SQLite, and stores to ChromaDB with rich metadata.
"""

import asyncio
import concurrent.futures
import glob
import hashlib
import logging
import os
import sqlite3
import time
from pathlib import Path
from typing import List, Optional

import chromadb
import fitz  # PyMuPDF

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

log = logging.getLogger("bulk_ingestor")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "graph_db", "ingestor.db")
CHROMA_PATH = os.path.join(BASE_DIR, "graph_db", "chroma")


class BulkUploadRequest(BaseModel):
    folder_path: Optional[str] = None


@router.post("/upload-bulk")
async def upload_bulk(req: Optional[BulkUploadRequest] = None):
    """Process all PDFs in folder_path in parallel and store in ChromaDB."""
    try:
        path = req.folder_path if req and req.folder_path else None
        if not path:
            default_sources = os.path.join(BASE_DIR, "uploads", "sources")
            default_pdfs = os.path.join(BASE_DIR, "uploads", "pdfs")
            path = default_sources if os.path.exists(default_sources) else default_pdfs

        if not os.path.exists(path):
            return {
                "error": f"Path does not exist: {path}",
                "processed": 0,
                "chunks_added": 0,
            }

        pdf_files = glob.glob(os.path.join(path, "*.pdf")) + glob.glob(os.path.join(path, "**", "*.pdf"), recursive=True)
        pdf_files = list(set(pdf_files))
        if not pdf_files:
            return {
                "error": "No PDFs found in path",
                "path": path,
                "processed": 0,
                "chunks_added": 0,
            }

        ingestor = BulkIngestor()
        summary = await ingestor.process_pdf_folder(path)
        return summary
    except Exception as e:
        log.error(f"Upload bulk error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class BulkIngestor:
    """Production-ready bulk PDF ingestion pipeline."""

    def __init__(self):
        """Initialize ChromaDB client, collection, and SQLite DB."""
        self.chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)
        self.collection = self.chroma_client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
        self.db_path = DB_PATH
        self.init_sqlite()

    def init_sqlite(self):
        """Create SQLite table for deduplication tracking."""
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chunk_hash TEXT UNIQUE,
                    pdf_name TEXT,
                    chunk_index INTEGER,
                    timestamp TEXT,
                    char_count INTEGER
                )
            """)
            conn.commit()

    def extract_text_with_metadata(self, pdf_path: str) -> List[dict]:
        """Extract text from each PDF page with section header detection.

        Returns list of page dicts with text, page_num, pdf_name,
        section_header, and char_count. Skips blank/image pages (< 50 chars).
        """
        pdf_name = os.path.basename(pdf_path)
        pages = []

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            log.error("Failed to open PDF %s: %s", pdf_path, e)
            return []

        detected_header = None

        for page_num in range(len(doc)):
            try:
                page = doc[page_num]
                text = page.get_text("text")
                char_count = len(text)

                # Skip blank / image-only pages
                if char_count < 50:
                    continue

                # Detect section headers from the extracted text
                for line in text.split("\n"):
                    line = line.strip()
                    if not line:
                        continue
                    if (len(line) < 80) and (
                        line.isupper() or (
                            line.endswith(":") and len(line.split()) < 8
                        )
                    ):
                        detected_header = line
                        break

                pages.append(
                    {
                        "text": text,
                        "page_num": page_num + 1,  # 1-indexed
                        "pdf_name": pdf_name,
                        "section_header": detected_header,
                        "char_count": char_count,
                    }
                )
            except Exception as e:
                log.warning(
                    "Page %d in %s extraction failed: %s", page_num + 1, pdf_name, e
                )
                continue

        doc.close()
        return pages

    def semantic_chunk(self, pages: List[dict]) -> List[dict]:
        """Split pages into overlapping chunks at paragraph boundaries.

        Target chunk size: 1500 chars. Minimum: 200 chars (merged with next).
        Overlap: last 150 chars of previous chunk prepended to next.
        """
        if not pages:
            return []

        # Join all pages, tracking source metadata for each character block
        paragraphs = []
        for page in pages:
            for para in page["text"].split("\n\n"):
                para = para.strip()
                if para:
                    paragraphs.append(
                        {
                            "text": para,
                            "page_num": page["page_num"],
                            "pdf_name": page["pdf_name"],
                            "section_header": page["section_header"],
                        }
                    )

        if not paragraphs:
            return []

        TARGET_SIZE = 1500
        MIN_SIZE = 200
        OVERLAP = 150

        chunks = []
        current_text = ""
        current_page_num = paragraphs[0]["page_num"]
        current_pdf_name = paragraphs[0]["pdf_name"]
        current_section = paragraphs[0]["section_header"]

        for para in paragraphs:
            candidate = (current_text + "\n\n" + para["text"]).strip() if current_text else para["text"]

            if len(candidate) <= TARGET_SIZE:
                current_text = candidate
                current_page_num = para["page_num"]
                current_pdf_name = para["pdf_name"]
                current_section = para["section_header"] or current_section
            else:
                # Flush current chunk if non-empty
                if current_text:
                    chunks.append(
                        {
                            "chunk_text": current_text,
                            "page_num": current_page_num,
                            "pdf_name": current_pdf_name,
                            "section_header": current_section,
                        }
                    )

                # Start new chunk with overlap from end of previous
                if current_text and OVERLAP > 0:
                    overlap_text = current_text[-OVERLAP:]
                    current_text = overlap_text + "\n\n" + para["text"]
                else:
                    current_text = para["text"]

                current_page_num = para["page_num"]
                current_pdf_name = para["pdf_name"]
                current_section = para["section_header"] or current_section

        # Flush the last chunk
        if current_text:
            chunks.append(
                {
                    "chunk_text": current_text,
                    "page_num": current_page_num,
                    "pdf_name": current_pdf_name,
                    "section_header": current_section,
                }
            )

        # Merge tiny chunks (< MIN_SIZE) with next, then assign index + hash
        merged = []
        for i, chunk in enumerate(chunks):
            if merged and len(merged[-1]["chunk_text"]) < MIN_SIZE:
                merged[-1]["chunk_text"] += "\n\n" + chunk["chunk_text"]
                # Keep the earliest page_num and the latest section_header
                merged[-1]["section_header"] = chunk["section_header"] or merged[-1]["section_header"]
            else:
                merged.append(chunk)

        # Add chunk_index and chunk_hash
        for i, chunk in enumerate(merged):
            chunk["chunk_index"] = i
            chunk["chunk_hash"] = hashlib.md5(
                chunk["chunk_text"].encode()
            ).hexdigest()

        return merged

    def deduplicate(self, chunks: List[dict]) -> List[dict]:
        """Filter out chunks already seen (by hash) in SQLite."""
        if not chunks:
            return []

        unique_chunks = []
        skipped = 0

        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL")

            for chunk in chunks:
                cursor = conn.execute(
                    "SELECT 1 FROM processed_chunks WHERE chunk_hash = ?",
                    (chunk["chunk_hash"],),
                )
                if cursor.fetchone():
                    skipped += 1
                    continue

                # New chunk — record it immediately
                conn.execute(
                    """INSERT INTO processed_chunks
                       (chunk_hash, pdf_name, chunk_index, timestamp, char_count)
                       VALUES (?, ?, ?, datetime('now'), ?)""",
                    (
                        chunk["chunk_hash"],
                        chunk["pdf_name"],
                        chunk["chunk_index"],
                        len(chunk["chunk_text"]),
                    ),
                )
                unique_chunks.append(chunk)

            conn.commit()

        total = len(chunks)
        kept = len(unique_chunks)
        print(f"Deduplication: kept {kept} / total {total} chunks")

        return unique_chunks

    def store_to_chromadb(self, chunks: List[dict]) -> int:
        """Store chunks into ChromaDB in batches of 50."""
        if not chunks:
            return 0

        BATCH_SIZE = 50
        stored = 0

        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            ids = [f"{c['pdf_name']}_{c['chunk_index']}" for c in batch]
            documents = [c["chunk_text"] for c in batch]
            metadatas = [
                {
                    "pdf_name": c["pdf_name"],
                    "page_num": c["page_num"],
                    "section_header": c["section_header"] or "unknown",
                    "chunk_index": c["chunk_index"],
                }
                for c in batch
            ]

            try:
                self.collection.add(
                    ids=ids, documents=documents, metadatas=metadatas
                )
                stored += len(batch)
            except Exception as e:
                # Handle DuplicateIDError — skip duplicate IDs individually
                log.warning("Batch insert error, falling back to per-chunk: %s", e)
                for j, c in enumerate(batch):
                    try:
                        self.collection.add(
                            ids=[ids[j]],
                            documents=[documents[j]],
                            metadatas=[metadatas[j]],
                        )
                        stored += 1
                    except Exception:
                        log.debug("Skipping duplicate chunk %s", ids[j])
                        continue

        return stored

    def process_single_pdf(self, pdf_path: str) -> dict:
        """Full pipeline for a single PDF: extract → chunk → dedup → store."""
        pdf_name = os.path.basename(pdf_path)
        try:
            pages = self.extract_text_with_metadata(pdf_path)
            if not pages:
                return {
                    "pdf_name": pdf_name,
                    "chunks_stored": 0,
                    "duplicates_skipped": 0,
                    "status": "ok",
                }

            all_chunks = self.semantic_chunk(pages)
            total_before = len(all_chunks)
            unique_chunks = self.deduplicate(all_chunks)
            duplicates_skipped = total_before - len(unique_chunks)

            stored = self.store_to_chromadb(unique_chunks)

            return {
                "pdf_name": pdf_name,
                "chunks_stored": stored,
                "duplicates_skipped": duplicates_skipped,
                "status": "ok",
            }
        except Exception as e:
            log.error("Failed to process %s: %s", pdf_path, e)
            return {
                "pdf_name": pdf_name,
                "chunks_stored": 0,
                "duplicates_skipped": 0,
                "status": "error",
                "message": str(e),
            }

    async def process_pdf_folder(self, folder_path: str) -> dict:
        """Process all PDFs in a folder in parallel (4 workers).

        Returns aggregate stats: total_pdfs, successful, failed,
        total_chunks_stored, total_duplicates_skipped, failed_files, time_taken.
        """
        start_time = time.time()

        pdf_files = glob.glob(os.path.join(folder_path, "**", "*.pdf"), recursive=True)

        if not pdf_files:
            return {
                "total_pdfs": 0,
                "successful": 0,
                "failed": 0,
                "total_chunks_stored": 0,
                "total_duplicates_skipped": 0,
                "failed_files": [],
                "time_taken_seconds": 0.0,
            }

        total = len(pdf_files)
        results = []
        successful = 0
        failed = 0
        total_stored = 0
        total_dupes = 0
        failed_files = []

        # Use ThreadPoolExecutor for parallel I/O-bound PDF processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_pdf = {}
            for idx, pdf_path in enumerate(pdf_files):
                pdf_name = os.path.basename(pdf_path)
                print(f"Processing {idx + 1}/{total}: {pdf_name}")
                future = executor.submit(self.process_single_pdf, pdf_path)
                future_to_pdf[future] = pdf_path

            for future in concurrent.futures.as_completed(future_to_pdf):
                result = future.result()
                results.append(result)

                if result["status"] == "ok":
                    successful += 1
                    total_stored += result["chunks_stored"]
                    total_dupes += result["duplicates_skipped"]
                else:
                    failed += 1
                    failed_files.append(result["pdf_name"])

        elapsed = time.time() - start_time

        summary = {
            "total_pdfs": total,
            "processed": successful,
            "successful": successful,
            "failed": failed,
            "total_chunks_stored": total_stored,
            "chunks_stored": total_stored,
            "chunks_added": total_stored,
            "total_duplicates_skipped": total_dupes,
            "duplicates_skipped": total_dupes,
            "failed_files": failed_files,
            "time_taken_seconds": round(elapsed, 2),
        }

        print(f"\n{'='*50}")
        print(f"Bulk Ingestion Complete")
        print(f"  Total PDFs:            {total}")
        print(f"  Successful:            {successful}")
        print(f"  Failed:                {failed}")
        print(f"  Chunks stored:         {total_stored}")
        print(f"  Duplicates skipped:    {total_dupes}")
        print(f"  Time taken:            {elapsed:.2f}s")
        print(f"{'='*50}")

        return summary
