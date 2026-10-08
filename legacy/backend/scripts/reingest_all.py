#!/usr/bin/env python3
"""Re-ingest all uploaded sources from SQLite into ChromaDB 'sources' collection.

Uses chunk_size=800 and overlap=150 to ensure dense, comprehensive indexing
across all PDFs and documents in the library.
Includes PyMuPDF OCR fallback for image-based/scanned/jsPDF PDFs.
"""

import os
import sys
import time
import sqlite3
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple, Dict, Any

import chromadb

try:
    import fitz  # PyMuPDF
except ImportError:
    try:
        import pymupdf as fitz
    except ImportError:
        fitz = None

try:
    import docx
except ImportError:
    docx = None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("reingest_all")

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "graph_db", "ingestor.db")
CHROMA_DIR = os.path.join(BASE_DIR, "graph_db", "chroma")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "sources")

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
BATCH_SIZE = 50
MAX_WORKERS = 4


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into chunks with sliding window overlap."""
    if not text:
        return []
    chunks = []
    start = 0
    text_len = len(text)
    step = max(1, chunk_size - overlap)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks


def extract_text_from_file(file_path: str, file_type: str) -> str:
    """Extract full text from PDF or DOCX file, with OCR fallback for scanned/jsPDF pages."""
    if not os.path.isfile(file_path):
        return ""

    file_ext = os.path.splitext(file_path)[1].lower().lstrip(".")
    text_parts = []

    if file_ext == "pdf" or str(file_type).lower() == "pdf":
        if fitz is None:
            return ""
        try:
            doc = fitz.open(file_path)
            for page in doc:
                page_text = page.get_text()
                # If page has very little or no selectable text, attempt OCR
                if len(page_text.strip()) < 20:
                    try:
                        tp = page.get_textpage_ocr(language="eng")
                        ocr_text = page.get_text(textpage=tp)
                        if len(ocr_text.strip()) > len(page_text.strip()):
                            page_text = ocr_text
                    except Exception:
                        pass
                if page_text:
                    text_parts.append(page_text)
            doc.close()
        except Exception as e:
            logger.warning(f"Error reading PDF {file_path}: {e}")

    elif file_ext in ["docx", "doc"] or str(file_type).lower() in ["docx", "doc"]:
        if docx is not None:
            try:
                doc = docx.Document(file_path)
                doc_text = "\n".join([p.text for p in doc.paragraphs if p.text])
                text_parts.append(doc_text)
            except Exception as e:
                logger.warning(f"Error reading DOCX {file_path}: {e}")

    return "\n".join(text_parts).strip()


def process_single_source(row_data: Dict[str, Any]) -> Dict[str, Any]:
    """Process a single file: extract text, generate chunks and metadata."""
    source_id = row_data["id"]
    filename = row_data["filename"]
    file_type = row_data["type"] or "pdf"
    file_path = row_data["path"]

    # Path resolution fallback
    if not os.path.exists(file_path):
        alt1 = os.path.join(UPLOAD_DIR, os.path.basename(file_path))
        alt2 = os.path.join(UPLOAD_DIR, f"{source_id}_{filename}")
        if os.path.exists(alt1):
            file_path = alt1
        elif os.path.exists(alt2):
            file_path = alt2

    if not os.path.exists(file_path):
        return {"id": source_id, "filename": filename, "chunks": [], "error": "file_not_found"}

    raw_text = extract_text_from_file(file_path, file_type)
    if not raw_text:
        return {"id": source_id, "filename": filename, "chunks": [], "error": "no_text"}

    chunks = chunk_text(raw_text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
    chunk_ids = [f"{source_id}_chunk_{j}" for j in range(len(chunks))]
    chunk_metadatas = [
        {
            "source": filename,
            "source_id": source_id,
            "filename": filename,
            "file_id": source_id,
            "chunk_idx": j,
            "filepath": file_path,
        }
        for j in range(len(chunks))
    ]

    return {
        "id": source_id,
        "filename": filename,
        "chunks": chunks,
        "chunk_ids": chunk_ids,
        "chunk_metadatas": chunk_metadatas,
        "error": None,
    }


def reingest_all():
    """Main routine to clear ChromaDB sources collection and re-index all sources."""
    start_time = time.time()
    if not os.path.exists(DB_PATH):
        logger.error(f"Database not found at {DB_PATH}")
        sys.exit(1)

    logger.info(f"Connecting to database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH, timeout=60.0)
    conn.row_factory = sqlite3.Row

    with conn:
        sources = [
            dict(r)
            for r in conn.execute(
                "SELECT id, filename, type, path FROM uploaded_sources ORDER BY uploaded_at ASC"
            ).fetchall()
        ]

    logger.info(f"Found {len(sources)} source files in SQLite database.")

    # Initialize ChromaDB client
    os.makedirs(CHROMA_DIR, exist_ok=True)
    logger.info(f"Connecting to ChromaDB at {CHROMA_DIR}...")
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Delete existing 'sources' collection if present
    try:
        chroma_client.delete_collection("sources")
        logger.info("Deleted existing 'sources' collection from ChromaDB.")
    except Exception as e:
        logger.info(f"No existing 'sources' collection to delete or delete failed: {e}")

    # Create fresh 'sources' collection with cosine space
    logger.info("Creating fresh 'sources' collection with cosine distance metric...")
    collection = chroma_client.create_collection(
        name="sources",
        metadata={"hnsw:space": "cosine"}
    )

    logger.info(f"Extracting and chunking documents using {MAX_WORKERS} worker threads...")
    total_chunks_indexed = 0
    files_successful = 0
    files_empty = 0
    files_missing = 0
    update_batch = []

    # Parallel text extraction & chunking
    results_map = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_single_source, s): s["id"] for s in sources}
        completed_count = 0
        for future in as_completed(futures):
            res = future.result()
            results_map[res["id"]] = res
            completed_count += 1
            if completed_count % 25 == 0 or completed_count == len(sources):
                logger.info(f"Extracted {completed_count}/{len(sources)} files...")

    logger.info("Inserting chunks into ChromaDB collection 'sources'...")
    # Ingest sequentially to ChromaDB to ensure thread safety
    for idx, s in enumerate(sources, start=1):
        res = results_map.get(s["id"])
        if not res or res.get("error") == "file_not_found":
            files_missing += 1
            update_batch.append((0, s["id"]))
            continue
        if res.get("error") == "no_text" or not res["chunks"]:
            files_empty += 1
            update_batch.append((0, s["id"]))
            continue

        chunks = res["chunks"]
        chunk_ids = res["chunk_ids"]
        chunk_metadatas = res["chunk_metadatas"]

        for b_start in range(0, len(chunks), BATCH_SIZE):
            b_end = b_start + BATCH_SIZE
            collection.add(
                documents=chunks[b_start:b_end],
                metadatas=chunk_metadatas[b_start:b_end],
                ids=chunk_ids[b_start:b_end],
            )

        total_chunks_indexed += len(chunks)
        files_successful += 1
        update_batch.append((len(chunks), s["id"]))

        if idx % 50 == 0 or idx == len(sources):
            logger.info(f"ChromaDB progress: {idx}/{len(sources)} sources stored ({total_chunks_indexed} total chunks)")

    # Update SQLite
    logger.info("Updating chunks_count in SQLite table 'uploaded_sources'...")
    with conn:
        conn.executemany(
            "UPDATE uploaded_sources SET chunks_count = ? WHERE id = ?",
            update_batch
        )
    conn.close()

    elapsed = time.time() - start_time
    final_count = collection.count()
    logger.info("=" * 60)
    logger.info("RE-INGESTION COMPLETED")
    logger.info(f"Time Taken           : {elapsed:.1f}s")
    logger.info(f"Total Sources in DB  : {len(sources)}")
    logger.info(f"Files Indexed        : {files_successful}")
    logger.info(f"Files Empty/Scanned  : {files_empty}")
    logger.info(f"Files Missing        : {files_missing}")
    logger.info(f"Total Chunks Added   : {total_chunks_indexed}")
    logger.info(f"ChromaDB Collection  : {final_count} chunks")
    if files_successful > 0:
        logger.info(f"Average Chunks/File  : {total_chunks_indexed / files_successful:.1f}")
    logger.info("=" * 60)


if __name__ == "__main__":
    reingest_all()
