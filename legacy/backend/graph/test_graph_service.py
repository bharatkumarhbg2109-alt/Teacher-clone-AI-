"""Test suite for KnowledgeGraphService — run with: python backend/graph/test_graph_service.py"""

import os
import sqlite3
import sys

# Ensure the backend/ directory is on sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from graph_service import KnowledgeGraphService


def _seed_test_data(db_path: str):
    """Insert test concepts and relationships if tables are empty."""
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
    if count == 0:
        conn.execute(
            "INSERT OR IGNORE INTO concepts (id, name, normalized_name, type, source_pdf, chunk_id, importance_score, mention_count) VALUES "
            "(1,'Force','force','topic','test.pdf','c1',8.0,3)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO concepts (id, name, normalized_name, type, source_pdf, chunk_id, importance_score, mention_count) VALUES "
            "(2,'Motion','motion','concept','test.pdf','c1',6.0,2)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO concepts (id, name, normalized_name, type, source_pdf, chunk_id, importance_score, mention_count) VALUES "
            "(3,'Velocity','velocity','concept','test.pdf','c2',5.0,1)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO concepts (id, name, normalized_name, type, source_pdf, chunk_id, importance_score, mention_count) VALUES "
            "(4,'Acceleration','acceleration','subtopic','test.pdf','c2',7.0,2)"
        )
        conn.execute(
            "INSERT OR IGNORE INTO relationships VALUES "
            "(1,'force','motion','prerequisite',0.9,'c1')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO relationships VALUES "
            "(2,'motion','velocity','related',0.7,'c1')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO relationships VALUES "
            "(3,'velocity','acceleration','prerequisite',0.8,'c2')"
        )
        conn.execute(
            "INSERT OR IGNORE INTO relationships VALUES "
            "(4,'force','acceleration','related',0.6,'c1')"
        )
        conn.commit()
    conn.close()


def test_1_import():
    """TEST 1 — Import"""
    svc = KnowledgeGraphService()
    print("PASS: TEST 1 — Import OK")
    return svc


def test_2_build_graph(svc):
    """TEST 2 — Build graph (seeds test data if empty)"""
    _seed_test_data(svc.db_path)

    # Remove any existing pickle to force rebuild
    if os.path.exists(svc.graph_path):
        os.remove(svc.graph_path)
    svc.graph = None

    G = svc.build_graph_from_db()
    assert G.number_of_nodes() >= 2, "FAIL: No nodes in graph"
    assert G.number_of_edges() >= 1, "FAIL: No edges in graph"
    print(f"PASS: TEST 2 — Graph built — {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    return G


def test_3_pickle_persistence(svc):
    """TEST 3 — Pickle save/load"""
    assert os.path.exists(svc.graph_path), "FAIL: Pickle file not created"

    svc2 = KnowledgeGraphService()
    G2 = svc2.load_graph()
    assert G2.number_of_nodes() > 0, "FAIL: Loaded graph has no nodes"
    print(f"PASS: TEST 3 — Graph persists and loads from pickle ({G2.number_of_nodes()} nodes)")


def test_4_neighbor_query(svc):
    """TEST 4 — Neighbor query"""
    result = svc.get_concept_neighbors("force", depth=2)
    assert "neighbors" in result or "error" in result, "FAIL: Unexpected return structure"
    if "neighbors" in result:
        print(f"PASS: TEST 4 — Neighbors found — {len(result['neighbors'])} neighbors for 'force'")
    else:
        print(f"PASS: TEST 4 — Handled missing concept gracefully: {result}")


def test_5_export_json(svc):
    """TEST 5 — Export JSON"""
    data = svc.export_graph_json()
    assert "nodes" in data, "FAIL: Missing 'nodes' key"
    assert "edges" in data, "FAIL: Missing 'edges' key"
    assert "stats" in data, "FAIL: Missing 'stats' key"
    assert isinstance(data["nodes"], list), "FAIL: nodes is not a list"
    assert isinstance(data["edges"], list), "FAIL: edges is not a list"
    if data["nodes"]:
        assert "id" in data["nodes"][0], "FAIL: node missing 'id' field"
        assert "label" in data["nodes"][0], "FAIL: node missing 'label' field"
        assert "size" in data["nodes"][0], "FAIL: node missing 'size' field"
    print(f"PASS: TEST 5 — JSON export — {data['stats']}")


def test_6_top_concepts(svc):
    """TEST 6 — Top concepts"""
    top = svc.get_top_concepts(5)
    assert isinstance(top, list), "FAIL: top_concepts did not return a list"
    names = [c["name"] for c in top[:3]]
    print(f"PASS: TEST 6 — Top concepts — {names}")


def test_7_clear_graph_data(svc):
    """TEST 7 — Clear graph data endpoint"""
    from graph_service import clear_graph_data
    result = clear_graph_data()
    assert result == {"status": "success", "message": "Graph data cleared"}, f"FAIL: unexpected result {result}"

    conn = sqlite3.connect(svc.db_path)
    c_count = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
    r_count = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    conn.close()
    assert c_count == 0, f"FAIL: concepts not empty ({c_count})"
    assert r_count == 0, f"FAIL: relationships not empty ({r_count})"
    assert not os.path.exists(svc.graph_path), "FAIL: graph pkl was not removed"
    print("PASS: TEST 7 — Clear graph data OK")


def main():
    print("=" * 50)
    print("KnowledgeGraphService Test Suite")
    print("=" * 50)

    # TEST 1 — Import
    svc = test_1_import()

    # TEST 2 — Build graph
    test_2_build_graph(svc)

    # TEST 3 — Pickle persistence
    test_3_pickle_persistence(svc)

    # TEST 4 — Neighbor query
    test_4_neighbor_query(svc)

    # TEST 5 — Export JSON
    test_5_export_json(svc)

    # TEST 6 — Top concepts
    test_6_top_concepts(svc)

    # TEST 7 — Clear graph data
    test_7_clear_graph_data(svc)

    print("\n" + "=" * 50)
    print("All 7 tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()

