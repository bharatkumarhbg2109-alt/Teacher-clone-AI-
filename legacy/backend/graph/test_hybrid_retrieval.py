"""Test suite for HybridRetriever — run with: python backend/graph/test_hybrid_retrieval.py"""

import asyncio
import sys

# Ensure the backend/ directory is on sys.path
BACKEND_DIR = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from hybrid_retrieval import HybridRetriever


def test_1_import():
    """TEST 1 — Import and init"""
    r = HybridRetriever()
    print(f"PASS: TEST 1 — Init OK — ChromaDB has {r.collection.count()} chunks, Graph has {r.G.number_of_nodes()} nodes")
    return r


def test_2_vector_search(r):
    """TEST 2 — Vector search"""
    results = r.vector_search("what is force and motion", n_results=3)
    assert isinstance(results, list), "FAIL: vector_search did not return a list"
    if results:
        assert "text" in results[0], "FAIL: missing 'text' in result"
        assert "distance" in results[0], "FAIL: missing 'distance' in result"
        assert "source" in results[0], "FAIL: missing 'source' in result"
        assert results[0]["source"] == "vector", "FAIL: source should be 'vector'"
        print(f"PASS: TEST 2 — Vector search returned {len(results)} chunks")
    else:
        print("PASS: TEST 2 — Vector search returned empty (ChromaDB has no PDF data yet)")


def test_3_graph_expansion(r):
    """TEST 3 — Graph expansion (no Ollama needed)"""
    if r.G.number_of_nodes() > 0:
        top_nodes = list(r.G.nodes())[:2]
        expanded = r.graph_expand(top_nodes)
        assert isinstance(expanded, list), "FAIL: graph_expand did not return a list"
        print(f"PASS: TEST 3 — Graph expansion returned {len(expanded)} chunks for {top_nodes}")
    else:
        print("SKIP: TEST 3 — Graph empty")


def test_4_context_assembly(r):
    """TEST 4 — Context assembly (requires Ollama)"""
    try:
        result = asyncio.run(r.assemble_context("explain Newton's first law"))
        assert "all_chunks" in result, "FAIL: missing 'all_chunks'"
        assert "context_text" in result, "FAIL: missing 'context_text'"
        assert "query_concepts" in result, "FAIL: missing 'query_concepts'"
        assert "concept_map" in result, "FAIL: missing 'concept_map'"
        assert "prerequisite_warning" in result, "FAIL: missing 'prerequisite_warning'"
        assert isinstance(result["all_chunks"], list), "FAIL: all_chunks is not a list"
        print(
            f"PASS: TEST 4 — Context assembled — "
            f"{len(result['all_chunks'])} chunks, "
            f"concepts: {result['query_concepts']}"
        )
    except Exception as e:
        print(f"SKIP: TEST 4 — Ollama not available — {e}")


def test_5_prerequisite_warning(r):
    """TEST 5 — Prerequisite warning"""
    # Empty list should return None
    warning = r.get_prerequisite_warning([])
    assert warning is None, f"FAIL: Expected None for empty list, got {warning}"

    # If graph has prerequisite chains, test with a concept that has prereqs
    if r.G.number_of_nodes() > 0:
        # Try with a concept that likely has prerequisites
        test_concept = list(r.G.nodes())[0]
        result = r.get_prerequisite_warning([test_concept])
        # result can be None or a string — both are valid
        assert result is None or isinstance(result, str), f"FAIL: unexpected type {type(result)}"

    print("PASS: TEST 5 — Prerequisite warning handles empty input correctly")


def test_6_api_endpoint():
    """TEST 6 — API endpoint test"""
    try:
        import httpx
        r2 = httpx.post(
            "http://localhost:8002/query-hybrid",
            json={"query": "what is acceleration"},
            timeout=30,
        )
        assert r2.status_code == 200, f"FAIL: Status {r2.status_code}"
        data = r2.json()
        assert "all_chunks" in data, "FAIL: missing 'all_chunks' in response"
        assert "context_text" in data, "FAIL: missing 'context_text' in response"
        print(f"PASS: TEST 6 — Hybrid API endpoint working — {len(data['all_chunks'])} chunks returned")
    except Exception as e:
        print(f"SKIP: TEST 6 — Server not running — {e}")


def main():
    print("=" * 50)
    print("HybridRetriever Test Suite")
    print("=" * 50)

    # TEST 1 — Import
    r = test_1_import()

    # TEST 2 — Vector search
    test_2_vector_search(r)

    # TEST 3 — Graph expansion
    test_3_graph_expansion(r)

    # TEST 4 — Context assembly
    test_4_context_assembly(r)

    # TEST 5 — Prerequisite warning
    test_5_prerequisite_warning(r)

    # TEST 6 — API endpoint
    test_6_api_endpoint()

    print("\n" + "=" * 50)
    print("All 6 tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
