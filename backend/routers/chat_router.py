"""Chat and Source Upload Router for AI Teacher Clone."""

import json
import logging
import os
import re
import shutil
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

import chromadb
from fastapi import APIRouter, File, HTTPException, UploadFile
import httpx
from pydantic import BaseModel

try:
    import fitz  # PyMuPDF
except ImportError:
    try:
        import pymupdf as fitz
    except ImportError:
        fitz = None

try:
    import docx
except ImportError:
    docx = None

logger = logging.getLogger("chat_router")

router = APIRouter()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "graph_db", "ingestor.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads", "sources")
CHROMA_DIR = os.path.join(BASE_DIR, "graph_db", "chroma")
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.1:8b"

# Ensure upload directory exists
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)


def init_chat_tables(db_path: str = DB_PATH) -> None:
    """Initialize SQLite tables for sources, chats, and chat messages."""
    conn = sqlite3.connect(db_path, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
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
    finally:
        conn.close()


# Ensure tables are initialized when module is loaded
init_chat_tables()


def get_chroma_collection(collection_name: str = "sources"):
    """Get or create ChromaDB collection, defaulting to 'sources'."""
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
        logger.error(f"Failed to initialize ChromaDB collection: {e}")
        return None


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> List[str]:
    """Split text into chunks of chunk_size characters with overlap."""
    if not text:
        return []
    chunks = []
    start = 0
    text_len = len(text)
    step = max(1, chunk_size - overlap)
    while start < text_len:
        end = min(start + chunk_size, text_len)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start += step
    return chunks


METADATA_PATTERNS = [
    # Hindi/Hinglish inventory questions
    r"\bkitn[ei|i]\s+(?:pdf|file|document|kitab|page|paper)",
    r"\bmere\s+paas\s+kitn",
    r"\bkaun\s+kaun\s+s[ei]\s+(?:pdf|file|document|topic)",
    r"\bkya\s+kya\s+upload",
    r"\bkons[ei]\s+(?:pdf|file|document)",
    r"\bkya\s+upload\s+(?:kiya|hai|hua)",
    r"\bshow\s+all\s+(?:pdf|file|document)",
    r"\blist\s+(?:all\s+)?(?:pdf|file|document|source)",
    r"\blist\s+my\s+(?:pdf|file|document|source)",
    r"\ball\s+(?:pdf|file|document)s?\b",
    # English inventory questions
    r"\bhow\s+many\s+(?:pdf|file|document|source|paper)",
    r"\btotal\s+(?:pdf|file|document|source|paper)",
    r"\bcount\s+of\s+(?:pdf|file|document|source)",
    r"\bwhat\s+(?:pdf|file|document)s?\s+(?:do\s+i\s+have|are\s+uploaded|exist)",
    r"\bwhich\s+(?:pdf|file|document)s?\s+(?:do\s+i\s+have|are\s+uploaded|are\s+available)",
    r"\bshow\s+my\s+(?:pdf|file|document|source|library)",
    r"\bmy\s+(?:pdf|file|document|source)s?\s+list\b",
]


def is_metadata_query(message: str) -> bool:
    """Check if user query is asking about uploaded files / inventory instead of topic content."""
    msg = message.strip().lower()
    for pattern in METADATA_PATTERNS:
        if re.search(pattern, msg):
            return True
    return False


def get_metadata_answer(message: str, db_path: str = DB_PATH) -> str:
    """Query SQLite database for exact uploaded sources count and metadata."""
    msg = message.strip().lower()
    total_count = 0
    sources = []
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        with conn:
            rows = conn.execute(
                "SELECT filename, type, uploaded_at, chunks_count FROM uploaded_sources ORDER BY uploaded_at DESC"
            ).fetchall()
            sources = [dict(r) for r in rows]
            total_count = len(sources)
        conn.close()
    except Exception as e:
        logger.error(f"Error reading sources metadata: {e}")
        return "Library details retrieve karne mein dikkat aayi. Kripya dobara try karein."

    list_keywords = ["list", "kaun kaun", "kya kya", "names", "naam", "show", "konsi", "which"]
    wants_list = any(kw in msg for kw in list_keywords)

    if wants_list:
        if total_count == 0:
            return "Aapke library mein abhi koi PDF ya document uploaded nahi hai."

        display_limit = 30
        display_sources = sources[:display_limit]
        file_lines = [
            f"{i+1}. **{s['filename']}** ({s.get('chunks_count', 0)} chunks)"
            for i, s in enumerate(display_sources)
        ]
        list_text = "\n".join(file_lines)
        if total_count > display_limit:
            remaining = total_count - display_limit
            list_text += f"\n\n*...aur {remaining} files library mein available hain.*"

        return (
            f"Aapke library mein total **{total_count} files** uploaded hain:\n\n"
            f"{list_text}\n\n"
            "Aap inme se kisi bhi topic ya document ke baare mein pooch sakte hain!"
        )
    else:
        return (
            f"Aapke library mein total **{total_count} PDF/documents** uploaded hain. "
            "Aap inme se kisi bhi topic ya file ke baare mein sawal pooch sakte hain!"
        )


class ChatRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None
    file_ids: Optional[List[str]] = []
    use_rag: bool = True
    collection: str = "sources"
    stream: bool = False


# Backward compatibility alias
ChatSendRequest = ChatRequest


from fastapi.responses import StreamingResponse


@router.get("/sources/stats")
def get_sources_stats() -> Dict[str, Any]:
    """Return comprehensive statistics about uploaded sources and ChromaDB indexing health."""
    total_uploaded = 0
    recent_uploads = []
    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        with conn:
            total_uploaded = conn.execute("SELECT COUNT(*) FROM uploaded_sources").fetchone()[0]
            recent_rows = conn.execute(
                "SELECT filename, type, uploaded_at, chunks_count FROM uploaded_sources ORDER BY uploaded_at DESC LIMIT 5"
            ).fetchall()
            recent_uploads = [dict(r) for r in recent_rows]
        conn.close()
    except Exception as e:
        logger.error(f"Error fetching source stats from SQLite: {e}")

    total_chunks = 0
    try:
        col = get_chroma_collection("sources")
        if col:
            total_chunks = col.count()
    except Exception as e:
        logger.error(f"Error fetching ChromaDB chunk count: {e}")

    chunks_per_pdf = round(total_chunks / total_uploaded, 2) if total_uploaded > 0 else 0.0
    indexing_health = "good" if chunks_per_pdf >= 2.0 else "needs_reindex"

    return {
        "status": "ok",
        "total_pdfs_uploaded": total_uploaded,
        "total_chunks_indexed": total_chunks,
        "chunks_per_pdf": chunks_per_pdf,
        "indexing_health": indexing_health,
        "recent_uploads": recent_uploads,
    }


@router.get("/test-rag")
async def test_rag(query: str = "transfer learning"):
    """Debug endpoint — test if RAG retrieval is working."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        try:
            col = client.get_collection("sources")
        except Exception:
            col = client.get_collection("documents")

        results = col.query(
            query_texts=[query],
            n_results=3,
            include=["documents", "metadatas", "distances"],
        )
        chunks = results["documents"][0] if results.get("documents") else []
        metadatas = results["metadatas"][0] if results.get("metadatas") else []

        formatted_results = []
        for doc, meta in zip(chunks, metadatas):
            src = meta.get("filename") or meta.get("source") or meta.get("pdf_name", "unknown")
            if "_" in src and len(src.split("_")[0]) in [32, 36]:
                src = "_".join(src.split("_")[1:])
            formatted_results.append({
                "source": src,
                "preview": doc[:300],
            })

        return {
            "status": "ok",
            "query": query,
            "chunks_found": len(chunks),
            "collection_size": col.count(),
            "results": formatted_results,
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/send")
async def send_chat(req: ChatRequest):
    """Process user message, retrieve context from ChromaDB via RAG pipeline,

    query Ollama with rich system prompt and history, and persist to SQLite.
    Returns JSON by default or StreamingResponse if stream=True.
    """
    chat_id = req.chat_id or str(uuid.uuid4())
    message = req.message.strip()
    file_ids = req.file_ids or []

    # ── STEP 0: Metadata / Inventory Intent Detection ──────────────────────
    if is_metadata_query(message):
        meta_reply = get_metadata_answer(message, DB_PATH)
        # Persist conversation to SQLite
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            with conn:
                cursor = conn.execute("SELECT id FROM chats WHERE id = ?", (chat_id,))
                if not cursor.fetchone():
                    chat_title = message[:30] if message else "New Chat"
                    conn.execute(
                        "INSERT INTO chats (id, title) VALUES (?, ?)",
                        (chat_id, chat_title),
                    )
                conn.execute(
                    """INSERT INTO chat_messages (id, chat_id, role, content, attachments)
                       VALUES (?, ?, ?, ?, ?)""",
                    (str(uuid.uuid4()), chat_id, "user", message, json.dumps(file_ids)),
                )
                conn.execute(
                    """INSERT INTO chat_messages (id, chat_id, role, content, attachments)
                       VALUES (?, ?, ?, ?, ?)""",
                    (str(uuid.uuid4()), chat_id, "assistant", meta_reply, "[]"),
                )
            conn.close()
        except Exception as db_err:
            logger.error(f"Failed to persist metadata chat messages in SQLite: {db_err}")

        if req.stream:
            async def meta_stream():
                for line in meta_reply.split("\n"):
                    yield f"data: {line}\n\n"
                yield "data: [DONE]\n\n"

            return StreamingResponse(
                meta_stream(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Chat-Id": chat_id,
                    "X-Sources-Used": "[]",
                    "X-Rag-Active": "false",
                    "X-Is-Metadata": "true",
                },
            )

        return {
            "response": meta_reply,
            "sources_used": [],
            "rag_active": False,
            "is_metadata": True,
            "chat_id": chat_id,
        }

    # ── STEP 1: ChromaDB retrieval ─────────────────────────────────────────
    context_text = ""
    source_files = []

    if req.use_rag:
        t0 = time.perf_counter()
        try:
            target_collection_name = req.collection or "sources"
            collection = get_chroma_collection(target_collection_name)
            if collection and collection.count() > 0:
                query_kwargs = {
                    "query_texts": [message],
                    "n_results": min(5, collection.count()),
                    "include": ["documents", "metadatas", "distances"],
                }
                if file_ids:
                    query_kwargs["where"] = (
                        {"file_id": file_ids[0]}
                        if len(file_ids) == 1
                        else {"file_id": {"$in": file_ids}}
                    )

                results = collection.query(**query_kwargs)

                chunks = results.get("documents", [[]])[0] if results.get("documents") else []
                metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
                distances = results.get("distances", [[]])[0] if results.get("distances") else []

                # Filter out low-relevance chunks (distance > 1.5 means poor match)
                relevant = [
                    (doc, meta, dist)
                    for doc, meta, dist in zip(chunks, metadatas, distances)
                    if dist < 1.5
                ]

                # Fallback to top chunks if strict threshold filtered everything
                if not relevant and chunks:
                    relevant = list(zip(chunks, metadatas, distances))[:2]

                if relevant:
                    context_parts = []
                    for i, (doc, meta, dist) in enumerate(relevant, 1):
                        source_name = (
                            meta.get("filename")
                            or meta.get("source")
                            or meta.get("pdf_name")
                            or f"Source {i}"
                        )
                        # Strip uuid prefix if present (e.g. 36-char uuid + _)
                        if "_" in source_name and len(source_name.split("_")[0]) in [32, 36]:
                            clean_name = "_".join(source_name.split("_")[1:])
                        else:
                            clean_name = source_name

                        if clean_name not in source_files:
                            source_files.append(clean_name)
                        
                        is_visual = meta.get("type") == "image" or any(clean_name.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"])
                        prefix = f"[Visual Source {i} (Image): {clean_name}]" if is_visual else f"[Source {i}: {clean_name}]"
                        context_parts.append(f"{prefix}\n{doc}")
                    context_text = "\n\n---\n\n".join(context_parts)
                logger.info(
                    "RAG retrieval complete",
                    extra={"latency_ms": round((time.perf_counter() - t0) * 1000), "chunks": len(relevant) if 'relevant' in locals() else 0},
                )
        except Exception as e:
            logger.warning(f"[RAG WARNING] ChromaDB query failed: {e}")
            context_text = ""

    # ── STEP 2: Build system prompt ────────────────────────────────────────
    total_uploaded_count = 0
    try:
        conn = sqlite3.connect(DB_PATH, timeout=10.0)
        total_uploaded_count = conn.execute("SELECT COUNT(*) FROM uploaded_sources").fetchone()[0]
        conn.close()
    except Exception:
        pass

    if context_text:
        system_prompt = f"""You are an expert AI Teacher helping a student learn from their uploaded study materials.

IMPORTANT FACTS YOU KNOW:
- The student has uploaded {total_uploaded_count} files/PDFs total in their library.
- Below are the most relevant excerpts retrieved from their uploaded study materials for this query.

INSTRUCTIONS:
- Answer using the provided context from the student's study materials
- Explain concepts clearly with examples, analogies, and step-by-step breakdowns
- If the student asks in Hindi/Hinglish, respond in the same language naturally
- Always cite which source/PDF your answer is based on
- If the answer is NOT in the provided context, say: "Yeh topic aapke uploaded materials mein nahi mila, lekin main general knowledge se bata sakta hun: ..." and then answer briefly
- Never make up facts that aren't in the context

CONTEXT FROM UPLOADED PDFs:
{context_text}

Remember: You are teaching this student. Be encouraging, clear, and thorough."""
    else:
        system_prompt = f"""You are an expert AI Teacher. 
The student has uploaded {total_uploaded_count} files/PDFs in their library, but no specific matching context was found for this query.
Answer from your general knowledge but tell the student:
"Main aapke uploaded PDFs mein yeh specifically nahi dhundh paya. General knowledge se bata raha hun:"
Be helpful, clear, and encouraging."""

    # ── STEP 3: Build message history for context window ──────────────────
    ollama_messages = [{"role": "system", "content": system_prompt}]

    try:
        conn = sqlite3.connect(DB_PATH, timeout=30.0)
        conn.row_factory = sqlite3.Row
        with conn:
            recent_messages = conn.execute(
                """SELECT role, content FROM chat_messages 
                   WHERE chat_id = ? 
                   ORDER BY created_at DESC LIMIT 6""",
                (chat_id,),
            ).fetchall()

            for msg in reversed(recent_messages):
                ollama_messages.append({"role": msg["role"], "content": msg["content"]})
        conn.close()
    except Exception as e:
        logger.warning(f"[HISTORY WARNING] Could not load chat history: {e}")

    ollama_messages.append({"role": "user", "content": message})

    # ── Non-streaming mode (default: stream=False) ──────────────────────────
    if not req.stream:
        ai_reply = ""
        try:
            try:
                import ollama as ollama_client
                res = ollama_client.chat(
                    model=OLLAMA_MODEL,
                    messages=ollama_messages,
                    options={
                        "temperature": 0.7,
                        "num_ctx": 4096,
                        "top_p": 0.9,
                    },
                )
                ai_reply = res["message"]["content"]
            except (ImportError, Exception):
                async with httpx.AsyncClient(timeout=120.0) as client:
                    chat_resp = await client.post(
                        "http://localhost:11434/api/chat",
                        json={
                            "model": OLLAMA_MODEL,
                            "messages": ollama_messages,
                            "stream": False,
                            "options": {
                                "temperature": 0.7,
                                "num_ctx": 4096,
                                "top_p": 0.9,
                            },
                        },
                    )
                    chat_resp.raise_for_status()
                    data = chat_resp.json()
                    ai_reply = data.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"[OLLAMA ERROR] {e}")
            ai_reply = "Sorry, model se response nahi mila. Kripya dobara try karein."

        # STEP 5: Save to SQLite
        try:
            conn = sqlite3.connect(DB_PATH, timeout=30.0)
            conn.execute("PRAGMA journal_mode=WAL")
            with conn:
                cursor = conn.execute("SELECT id FROM chats WHERE id = ?", (chat_id,))
                if not cursor.fetchone():
                    chat_title = message[:30] if message else "New Chat"
                    conn.execute(
                        "INSERT INTO chats (id, title) VALUES (?, ?)",
                        (chat_id, chat_title),
                    )

                user_msg_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO chat_messages (id, chat_id, role, content, attachments)
                       VALUES (?, ?, ?, ?, ?)""",
                    (user_msg_id, chat_id, "user", message, json.dumps(file_ids)),
                )

                asst_msg_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO chat_messages (id, chat_id, role, content, attachments)
                       VALUES (?, ?, ?, ?, ?)""",
                    (asst_msg_id, chat_id, "assistant", ai_reply, json.dumps(source_files)),
                )
            conn.close()
        except Exception as db_err:
            logger.error(f"Failed to persist chat messages in SQLite: {db_err}")

        # STEP 6: Return response
        return {
            "response": ai_reply,
            "sources_used": list(dict.fromkeys(source_files)),
            "rag_active": bool(context_text),
            "chat_id": chat_id,
        }

    # ── Streaming mode (stream=True) ───────────────────────────────────────
    async def event_generator():
        full_reply_parts = []
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream(
                    "POST",
                    "http://localhost:11434/api/chat",
                    json={
                        "model": OLLAMA_MODEL,
                        "messages": ollama_messages,
                        "stream": True,
                        "options": {
                            "temperature": 0.7,
                            "num_ctx": 4096,
                            "top_p": 0.9,
                        },
                    },
                ) as response:
                    if response.status_code != 200:
                        err_bytes = await response.aread()
                        err_msg = err_bytes.decode("utf-8", errors="ignore")
                        logger.error(f"Ollama stream error {response.status_code}: {err_msg}")
                        yield f"data: Ollama error ({response.status_code}): {err_msg}\n\n"
                        yield "data: [DONE]\n\n"
                        return

                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except Exception:
                            continue

                        chunk = data.get("message", {}).get("content", "")
                        if chunk:
                            full_reply_parts.append(chunk)
                            lines = chunk.split("\n")
                            sse_message = "\n".join([f"data: {l}" for l in lines]) + "\n\n"
                            yield sse_message

                        if data.get("done", False):
                            break

        except httpx.TimeoutException:
            logger.error("Ollama streaming timed out")
            yield "data: Response timed out. Please retry.\n\n"
        except Exception as e:
            logger.error(f"Ollama streaming failed: {e}")
            yield f"data: AI Teacher error: {str(e)}\n\n"
        finally:
            yield "data: [DONE]\n\n"

            # Save to SQLite database
            full_reply = "".join(full_reply_parts).strip()
            if full_reply:
                try:
                    conn = sqlite3.connect(DB_PATH, timeout=30.0)
                    conn.execute("PRAGMA journal_mode=WAL")
                    with conn:
                        cursor = conn.execute("SELECT id FROM chats WHERE id = ?", (chat_id,))
                        if not cursor.fetchone():
                            chat_title = message[:30] if message else "New Chat"
                            conn.execute(
                                "INSERT INTO chats (id, title) VALUES (?, ?)",
                                (chat_id, chat_title),
                            )

                        user_msg_id = str(uuid.uuid4())
                        conn.execute(
                            """INSERT INTO chat_messages (id, chat_id, role, content, attachments)
                               VALUES (?, ?, ?, ?, ?)""",
                            (user_msg_id, chat_id, "user", message, json.dumps(file_ids)),
                        )

                        asst_msg_id = str(uuid.uuid4())
                        conn.execute(
                            """INSERT INTO chat_messages (id, chat_id, role, content, attachments)
                               VALUES (?, ?, ?, ?, ?)""",
                            (asst_msg_id, chat_id, "assistant", full_reply, json.dumps(source_files)),
                        )
                    conn.close()
                except Exception as db_err:
                    logger.error(f"Failed to persist chat messages in SQLite: {db_err}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Chat-Id": chat_id,
            "X-Sources-Used": json.dumps(list(dict.fromkeys(source_files))),
            "X-Rag-Active": "true" if context_text else "false",
        },
    )


@router.post("/upload-source")
async def upload_source(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Save uploaded source file, extract text (PDF/DOCX), chunk and store in ChromaDB,

    and record in SQLite.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename missing")

    file_id = str(uuid.uuid4())
    original_filename = file.filename
    clean_filename = os.path.basename(original_filename)
    ext = os.path.splitext(clean_filename)[1].lower().lstrip(".")
    saved_filename = f"{file_id}_{clean_filename}"
    saved_path = os.path.join(UPLOAD_DIR, saved_filename)

    # 1. Save file to backend/uploads/sources/{uuid}_{filename}
    try:
        with open(saved_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        logger.error(f"File save error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

    # 2. Extract text based on file type
    chunks = []
    file_type = ext

    if ext == "pdf":
        file_type = "pdf"
        if fitz:
            try:
                doc = fitz.open(saved_path)
                full_text = ""
                for page in doc:
                    page_text = page.get_text()
                    if len(page_text.strip()) < 20:
                        try:
                            tp = page.get_textpage_ocr(language="eng")
                            ocr_text = page.get_text(textpage=tp)
                            if len(ocr_text.strip()) > len(page_text.strip()):
                                page_text = ocr_text
                        except Exception:
                            pass
                    full_text += page_text + "\n"
                doc.close()
                chunks = chunk_text(full_text, chunk_size=800, overlap=150)
            except Exception as e:
                logger.error(f"PDF extraction error: {e}")
        else:
            logger.warning("fitz (PyMuPDF) is not installed; PDF text not extracted")

    elif ext in ["docx", "doc"]:
        file_type = "docx"
        if docx and ext == "docx":
            try:
                doc = docx.Document(saved_path)
                full_text = "\n".join([p.text for p in doc.paragraphs if p.text])
                chunks = chunk_text(full_text, chunk_size=800, overlap=150)
            except Exception as e:
                logger.error(f"DOCX extraction error: {e}")
        else:
            logger.warning("python-docx not available or file is .doc binary")

    elif ext in ["png", "jpg", "jpeg", "webp", "gif", "bmp"]:
        file_type = "image"
        from routers.vision import is_image, describe_image

        visual_context = ""
        if is_image(str(saved_path)):
            visual_context = await describe_image(
                image_path=str(saved_path),
                user_prompt="Extract all educational content, text, diagrams, and data from this image.",
            )
            if visual_context and not visual_context.startswith("[Vision"):
                chunk_text_content = f"[IMAGE CONTENT — {clean_filename}]\n{visual_context}"
                chunks = chunk_text(chunk_text_content, chunk_size=800, overlap=150)
            else:
                chunks = [f"[IMAGE SOURCE — {clean_filename}]"]

    # 3. Add to ChromaDB collection "sources"
    chunks_added = 0
    if chunks:
        collection = get_chroma_collection("sources")
        if collection:
            try:
                chunk_ids = [f"{file_id}_chunk_{i}" for i in range(len(chunks))]
                metadatas = [
                    {
                        "file_id": file_id,
                        "source_id": file_id,
                        "filename": original_filename,
                        "source": original_filename,
                        "type": file_type,
                        "chunk_idx": i,
                        "filepath": saved_path,
                    }
                    for i in range(len(chunks))
                ]
                collection.add(
                    documents=chunks,
                    metadatas=metadatas,
                    ids=chunk_ids,
                )
                chunks_added = len(chunks)
            except Exception as e:
                logger.error(f"ChromaDB insert error: {e}")

    # 4. Save to SQLite table "uploaded_sources"
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        with conn:
            conn.execute(
                """INSERT INTO uploaded_sources (id, filename, type, path, chunks_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (file_id, original_filename, file_type, saved_path, chunks_added),
            )
    except Exception as e:
        logger.error(f"SQLite insert error for uploaded source: {e}")
        raise HTTPException(status_code=500, detail=f"Database record failed: {str(e)}")
    finally:
        conn.close()

    return {
        "file_id": file_id,
        "name": original_filename,
        "type": file_type,
        "chunks_added": chunks_added,
    }


@router.get("/sources")
def get_sources() -> List[Dict[str, Any]]:
    """Return list of all uploaded sources from SQLite table 'uploaded_sources'."""
    if not os.path.exists(DB_PATH):
        return []

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        rows = conn.execute(
            """SELECT id, filename, type, uploaded_at, chunks_count
               FROM uploaded_sources
               ORDER BY uploaded_at DESC"""
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching uploaded sources: {e}")
        return []
    finally:
        conn.close()


@router.get("/history/{chat_id}")
def get_history(chat_id: str) -> List[Dict[str, Any]]:
    """Return list of messages from SQLite table 'chat_messages' for a chat_id."""
    if not os.path.exists(DB_PATH):
        return []

    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        rows = conn.execute(
            """SELECT id, chat_id, role, content, attachments, created_at
               FROM chat_messages
               WHERE chat_id = ?
               ORDER BY created_at ASC""",
            (chat_id,),
        ).fetchall()

        history = []
        for r in rows:
            item = dict(r)
            att_val = item.get("attachments")
            if isinstance(att_val, str):
                try:
                    item["attachments"] = json.loads(att_val)
                except Exception:
                    item["attachments"] = []
            else:
                item["attachments"] = []
            history.append(item)
        return history
    except Exception as e:
        logger.error(f"Error fetching chat history: {e}")
        return []
    finally:
        conn.close()


@router.post("/new")
def create_new_chat() -> Dict[str, Any]:
    """Create a new chat session."""
    new_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        with conn:
            conn.execute("INSERT INTO chats (id, title) VALUES (?, ?)", (new_id, "New Chat"))
        return {"chat_id": new_id, "id": new_id, "title": "New Chat"}
    except Exception as e:
        logger.error(f"Error creating chat: {e}")
        return {"chat_id": new_id, "id": new_id, "title": "New Chat"}
    finally:
        conn.close()


@router.get("/chats")
def get_chats() -> List[Dict[str, Any]]:
    """Return all chat sessions."""
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        rows = conn.execute("SELECT id, title, created_at FROM chats ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error fetching chats: {e}")
        return []
    finally:
        conn.close()


@router.delete("/sources/{source_id}")
def delete_source(source_id: str) -> Dict[str, Any]:
    """Delete an uploaded source from database."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        with conn:
            conn.execute("DELETE FROM uploaded_sources WHERE id = ?", (source_id,))
        return {"status": "ok", "deleted": source_id}
    except Exception as e:
        logger.error(f"Error deleting source: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()


@router.delete("/{chat_id}")
def delete_chat(chat_id: str) -> Dict[str, Any]:
    """Delete a chat and its messages."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        with conn:
            conn.execute("DELETE FROM chat_messages WHERE chat_id = ?", (chat_id,))
            conn.execute("DELETE FROM chats WHERE id = ?", (chat_id,))
        return {"status": "ok", "deleted": chat_id}
    except Exception as e:
        logger.error(f"Error deleting chat: {e}")
        return {"status": "error", "message": str(e)}
    finally:
        conn.close()

