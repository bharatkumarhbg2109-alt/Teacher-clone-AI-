"""Graph Visualizer — Pyvis HTML + D3 JSON export from NetworkX knowledge graph.

Generates an interactive Pyvis HTML visualization and a structured
D3.js-compatible JSON export, both color-coded by Louvain-detected
chapter communities.
"""

import json
import os

from pyvis.network import Network

from app.graph.graph_service import KnowledgeGraphService

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

# Chapter color palette — deterministic by community ID
COLORS = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
    "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E9",
    "#F8C471", "#82E0AA", "#F1948A", "#85C1E9", "#D7BDE2",
]


@router.get("/graph/visualize")
def visualize_graph(format: str = "json"):
    """Generate Pyvis HTML and D3 JSON for graph visualization."""
    viz = GraphVisualizer()
    html_path = viz.generate_pyvis_html()
    d3_data = viz.generate_d3_json()
    if format.lower() == "html" and os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return {
        "status": "ok",
        "html_file": html_path,
        "data": d3_data,
    }


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATIC_DIR = os.path.join(BASE_DIR, "static")


class GraphVisualizer:
    """Generate interactive visualizations from the knowledge graph."""

    def __init__(self):
        """Load the knowledge graph and ensure static directory exists."""
        self.graph_svc = KnowledgeGraphService()
        self.graph_svc.load_graph()
        self.G = self.graph_svc.graph
        self.static_dir = STATIC_DIR
        os.makedirs(self.static_dir, exist_ok=True)

    def get_chapter_color(self, chapter_id) -> str:
        """Return a hex color for the given chapter ID."""
        if chapter_id is None:
            return "#CCCCCC"
        return COLORS[chapter_id % len(COLORS)]

    def generate_pyvis_html(self) -> str:
        """Generate an interactive Pyvis HTML visualization of the graph.

        Dark theme, force-directed layout, curved edges, hover tooltips.
        Saves to backend/static/knowledge_map.html and returns the path.
        """
        net = Network(
            height="750px",
            width="100%",
            bgcolor="#1a1a2e",
            font_color="white",
            directed=True,
        )

        net.set_options(json.dumps({
            "physics": {
                "enabled": True,
                "solver": "forceAtlas2Based",
                "forceAtlas2Based": {
                    "gravitationalConstant": -50,
                    "springLength": 100,
                },
            },
            "edges": {
                "smooth": {"type": "curvedCW", "roundness": 0.2},
            },
            "interaction": {
                "hover": True,
                "tooltipDelay": 200,
            },
        }))

        # Add nodes
        for node, attrs in self.G.nodes(data=True):
            importance = attrs.get("importance", 1)
            size = max(10, min(importance * 4, 40))
            color = self.get_chapter_color(attrs.get("chapter_id"))
            title = (
                f"<b>{attrs.get('display_name', node)}</b><br>"
                f"Type: {attrs.get('type', '?')}<br>"
                f"Importance: {importance:.1f}<br>"
                f"Chapter: {attrs.get('chapter_id', '?')}"
            )
            net.add_node(
                node,
                label=attrs.get("display_name", node)[:20],
                size=size,
                color=color,
                title=title,
            )

        # Add edges
        for u, v, d in self.G.edges(data=True):
            relation = d.get("relation_type", "related")
            dash = relation in ("related", "example_of")
            weight = d.get("weight", 0.5)
            net.add_edge(
                u, v,
                label=relation,
                color="#888888",
                dashes=dash,
                width=weight * 2,
            )

        output_path = f"{self.static_dir}/knowledge_map.html"
        net.save_graph(output_path)
        return output_path

    def generate_d3_json(self) -> dict:
        """Generate D3.js-compatible JSON with nodes, links, and counts.

        Saves to backend/static/graph_data.json and returns the data dict.
        """
        nodes = []
        for node, attrs in self.G.nodes(data=True):
            importance = attrs.get("importance", 1)
            nodes.append({
                "id": node,
                "label": attrs.get("display_name", node),
                "type": attrs.get("type", "concept"),
                "group": attrs.get("chapter_id", 0),
                "importance": importance,
                "size": max(4, min(importance * 2, 20)),
                "color": self.get_chapter_color(attrs.get("chapter_id")),
            })

        links = []
        for u, v, d in self.G.edges(data=True):
            relation = d.get("relation_type", "related")
            links.append({
                "source": u,
                "target": v,
                "type": relation,
                "value": d.get("weight", 0.5),
                "dashed": relation in ("related", "example_of"),
            })

        data = {
            "nodes": nodes,
            "links": links,
            "node_count": len(nodes),
            "edge_count": len(links),
        }

        output_path = f"{self.static_dir}/graph_data.json"
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

        return data
