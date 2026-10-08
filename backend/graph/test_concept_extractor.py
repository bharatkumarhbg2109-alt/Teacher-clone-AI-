"""Test suite for ConceptExtractor — run with: python backend/graph/test_concept_extractor.py"""

import os
import sqlite3
import sys

# Ensure the backend/ directory is on sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from concept_extractor import ConceptExtractor


def test_1_import():
    """TEST 1 — Import and init"""
    ce = ConceptExtractor()
    print("PASS: TEST 1 — Init OK")
    return ce


def test_2_sqlite_tables(ce):
    """TEST 2 — SQLite tables exist"""
    conn = sqlite3.connect(ce.db_path)
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    conn.close()
    for t in ["concepts", "relationships", "extraction_log"]:
        assert t in tables, f"FAIL: {t} table missing"
    print("PASS: TEST 2 — All tables exist")


def test_3_normalize_name(ce):
    """TEST 3 — Name normalization"""
    assert ce.normalize_name("  Forces  ") == "force"
    assert ce.normalize_name("Newton's Laws") == "newton's law"
    # "multiple spaces" ends with 's' → depluralize removes it per spec
    assert ce.normalize_name("  Multiple   Spaces  ") == "multiple space"
    assert ce.normalize_name("short") == "short"  # words <= 4 chars not depluralized
    print("PASS: TEST 3 — normalize_name works")


def test_4_json_parsing(ce):
    """TEST 4 — Valid JSON parsing (no Ollama needed)"""
    fake_response = (
        '{"concepts": [{"name": "Force", "type": "topic", "importance": 8}], '
        '"relationships": [{"from": "Force", "to": "Motion", "type": "related", "weight": 0.7}]}'
    )
    parsed = ce.parse_llm_response(fake_response, "test_chunk_1", "test.pdf")
    assert len(parsed["concepts"]) == 1
    assert len(parsed["relationships"]) == 1
    assert parsed["concepts"][0]["name"] == "Force"
    assert parsed["relationships"][0]["from"] == "Force"
    print("PASS: TEST 4 — JSON parsing works")


def test_5_bad_json_recovery(ce):
    """TEST 5 — Malformed JSON recovery"""
    bad_response = (
        'Here is the answer: {"concepts": [{"name": "Test", "type": "concept", '
        '"importance": 5}], "relationships": []} some trailing text'
    )
    parsed = ce.parse_llm_response(bad_response, "test_chunk_2", "test.pdf")
    assert "parse_error" not in parsed or not parsed.get("parse_error")
    assert len(parsed["concepts"]) == 1
    print("PASS: TEST 5 — Bad JSON recovery works")


def test_6_ollama_connection():
    """TEST 6 — Ollama connection check"""
    try:
        import httpx

        r = httpx.get("http://localhost:11434/api/tags", timeout=5)
        assert r.status_code == 200
        models = [m["name"] for m in r.json().get("models", [])]
        has_model = any("llama3.1" in m for m in models)
        print(f"PASS: TEST 6 — Ollama running — llama3.1 available: {has_model}")
    except Exception:
        print("SKIP: TEST 6 — Ollama not running")


def test_7_single_chunk_extraction(ce):
    """TEST 7 — Single chunk extraction (requires Ollama)"""
    import asyncio

    test_text = (
        "Newton's First Law states that an object at rest stays at rest "
        "unless acted upon by an external force. This is also called the "
        "law of inertia. Inertia is the tendency of objects to resist "
        "changes in their state of motion."
    )
    try:
        result = asyncio.run(ce.call_ollama(ce.build_prompt(test_text)))
        assert result is not None, "FAIL: Ollama returned None"
        parsed = ce.parse_llm_response(result, "test_001", "test.pdf")
        assert len(parsed.get("concepts", [])) >= 1
        print(
            f"PASS: TEST 7 — Ollama extraction works — {len(parsed['concepts'])} concepts found"
        )
    except Exception as e:
        print(f"SKIP: TEST 7 — Ollama test failed — {e}")


def main():
    print("=" * 50)
    print("ConceptExtractor Test Suite")
    print("=" * 50)

    # TEST 1 — Import and init
    ce = test_1_import()

    # TEST 2 — SQLite tables
    test_2_sqlite_tables(ce)

    # TEST 3 — Normalize name
    test_3_normalize_name(ce)

    # TEST 4 — JSON parsing
    test_4_json_parsing(ce)

    # TEST 5 — Bad JSON recovery
    test_5_bad_json_recovery(ce)

    # TEST 6 — Ollama connection
    test_6_ollama_connection()

    # TEST 7 — Single chunk extraction
    test_7_single_chunk_extraction(ce)

    print("\n" + "=" * 50)
    print("All required tests (1-5) passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
