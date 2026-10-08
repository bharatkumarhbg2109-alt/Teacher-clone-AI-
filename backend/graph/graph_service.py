"""Knowledge Graph Service — NetworkX-backed concept graph from SQLite data.

Loads concepts and relationships from the SQLite database into a
NetworkX directed graph, persists via GraphML, and exposes query
functions for neighbors, prerequisite chains, centrality, and
JSON export for frontend visualization.
"""

import os
import re
import sqlite3
from typing import List, Optional

import networkx as nx


from fastapi import APIRouter

router = APIRouter()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "graph_db", "ingestor.db")
GRAPH_PATH = os.path.join(BASE_DIR, "graph_db", "knowledge_graph.graphml")


@router.post("/build-graph")
def build_graph():
    """Load all concepts and relationships from SQLite and build NetworkX graph."""
    svc = KnowledgeGraphService()
    G = svc.build_graph_from_db()
    return {
        "status": "ok",
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
    }


@router.post("/clear-graph-data")
def clear_graph_data():
    """Clear all concepts, relationships/relations, and chapter/curriculum data from SQLite."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        target_tables = ["concepts", "relationships", "relations", "curriculum", "chapters"]
        for table in target_tables:
            if table in existing_tables:
                cursor.execute(f"DELETE FROM {table}")

        conn.commit()
    finally:
        conn.close()

    # Clear persisted knowledge graph cache file if present
    for path in [GRAPH_PATH, os.path.join(BASE_DIR, "graph_db", "knowledge_graph.pkl")]:
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    return {"status": "success", "message": "Graph data cleared"}


class KnowledgeGraphService:
    """Build, persist, and query a knowledge graph from extracted concepts."""

    def __init__(self):
        """Initialize paths and set graph to None (lazy-loaded)."""
        self.db_path = DB_PATH
        self.graph_path = GRAPH_PATH
        self.graph: Optional[nx.DiGraph] = None

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize a concept name: lowercase, depluralize, collapse whitespace."""
        name = name.strip().lower()
        if len(name) > 4 and name.endswith("s") and not name.endswith("ss"):
            name = name[:-1]
        name = re.sub(r"\s+", " ", name)
        return name

    def build_graph_from_db(self) -> nx.DiGraph:
        """Load all concepts and relationships from SQLite into a DiGraph.

        Nodes carry display_name, type, importance, mention_count, chapter_id.
        Edges carry relation_type and weight. Only adds edges where both
        endpoints exist as nodes. Saves graph to pickle.
        """
        G = nx.DiGraph()

        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            # Load concepts as nodes
            concept_rows = conn.execute(
                "SELECT id, name, normalized_name, type, importance_score, mention_count "
                "FROM concepts"
            ).fetchall()

            for row in concept_rows:
                norm = row["normalized_name"]
                G.add_node(
                    norm,
                    display_name=row["name"],
                    type=row["type"],
                    importance=row["importance_score"],
                    mention_count=row["mention_count"],
                    chapter_id=None,
                )

            # Load relationships as edges
            rel_rows = conn.execute(
                "SELECT source_concept, target_concept, relation_type, weight "
                "FROM relationships"
            ).fetchall()

            edges_added = 0
            for row in rel_rows:
                src = self._normalize_name(row["source_concept"])
                tgt = self._normalize_name(row["target_concept"])

                # Only add edge if both nodes exist
                if src in G.nodes and tgt in G.nodes:
                    G.add_edge(
                        src,
                        tgt,
                        relation_type=row["relation_type"],
                        weight=row["weight"],
                    )
                    edges_added += 1
        finally:
            conn.close()

        # Save graph to GraphML
        os.makedirs(os.path.dirname(self.graph_path), exist_ok=True)
        nx.write_graphml(G, self.graph_path)

        self.graph = G
        print(f"Graph built — Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")
        return G

    def load_graph(self) -> nx.DiGraph:
        """Load graph from GraphML if available, otherwise build from DB."""
        if self.graph is not None:
            return self.graph

        if os.path.exists(self.graph_path):
            try:
                self.graph = nx.read_graphml(self.graph_path).to_directed()
            except Exception as e:
                print(f"[KnowledgeGraphService] Failed to load GraphML: {e}")
                self.graph = self.build_graph_from_db()
        else:
            self.graph = self.build_graph_from_db()

        return self.graph

    def get_concept_neighbors(self, concept_name: str, depth: int = 2) -> dict:
        """Get neighbors of a concept up to given depth using BFS.

        Returns center concept name and list of neighbors with
        relation type and distance from center.
        """
        G = self.load_graph()
        normalized = self._normalize_name(concept_name)

        if normalized not in G.nodes:
            return {"error": "concept not found"}

        # Get ego graph (subgraph within radius)
        subgraph = nx.ego_graph(G, normalized, radius=depth, undirected=True)

        # Get shortest paths from center to all neighbors
        lengths = nx.single_source_shortest_path_length(subgraph, normalized)

        neighbors = []
        for node, dist in lengths.items():
            if node == normalized:
                continue

            # Find the edge relation between center and neighbor
            relation = "related"
            if G.has_edge(normalized, node):
                relation = G.edges[normalized, node].get("relation_type", "related")
            elif G.has_edge(node, normalized):
                relation = G.edges[node, normalized].get("relation_type", "related")

            neighbors.append({
                "name": node,
                "relation": relation,
                "depth": dist,
            })

        return {
            "center": concept_name,
            "neighbors": neighbors,
        }

    def get_prerequisite_chain(self, concept_name: str) -> List[str]:
        """Get the ordered prerequisite chain for a concept.

        Filters to only 'prerequisite' edges, finds all ancestors
        via topological sort, and returns the ordered list of
        concepts to learn first.
        """
        G = self.load_graph()
        normalized = self._normalize_name(concept_name)

        if normalized not in G.nodes:
            return []

        # Build subgraph with only prerequisite edges
        prereq_edges = [
            (u, v, d)
            for u, v, d in G.edges(data=True)
            if d.get("relation_type") == "prerequisite"
        ]
        prereq_graph = nx.DiGraph(prereq_edges)

        # If the concept isn't in the prereq graph, no prerequisites
        if normalized not in prereq_graph.nodes:
            return []

        # Find all ancestors (concepts that are prerequisites)
        try:
            ancestors = nx.ancestors(prereq_graph, normalized)
        except nx.NetworkXError:
            return []

        if not ancestors:
            return []

        # Topological sort of the subgraph containing ancestors + target
        sub = prereq_graph.subgraph(ancestors | {normalized})
        try:
            topo_order = list(nx.topological_sort(sub))
        except nx.NetworkXUnfeasible:
            # Cycle detected — return ancestors without ordering
            return list(ancestors)

        # Remove the target concept itself, return prerequisites in order
        return [c for c in topo_order if c != normalized]

    def get_top_concepts(self, n: int = 30) -> List[dict]:
        """Get top N concepts by combined importance + centrality score.

        Combined score = importance * 0.6 + centrality * 0.4 * 10.
        Returns list of dicts sorted by combined score descending.
        """
        G = self.load_graph()

        if not G.nodes:
            return []

        centrality = nx.degree_centrality(G)

        scored = []
        for node in G.nodes:
            data = G.nodes[node]
            importance = data.get("importance", 1.0)
            cent = centrality.get(node, 0.0)
            combined = importance * 0.6 + cent * 0.4 * 10

            scored.append({
                "name": data.get("display_name", node),
                "normalized": node,
                "importance": importance,
                "type": data.get("type", "concept"),
                "centrality": round(cent, 4),
                "combined_score": round(combined, 4),
            })

        scored.sort(key=lambda x: x["combined_score"], reverse=True)
        return scored[:n]

    def export_graph_json(self) -> dict:
        """Export the graph as a JSON-serializable dict for frontend visualization.

        Includes nodes (with visual sizing), edges, and aggregate stats.
        """
        G = self.load_graph()

        nodes = []
        for node in G.nodes:
            data = G.nodes[node]
            importance = data.get("importance", 1.0)
            nodes.append({
                "id": node,
                "label": data.get("display_name", node),
                "type": data.get("type", "concept"),
                "importance": importance,
                "chapter_id": data.get("chapter_id"),
                "size": min(importance * 2, 30),
            })

        edges = []
        for u, v, d in G.edges(data=True):
            edges.append({
                "source": u,
                "target": v,
                "type": d.get("relation_type", "related"),
                "weight": d.get("weight", 0.5),
            })

        isolated = sum(1 for n in G.nodes if G.degree(n) == 0)

        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "total_nodes": len(nodes),
                "total_edges": len(edges),
                "isolated_nodes": isolated,
            },
        }
