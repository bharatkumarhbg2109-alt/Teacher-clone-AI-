"""FastAPI application factory."""
import logging
import os
import sys
from contextlib import asynccontextmanager

import traceback

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import List

from app.config import settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("teachclone")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure tables exist (dev-friendly; prod uses Alembic).
    from app.db.init import init_models

    try:
        await init_models()
        log.info("Database tables ready.")
    except Exception as exc:  # pragma: no cover
        log.warning("init_models skipped: %s", exc)

    # Refuse to start in production with default/empty secrets.
    if not settings.DEBUG:
        required_secrets = ["SECRET_KEY", "ANTHROPIC_API_KEY", "CLERK_SECRET_KEY"]
        for key in required_secrets:
            value = getattr(settings, key, "")
            if not value or value in ("change-me", "your-key-here", ""):
                raise RuntimeError(
                    f"Required secret {key} is not configured — "
                    "set it in your environment before starting in production."
                )

    # Ensure the Qdrant collection exists.
    try:
        from app.services.vector_store import vector_store

        await vector_store.ensure_collection()
        log.info("Qdrant collection ready.")
    except Exception as exc:  # pragma: no cover
        log.warning("Qdrant setup skipped: %s", exc)

    # P4: Start the review scheduler if INLINE_TASKS is enabled.
    import asyncio
    if settings.INLINE_TASKS:
        from app.services.review_scheduler import run_review_scheduler
        asyncio.create_task(run_review_scheduler())
        log.info("Review scheduler started (INLINE_TASKS mode).")

    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.VERSION,
        lifespan=lifespan,
    )

    _origins_env = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000")
    ALLOWED_ORIGINS = [o.strip() for o in _origins_env.split(",") if o.strip()]
    # Always include APP_URL so the frontend can talk to the API.
    if settings.APP_URL not in ALLOWED_ORIGINS:
        ALLOWED_ORIGINS.append(settings.APP_URL)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting (chat + DNA extraction endpoints)
    from app.middleware.rate_limit import RateLimitMiddleware, configure_groups

    configure_groups(
        chat_limit=settings.RATE_LIMIT_CHAT,
        dna_limit=settings.RATE_LIMIT_DNA,
        auth_limit=settings.RATE_LIMIT_AUTH,
        auth_window=settings.RATE_LIMIT_AUTH_WINDOW,
        upload_limit=settings.RATE_LIMIT_UPLOAD,
        voice_limit=settings.RATE_LIMIT_VOICE,
        public_limit=settings.RATE_LIMIT_PUBLIC,
        window=settings.RATE_LIMIT_WINDOW,
        backoff_base=settings.RATE_LIMIT_BACKOFF_BASE,
        backoff_max=settings.RATE_LIMIT_BACKOFF_MAX,
    )
    app.add_middleware(RateLimitMiddleware)

    # Request logging (logs 4xx/5xx with timing, user ID, and path)
    from app.middleware.request_logging import RequestLoggingMiddleware

    app.add_middleware(RequestLoggingMiddleware)

    # Security headers (CSP, X-Frame-Options, HSTS, etc.)
    from app.middleware.security_headers import SecurityHeadersMiddleware

    app.add_middleware(SecurityHeadersMiddleware)

    # Routers (added incrementally as features land).
    from app.routers import auth, health, users

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(users.router)

    # --- M1+ routers ---
    _include_optional(app, "storage")
    _include_optional(app, "teacher_profiles", "/profiles")
    _include_optional(app, "media")
    _include_optional(app, "sessions")
    _include_optional(app, "chat")
    _include_optional(app, "quizzes")
    _include_optional(app, "voice")
    _include_optional(app, "share")
    _include_optional(app, "discover")
    _include_optional(app, "billing")
    _include_optional(app, "organizations")
    _include_optional(app, "export")
    _include_optional(app, "webhooks")
    _include_optional(app, "v1_api")
    _include_optional(app, "dna_router")  # local Teacher DNA (Ollama)
    _include_optional(app, "gdpr")  # GDPR data export / account deletion
    _include_optional(app, "embed")  # embeddable widget
    _include_optional(app, "analytics")  # teacher profile analytics

    return app


def _include_optional(app: FastAPI, module_name: str, prefix: str | None = None) -> None:
    """Include a router if its module exists yet (keeps the app bootable
    while features are still being built)."""
    try:
        module = __import__(f"app.routers.{module_name}", fromlist=["router"])
    except ModuleNotFoundError as exc:
        log.error(
            "Failed to load router %s: %s — its endpoints will be unavailable.",
            module_name, exc,
        )
        if settings.DEBUG:
            raise
        return
    if prefix:
        app.include_router(module.router, prefix=prefix)
    else:
        app.include_router(module.router)


app = create_app()


# ── Bulk PDF Ingestor Endpoints ───────────────────────────────────────────
# Add the project root to sys.path so we can import graph.bulk_ingestor
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


try:
    from graph.bulk_ingestor import BulkIngestor
    import shutil
    from pathlib import Path

    @app.post("/upload-bulk")
    async def upload_bulk_pdfs(files: List[UploadFile] = File(...)):
        """Upload multiple PDFs, ingest them into ChromaDB."""
        upload_dir = Path("backend/uploads/pdfs")
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved = []
        for file in files:
            dest = upload_dir / file.filename
            with open(dest, "wb") as f:
                shutil.copyfileobj(file.file, f)
            saved.append(str(dest))
        ingestor = BulkIngestor()
        result = await ingestor.process_pdf_folder(str(upload_dir))
        return result

    @app.get("/ingestor/status")
    def ingestor_status():
        """Return current chunk count in ChromaDB."""
        ingestor = BulkIngestor()
        count = ingestor.collection.count()
        return {"total_chunks_in_chromadb": count}

    log.info("Bulk ingestor endpoints loaded (/upload-bulk, /ingestor/status)")
except Exception as exc:
    log.warning("Bulk ingestor endpoints not loaded: %s", exc)


# ── Concept Extractor Endpoints ──────────────────────────────────────────
try:
    from graph.concept_extractor import ConceptExtractor
    import sqlite3 as _sqlite3

    @app.post("/extract-concepts")
    async def extract_concepts():
        """Run concept extraction on all unprocessed ChromaDB chunks."""
        extractor = ConceptExtractor()
        result = await extractor.process_all_chunks(batch_size=5)
        extractor.merge_duplicate_concepts()
        return result

    @app.get("/concepts/stats")
    def concept_stats():
        """Return concept and relationship counts from SQLite."""
        extractor = ConceptExtractor()
        conn = _sqlite3.connect(extractor.db_path)
        concept_count = conn.execute("SELECT COUNT(*) FROM concepts").fetchone()[0]
        relation_count = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
        top5 = conn.execute(
            "SELECT name, importance_score FROM concepts ORDER BY importance_score DESC LIMIT 5"
        ).fetchall()
        conn.close()
        return {
            "total_concepts": concept_count,
            "total_relationships": relation_count,
            "top_concepts": [{"name": r[0], "importance": r[1]} for r in top5],
        }

    log.info("Concept extractor endpoints loaded (/extract-concepts, /concepts/stats)")
except Exception as exc:
    log.warning("Concept extractor endpoints not loaded: %s", exc)


# ── Knowledge Graph Endpoints ────────────────────────────────────────────
try:
    from graph.graph_service import KnowledgeGraphService

    @app.post("/build-graph")
    def build_graph():
        """Build the NetworkX graph from SQLite concepts & relationships."""
        svc = KnowledgeGraphService()
        G = svc.build_graph_from_db()
        return {"nodes": G.number_of_nodes(), "edges": G.number_of_edges()}

    @app.get("/graph/data")
    def graph_data():
        """Return the full graph as JSON (nodes, edges, stats)."""
        svc = KnowledgeGraphService()
        svc.load_graph()
        return svc.export_graph_json()

    @app.get("/graph/concept/{name}")
    def get_concept(name: str):
        """Return neighbors and prerequisite chain for a concept."""
        svc = KnowledgeGraphService()
        svc.load_graph()
        return {
            "neighbors": svc.get_concept_neighbors(name),
            "prerequisites": svc.get_prerequisite_chain(name),
        }

    @app.get("/graph/top-concepts")
    def top_concepts(n: int = 20):
        """Return top N concepts by importance + centrality."""
        svc = KnowledgeGraphService()
        svc.load_graph()
        return svc.get_top_concepts(n)

    log.info("Knowledge graph endpoints loaded (/build-graph, /graph/data, /graph/concept, /graph/top-concepts)")
except Exception as exc:
    log.warning("Knowledge graph endpoints not loaded: %s", exc)


# ── Curriculum Generator Endpoints ───────────────────────────────────────
try:
    from graph.curriculum_generator import CurriculumGenerator
    import json as _json
    import sqlite3 as _sqlite3_curriculum

    @app.post("/generate-curriculum")
    async def generate_curriculum():
        """Run Louvain community detection + LLM naming to build curriculum."""
        gen = CurriculumGenerator()
        curriculum = await gen.generate_curriculum()
        return {"total_chapters": len(curriculum), "curriculum": curriculum}

    @app.get("/curriculum")
    def get_curriculum():
        """Return the saved curriculum from SQLite."""
        conn = _sqlite3_curriculum.connect("backend/graph_db/ingestor.db")
        rows = conn.execute(
            "SELECT * FROM curriculum ORDER BY chapter_num"
        ).fetchall()
        cols = [
            "id", "chapter_num", "chapter_name", "chapter_description",
            "topic_list", "concept_list", "estimated_hours", "community_id",
        ]
        result = []
        for row in rows:
            d = dict(zip(cols, row))
            d["topic_list"] = _json.loads(d["topic_list"] or "[]")
            d["concept_list"] = _json.loads(d["concept_list"] or "[]")
            result.append(d)
        conn.close()
        return result

    log.info("Curriculum generator endpoints loaded (/generate-curriculum, /curriculum)")
except Exception as exc:
    log.warning("Curriculum generator endpoints not loaded: %s", exc)


# ── Static File Serving ──────────────────────────────────────────────────
os.makedirs("backend/static", exist_ok=True)
from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="backend/static"), name="static")


# ── Graph Visualizer Endpoints ───────────────────────────────────────────
try:
    from graph.graph_visualizer import GraphVisualizer
    import json as _json_viz

    @app.post("/graph/generate-visual")
    def generate_visual():
        """Generate Pyvis HTML and D3 JSON visualizations."""
        viz = GraphVisualizer()
        html_path = viz.generate_pyvis_html()
        d3_data = viz.generate_d3_json()
        return {
            "pyvis_url": "/static/knowledge_map.html",
            "nodes": d3_data["node_count"],
            "edges": d3_data["edge_count"],
        }

    @app.get("/graph/d3-data")
    def d3_data():
        """Return D3-compatible graph JSON."""
        path = "backend/static/graph_data.json"
        if not os.path.exists(path):
            viz = GraphVisualizer()
            return viz.generate_d3_json()
        with open(path) as f:
            return _json_viz.load(f)

    log.info("Graph visualizer endpoints loaded (/graph/generate-visual, /graph/d3-data)")
except Exception as exc:
    log.warning("Graph visualizer endpoints not loaded: %s", exc)


# ── Hybrid Retrieval Endpoint ────────────────────────────────────────────
try:
    from graph.hybrid_retrieval import HybridRetriever

    @app.post("/query-hybrid")
    async def query_hybrid(body: dict):
        """Hybrid retrieval: vector search + graph expansion + prerequisites."""
        query = body.get("query", "")
        if not query:
            return {"error": "No query provided"}
        retriever = HybridRetriever()
        context_data = await retriever.assemble_context(query)
        return context_data

    log.info("Hybrid retrieval endpoint loaded (/query-hybrid)")
except Exception as exc:
    log.warning("Hybrid retrieval endpoint not loaded: %s", exc)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch all unhandled exceptions — never expose internals to client."""
    log.error(
        "Unhandled exception on %s %s: %s: %s\n%s",
        request.method, request.url.path,
        type(exc).__name__, exc, traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return clean validation errors — no internal Python paths."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " → ".join(str(loc) for loc in error["loc"] if loc != "body"),
            "message": error["msg"],
        })
    return JSONResponse(
        status_code=422,
        content={"detail": "Validation failed", "errors": errors},
    )
