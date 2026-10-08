"""Test suite for CurriculumGenerator — run with: python backend/graph/test_curriculum_generator.py"""

import os
import sqlite3
import sys

# Ensure the backend/ directory is on sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from curriculum_generator import CurriculumGenerator


def _ensure_graph_data():
    """Make sure the graph has enough nodes for meaningful tests."""
    from graph_service import KnowledgeGraphService
    import networkx as nx

    svc = KnowledgeGraphService()
    svc.load_graph()
    if svc.graph and svc.graph.number_of_nodes() >= 5:
        return  # Already have enough data

    # Seed more test data if graph is too small
    db_path = "backend/graph_db/ingestor.db"
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
    if count < 8:
        extra_concepts = [
            (10, "Inertia", "inertia", "concept", "test.pdf", "c3", 5.0, 2),
            (11, "Newton's Second Law", "newton's second law", "topic", "test.pdf", "c3", 9.0, 4),
            (12, "Gravity", "gravity", "topic", "test.pdf", "c4", 8.0, 3),
            (13, "Friction", "friction", "subtopic", "test.pdf", "c4", 6.0, 2),
            (14, "Momentum", "momentum", "concept", "test.pdf", "c5", 7.0, 2),
            (15, "Energy", "energy", "topic", "test.pdf", "c5", 9.0, 5),
            (16, "Work", "work", "concept", "test.pdf", "c5", 5.0, 1),
            (17, "Power", "power", "concept", "test.pdf", "c5", 4.0, 1),
        ]
        for c in extra_concepts:
            conn.execute(
                "INSERT OR IGNORE INTO concepts VALUES (?,?,?,?,?,?,?,?)", c
            )
        extra_rels = [
            (10, "inertia", "newton's second law", "prerequisite", 0.8, "c3"),
            (11, "newton's second law", "gravity", "related", 0.7, "c3"),
            (12, "gravity", "friction", "related", 0.6, "c4"),
            (13, "friction", "momentum", "prerequisite", 0.5, "c4"),
            (14, "momentum", "energy", "prerequisite", 0.9, "c5"),
            (15, "energy", "work", "related", 0.8, "c5"),
            (16, "work", "power", "related", 0.7, "c5"),
        ]
        for r in extra_rels:
            conn.execute(
                "INSERT OR IGNORE INTO relationships VALUES (?,?,?,?,?,?)", r
            )
        conn.commit()
    conn.close()

    # Rebuild graph
    if os.path.exists("backend/graph_db/knowledge_graph.pkl"):
        os.remove("backend/graph_db/knowledge_graph.pkl")
    svc2 = KnowledgeGraphService()
    svc2.graph = None  # force rebuild
    svc2.build_graph_from_db()


def test_1_import():
    """TEST 1 — Import and init"""
    _ensure_graph_data()
    gen = CurriculumGenerator()
    print(f"PASS: TEST 1 — Init OK — graph has {gen.G.number_of_nodes()} nodes")
    return gen


def test_2_detect_chapters(gen):
    """TEST 2 — Chapter detection"""
    if gen.G.number_of_nodes() < 5:
        print("SKIP: TEST 2 — Need more graph data")
        return None

    partition = gen.detect_chapters()
    unique_chapters = len(set(partition.values()))
    assert unique_chapters >= 1, "FAIL: No chapters detected"
    print(f"PASS: TEST 2 — Detected {unique_chapters} chapters from {len(partition)} concepts")
    return partition


def test_3_chapter_ordering(gen, partition):
    """TEST 3 — Chapter ordering"""
    if partition is None:
        print("SKIP: TEST 3 — Skipped because TEST 2 was skipped")
        return None

    order = gen.order_chapters(partition)
    assert isinstance(order, list), "FAIL: order_chapters did not return a list"
    assert len(order) >= 1, "FAIL: Empty order list"
    print(f"PASS: TEST 3 — Chapter order: {order}")
    return order


def test_4_hierarchy(gen, partition, order):
    """TEST 4 — Hierarchy building"""
    if partition is None or order is None:
        print("SKIP: TEST 4 — Skipped because prerequisite test was skipped")
        return

    chapters = gen.build_hierarchy(partition, order)
    assert len(chapters) >= 1, "FAIL: No chapters in hierarchy"
    assert "topics" in chapters[0], "FAIL: Missing 'topics' key"
    assert "community_id" in chapters[0], "FAIL: Missing 'community_id' key"
    assert "subtopics" in chapters[0], "FAIL: Missing 'subtopics' key"
    assert "concepts" in chapters[0], "FAIL: Missing 'concepts' key"
    total_nodes = sum(ch["size"] for ch in chapters)
    print(f"PASS: TEST 4 — Hierarchy built — {len(chapters)} chapters, {total_nodes} total nodes")


def test_5_hour_estimation(gen):
    """TEST 5 — Hour estimation"""
    fake_chapter = {
        "topics": ["a", "b", "c"],
        "subtopics": ["d", "e"],
        "concepts": ["f", "g", "h", "i"],
    }
    hours = gen.estimate_hours(fake_chapter)
    assert hours > 0, "FAIL: Hours should be > 0"
    # 3*0.5 + 2*0.3 + 4*0.1 = 1.5 + 0.6 + 0.4 = 2.5
    assert hours == 2.5, f"FAIL: Expected 2.5, got {hours}"
    print(f"PASS: TEST 5 — Hours estimated: {hours}")


def test_6_sqlite_curriculum_table():
    """TEST 6 — Curriculum table exists"""
    db_path = "backend/graph_db/ingestor.db"
    conn = sqlite3.connect(db_path)
    tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    conn.close()
    assert "curriculum" in tables, "FAIL: curriculum table missing"
    print("PASS: TEST 6 — Curriculum table exists")


def main():
    print("=" * 50)
    print("CurriculumGenerator Test Suite")
    print("=" * 50)

    # TEST 1 — Import
    gen = test_1_import()

    # TEST 2 — Detect chapters
    partition = test_2_detect_chapters(gen)

    # TEST 3 — Chapter ordering
    order = test_3_chapter_ordering(gen, partition)

    # TEST 4 — Hierarchy
    test_4_hierarchy(gen, partition, order)

    # TEST 5 — Hour estimation
    test_5_hour_estimation(gen)

    # TEST 6 — SQLite table
    test_6_sqlite_curriculum_table()

    print("\n" + "=" * 50)
    print("All 6 tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
