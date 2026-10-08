"""Database and Ollama helper for AI Teacher Clone."""
import os
import sqlite3
import json
import logging
from typing import Optional, List, Dict, Any
import chromadb
import httpx

logger = logging.getLogger("database")

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "graph_db", "ingestor.db")
CHROMA_DIR = os.path.join(BASE_DIR, "graph_db", "chroma")
OLLAMA_MODEL = "llama3.1:8b"
OLLAMA_CHAT_URL = "http://localhost:11434/api/chat"

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
os.makedirs(CHROMA_DIR, exist_ok=True)


def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    """Get SQLite database connection with WAL mode enabled and Row factory."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    """Initialize all SQLite tables for sources, chats, teach sessions, and question practice."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS uploaded_sources (
                  id TEXT PRIMARY KEY,
                  filename TEXT,
                  type TEXT,
                  path TEXT,
                  chunks_count INTEGER DEFAULT 0,
                  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                  id TEXT PRIMARY KEY,
                  chat_id TEXT,
                  role TEXT,
                  content TEXT,
                  attachments TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chats (
                  id TEXT PRIMARY KEY,
                  title TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS teach_sessions (
                    id          TEXT PRIMARY KEY,
                    source_id   TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    topic       TEXT,
                    current_beat INTEGER DEFAULT 0,
                    beats_json  TEXT,
                    status      TEXT DEFAULT 'active',
                    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS question_patterns (
                    id            TEXT PRIMARY KEY,
                    name          TEXT NOT NULL,
                    raw_questions TEXT NOT NULL,
                    pattern_json  TEXT,
                    source_id     TEXT,
                    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS generated_questions (
                    id            TEXT PRIMARY KEY,
                    pattern_id    TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    question_type TEXT,
                    marks         INTEGER DEFAULT 1,
                    difficulty    TEXT DEFAULT 'medium',
                    options_json  TEXT,
                    correct_answer TEXT,
                    explanation   TEXT,
                    user_answer   TEXT,
                    is_correct    INTEGER,
                    attempted_at  DATETIME,
                    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
                );
            """)
    finally:
        conn.close()


init_db()


def get_chroma_collection(collection_name: str = "sources"):
    """Get ChromaDB collection, defaulting to 'sources' with fallback to 'documents'."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        try:
            return client.get_collection(collection_name)
        except Exception:
            try:
                return client.get_collection("sources")
            except Exception:
                return client.get_or_create_collection("documents")
    except Exception as e:
        logger.error(f"Failed to get ChromaDB collection: {e}")
        return None


def get_chroma_context(query: str, source_id: Optional[str] = None, n_results: int = 6) -> str:
    """Retrieve relevant chunks from ChromaDB for the given query, optionally scoped to source_id."""
    try:
        col = get_chroma_collection("sources")
        if not col or col.count() == 0:
            return ""

        query_limit = min(n_results, col.count())
        chunks = []

        # If source_id provided, attempt to filter by file_id first
        if source_id:
            try:
                res = col.query(
                    query_texts=[query],
                    where={"file_id": source_id},
                    n_results=query_limit,
                    include=["documents"]
                )
                if res and res.get("documents") and res["documents"][0]:
                    chunks = res["documents"][0]
            except Exception:
                pass

        # Fallback to query across all chunks if specific filter returned nothing
        if not chunks:
            res = col.query(
                query_texts=[query],
                n_results=query_limit,
                include=["documents"]
            )
            if res and res.get("documents") and res["documents"][0]:
                chunks = res["documents"][0]

        return "\n\n---\n\n".join(chunks) if chunks else ""
    except Exception as e:
        logger.warning(f"[ChromaDB context error] {e}")
        return ""


async def call_ollama(
    messages: List[Dict[str, str]],
    model: str = OLLAMA_MODEL,
    options: Optional[Dict[str, Any]] = None,
    timeout: float = 120.0,
) -> str:
    """Call Ollama LLM chat API using ollama package or httpx fallback."""
    opts = options or {"temperature": 0.7, "num_ctx": 4096}
    try:
        import ollama as ollama_client
        res = ollama_client.chat(model=model, messages=messages, options=opts)
        return res["message"]["content"]
    except (ImportError, Exception):
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                OLLAMA_CHAT_URL,
                json={
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": opts,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")
