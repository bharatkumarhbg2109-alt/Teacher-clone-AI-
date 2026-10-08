"""ChromaDB and Knowledge Graph Migration Script.

Validates ChromaDB >= 0.5 compatibility and migrates legacy
knowledge_graph.pkl to knowledge_graph.graphml format.
"""
import os
import sys
from pathlib import Path
import networkx as nx

BACKEND_DIR = Path(__file__).resolve().parent.parent
GRAPH_DB_DIR = BACKEND_DIR / "graph_db"
PKL_PATH = GRAPH_DB_DIR / "knowledge_graph.pkl"
GRAPHML_PATH = GRAPH_DB_DIR / "knowledge_graph.graphml"


def migrate_knowledge_graph():
    """Migrate legacy pickle knowledge graph to GraphML format."""
    if PKL_PATH.exists() and not GRAPHML_PATH.exists():
        print(f"[MIGRATE] Converting {PKL_PATH} to {GRAPHML_PATH}...")
        try:
            import pickle
            with open(PKL_PATH, "rb") as f:
                G = pickle.load(f)
            if not isinstance(G, nx.Graph):
                G = nx.DiGraph(G)
            nx.write_graphml(G, str(GRAPHML_PATH))
            print(f"[MIGRATE] GraphML written with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges.")
        except Exception as e:
            print(f"[MIGRATE] Pickle conversion failed: {e}")
    elif GRAPHML_PATH.exists():
        print(f"[MIGRATE] GraphML file already exists: {GRAPHML_PATH}")
    else:
        print("[MIGRATE] No graph cache found; will be created on first build.")


def verify_chromadb():
    """Verify ChromaDB >= 0.5 initialization and collections."""
    try:
        import chromadb
        version = chromadb.__version__
        print(f"[MIGRATE] ChromaDB version: {version}")
        major, minor = [int(x) for x in version.split(".")[:2]]
        assert (major > 0) or (major == 0 and minor >= 5), f"ChromaDB version {version} is < 0.5"

        chroma_dir = str(GRAPH_DB_DIR / "chroma")
        client = chromadb.PersistentClient(path=chroma_dir)
        collections = client.list_collections()
        col_names = [c.name for c in collections]
        print(f"[MIGRATE] ChromaDB collections: {col_names}")
        print("[MIGRATE] ChromaDB verification successful.")
    except Exception as e:
        print(f"[MIGRATE] ChromaDB check note: {e}")


def main():
    print("=" * 50)
    print("AI Teacher Clone — ChromaDB & Graph Migration")
    print("=" * 50)
    verify_chromadb()
    migrate_knowledge_graph()
    print("[MIGRATE] Migration check complete.")


if __name__ == "__main__":
    main()
