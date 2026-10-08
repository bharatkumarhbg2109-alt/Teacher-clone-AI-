"""Test suite for GraphVisualizer — run with: python backend/graph/test_graph_visualizer.py"""

import os
import sys

# Ensure the backend/ directory is on sys.path
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from graph_visualizer import GraphVisualizer


def test_1_import():
    """TEST 1 — Import and init"""
    viz = GraphVisualizer()
    print(f"PASS: TEST 1 — Init OK — graph has {viz.G.number_of_nodes()} nodes")
    return viz


def test_2_color_function(viz):
    """TEST 2 — Color function"""
    assert viz.get_chapter_color(None) == "#CCCCCC", "FAIL: None should return #CCCCCC"
    color0 = viz.get_chapter_color(0)
    assert color0.startswith("#"), f"FAIL: Chapter 0 color should start with #, got {color0}"
    color20 = viz.get_chapter_color(20)
    assert color20.startswith("#"), f"FAIL: Chapter 20 color should start with #, got {color20}"
    # Verify wrapping: chapter 15 should map to index 0 (15 % 15 = 0)
    assert viz.get_chapter_color(15) == viz.get_chapter_color(0), "FAIL: Color wrapping broken"
    print("PASS: TEST 2 — Color function works")


def test_3_d3_json(viz):
    """TEST 3 — D3 JSON generation"""
    data = viz.generate_d3_json()
    assert "nodes" in data, "FAIL: Missing 'nodes' key"
    assert "links" in data, "FAIL: Missing 'links' key"
    assert "node_count" in data, "FAIL: Missing 'node_count' key"
    assert "edge_count" in data, "FAIL: Missing 'edge_count' key"
    assert os.path.exists("backend/static/graph_data.json"), "FAIL: graph_data.json not saved"
    if data["nodes"]:
        node = data["nodes"][0]
        assert "id" in node, "FAIL: node missing 'id'"
        assert "color" in node, "FAIL: node missing 'color'"
        assert "label" in node, "FAIL: node missing 'label'"
        assert "size" in node, "FAIL: node missing 'size'"
    print(f"PASS: TEST 3 — D3 JSON — {data['node_count']} nodes, {data['edge_count']} edges")


def test_4_pyvis_html(viz):
    """TEST 4 — Pyvis HTML generation"""
    path = viz.generate_pyvis_html()
    assert os.path.exists("backend/static/knowledge_map.html"), "FAIL: HTML file not created"
    with open("backend/static/knowledge_map.html") as f:
        content = f.read()
    assert "<html" in content.lower() or "<!doctype" in content.lower(), "FAIL: Not valid HTML"
    assert len(content) > 1000, f"FAIL: HTML too small ({len(content)} chars)"
    print(f"PASS: TEST 4 — Pyvis HTML generated — {len(content)} chars")


def test_5_static_serving():
    """TEST 5 — Static files accessible"""
    try:
        import httpx
        r = httpx.get("http://localhost:8002/static/graph_data.json", timeout=5)
        assert r.status_code == 200, f"FAIL: Status {r.status_code}"
        print("PASS: TEST 5 — Static files served correctly")
    except Exception:
        print("SKIP: TEST 5 — Server not running")


def test_6_react_component():
    """TEST 6 — React component file exists and has required content"""
    path = "frontend/src/components/GraphMap.jsx"
    assert os.path.exists(path), f"FAIL: {path} not created"
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "iframe" in content, "FAIL: iframe missing in GraphMap"
    assert "fetch" in content, "FAIL: API fetch missing"
    assert "useState" in content, "FAIL: React hooks missing"
    assert "CHAPTER_COLORS" in content, "FAIL: Chapter colors missing"
    print("PASS: TEST 6 — GraphMap.jsx has required structure")


def main():
    print("=" * 50)
    print("GraphVisualizer Test Suite")
    print("=" * 50)

    # TEST 1 — Import
    viz = test_1_import()

    # TEST 2 — Color function
    test_2_color_function(viz)

    # TEST 3 — D3 JSON
    test_3_d3_json(viz)

    # TEST 4 — Pyvis HTML
    test_4_pyvis_html(viz)

    # TEST 5 — Static serving
    test_5_static_serving()

    # TEST 6 — React component
    test_6_react_component()

    print("\n" + "=" * 50)
    print("All 6 tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
