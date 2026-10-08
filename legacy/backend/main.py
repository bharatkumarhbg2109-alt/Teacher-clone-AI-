"""FastAPI Backend for AI Teacher Clone Knowledge Graph."""

import json
import os
import sqlite3
from typing import Any, Dict, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from routers.chat_router import router as chat_router, init_chat_tables
from routers.teach import router as teach_router
from routers.questions import router as questions_router
from database import init_db
from graph.bulk_ingestor import router as bulk_router
from graph.concept_extractor import router as concept_router
from graph.graph_service import router as graph_router
from graph.curriculum_generator import router as curriculum_router
from graph.graph_visualizer import router as visualizer_router
from graph.hybrid_retrieval import router as hybrid_router
from core.logging_config import setup_logging
from middleware.auth import APIKeyMiddleware, get_api_key

logger = setup_logging()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DB_PATH = os.path.join(BASE_DIR, "graph_db", "ingestor.db")

# Initialize all tables in SQLite
init_chat_tables(DB_PATH)
init_db(DB_PATH)

app = FastAPI(title="AI Teacher Clone Backend")
app.add_middleware(APIKeyMiddleware)

@app.get("/auth/key")
async def get_key():
    """Local-only endpoint — returns API key for Electron frontend bootstrap."""
    return {"api_key": get_api_key()}

# Register feature routers
app.include_router(chat_router, prefix="/chat", tags=["chat"])
app.include_router(teach_router)
app.include_router(questions_router)

# Register graph layer routers
app.include_router(bulk_router, tags=["graph"])
app.include_router(concept_router, tags=["graph"])
app.include_router(graph_router, tags=["graph"])
app.include_router(curriculum_router, tags=["graph"])
app.include_router(visualizer_router, tags=["graph"])
app.include_router(hybrid_router, tags=["graph"])

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static folder for Pyvis visualization and graph_data.json
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def read_root():
    return {"status": "ok", "message": "AI Teacher Clone Backend is running"}


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.get("/curriculum")
async def get_curriculum() -> List[Dict[str, Any]]:
    """Return list of curriculum chapters."""
    if not os.path.exists(DB_PATH):
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT * FROM curriculum ORDER BY chapter_num"
        ).fetchall()
        if not rows:
            conn.close()
            try:
                from graph.curriculum_generator import CurriculumGenerator

                gen = CurriculumGenerator()
                await gen.generate_curriculum()
                conn = sqlite3.connect(DB_PATH)
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT * FROM curriculum ORDER BY chapter_num"
                ).fetchall()
            except Exception as e:
                print(f"[Backend] Curriculum generation error: {e}")
                return []

        curriculum = []
        for r in rows:
            item = dict(r)
            for field in ("topic_list", "concept_list"):
                val = item.get(field)
                if isinstance(val, str):
                    try:
                        item[field] = json.loads(val)
                    except Exception:
                        item[field] = []
            curriculum.append(item)
        return curriculum
    finally:
        try:
            conn.close()
        except Exception:
            pass


@app.get("/graph/concept/{concept_name}")
def get_concept(concept_name: str) -> Dict[str, Any]:
    """Return neighbors and prerequisite chain for a concept."""
    try:
        from graph.graph_service import KnowledgeGraphService

        svc = KnowledgeGraphService()
        neighbors = svc.get_concept_neighbors(concept_name)
        prereqs = svc.get_prerequisite_chain(concept_name)
        return {
            "name": concept_name,
            "neighbors": neighbors,
            "prerequisites": prereqs,
        }
    except Exception as e:
        return {
            "name": concept_name,
            "neighbors": {"error": str(e)},
            "prerequisites": [],
        }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
