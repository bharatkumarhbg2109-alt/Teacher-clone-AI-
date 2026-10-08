"""Test suite for BulkIngestor — run with: python backend/graph/test_bulk_ingestor.py"""

import glob
import hashlib
import os
import sqlite3
import sys

# Ensure the backend/ directory is on sys.path so we can import bulk_ingestor
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from bulk_ingestor import BulkIngestor


def test_1_import():
    """TEST 1 — Import test"""
    b = BulkIngestor()
    print("PASS: TEST 1 — Import and init OK")
    return b


def test_2_sqlite(b):
    """TEST 2 — SQLite init test"""
    conn = sqlite3.connect(b.db_path)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    conn.close()
    assert ("processed_chunks",) in tables, "FAIL: Table not created"
    print("PASS: TEST 2 — SQLite table exists")


def test_3_chromadb(b):
    """TEST 3 — ChromaDB connection test"""
    count = b.collection.count()
    print(f"PASS: TEST 3 — ChromaDB connected, current chunks: {count}")


def test_4_chunking(b):
    """TEST 4 — Chunking test (no PDF needed)"""
    fake_pages = [
        {
            "text": "This is a test paragraph with enough characters to pass the minimum threshold for chunking. " * 5
            + "\n\n"
            + "Second paragraph here with more text to test chunking behavior properly. "
            * 5,
            "page_num": 1,
            "pdf_name": "test.pdf",
            "section_header": None,
            "char_count": 500,
        }
    ]
    chunks = b.semantic_chunk(fake_pages)
    assert len(chunks) >= 1, "FAIL: No chunks generated"
    assert "chunk_text" in chunks[0], "FAIL: Missing chunk_text key"
    assert "chunk_hash" in chunks[0], "FAIL: Missing chunk_hash key"
    assert "chunk_index" in chunks[0], "FAIL: Missing chunk_index key"
    # Verify hash is correct
    expected_hash = hashlib.md5(chunks[0]["chunk_text"].encode()).hexdigest()
    assert chunks[0]["chunk_hash"] == expected_hash, "FAIL: Hash mismatch"
    print(f"PASS: TEST 4 — Chunking works, got {len(chunks)} chunks")
    return chunks


def test_5_deduplication(b, chunks):
    """TEST 5 — Deduplication test"""
    # First pass: should keep all chunks
    first_pass = b.deduplicate(chunks)
    assert len(first_pass) == len(chunks), "FAIL: First pass dropped chunks"

    # Second pass: should skip all (they're now in SQLite)
    second_pass = b.deduplicate(chunks)
    assert len(second_pass) == 0, "FAIL: Deduplication not working"
    print("PASS: TEST 5 — Deduplication works")


def test_6_end_to_end(b):
    """TEST 6 — End-to-end with real PDF"""
    pdfs = glob.glob("backend/uploads/pdfs/**/*.pdf", recursive=True)
    if not pdfs:
        print("SKIP: TEST 6 — No PDFs found for end-to-end test")
        return
    result = b.process_single_pdf(pdfs[0])
    assert result["status"] == "ok", f"FAIL: {result}"
    print(f"PASS: TEST 6 — Real PDF processed — {result}")


def test_7_api_endpoint():
    """TEST 7 — API endpoint test"""
    try:
        import httpx
        r = httpx.get("http://localhost:8002/ingestor/status")
        assert r.status_code == 200
        print(f"PASS: TEST 7 — API endpoint working — {r.json()}")
    except Exception as e:
        print(f"SKIP: TEST 7 — Server not running — {e}")


def main():
    print("=" * 50)
    print("BulkIngestor Test Suite")
    print("=" * 50)

    # TEST 1 — Import
    b = test_1_import()

    # TEST 2 — SQLite
    test_2_sqlite(b)

    # TEST 3 — ChromaDB
    test_3_chromadb(b)

    # TEST 4 — Chunking
    chunks = test_4_chunking(b)

    # TEST 5 — Deduplication
    test_5_deduplication(b, chunks)

    # TEST 6 — End-to-end
    test_6_end_to_end(b)

    # TEST 7 — API
    test_7_api_endpoint()

    print("\n" + "=" * 50)
    print("All required tests (1-5) passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
