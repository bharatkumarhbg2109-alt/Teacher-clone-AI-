"""Verification test script for Chat API and File Upload endpoints."""

import io
import fitz
import docx
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def run_tests():
    # 1. Check OpenAPI /docs endpoints
    schema = app.openapi()
    chat_paths = [p for p in schema["paths"] if p.startswith("/chat")]
    print("=== 1. VERIFY DOCS / ENDPOINTS ===")
    print("Chat paths registered in OpenAPI:", sorted(chat_paths))
    assert "/chat/send" in chat_paths, "Missing /chat/send"
    assert "/chat/upload-source" in chat_paths, "Missing /chat/upload-source"
    assert "/chat/sources" in chat_paths, "Missing /chat/sources"
    assert "/chat/history/{chat_id}" in chat_paths, "Missing /chat/history/{chat_id}"
    print("[OK] All 4 endpoints present in /docs & OpenAPI!")

    # 2. Test PDF upload & ChromaDB chunk indexing
    print("\n=== 2. VERIFY PDF UPLOAD & CHROMADB ===")
    doc = fitz.open()
    page = doc.new_page()
    sample_text = (
        "Kepler's First Law: The orbit of every planet is an ellipse with the Sun at one of the two foci. "
        "This revolutionized astronomy and discarded the ancient model of circular orbits."
    )
    page.insert_text((72, 72), sample_text)
    pdf_bytes = doc.tobytes()
    doc.close()

    r_upload = client.post(
        "/chat/upload-source",
        files={"file": ("kepler_astronomy.pdf", pdf_bytes, "application/pdf")},
    )
    assert r_upload.status_code == 200, f"Upload failed: {r_upload.text}"
    data_upload = r_upload.json()
    print("Upload output:", data_upload)
    file_id = data_upload["file_id"]
    chunks_count = data_upload["chunks_added"]
    assert chunks_count > 0, "No chunks added to ChromaDB"
    print(f"[OK] Chunks added: {chunks_count}, File ID: {file_id}")

    # 3. Test Chat message send with streaming SSE response
    print("\n=== 3. VERIFY CHAT STREAMING WITH OLLAMA ===")
    full_reply = ""
    got_done = False
    chunk_count = 0

    with client.stream(
        "POST",
        "/chat/send",
        json={
            "message": "Explain Kepler's First Law simply in 1 sentence.",
            "file_ids": [file_id],
            "chat_id": "kepler-session-1",
        },
    ) as r_send:
        assert r_send.status_code == 200, f"Send failed: {r_send.status_code}"
        assert "text/event-stream" in r_send.headers.get("content-type", "")
        print("Chat send status: 200, Content-Type: text/event-stream")
        print("Header X-Chat-Id:", r_send.headers.get("X-Chat-Id"))
        print("Header X-Sources-Used:", r_send.headers.get("X-Sources-Used"))

        for line in r_send.iter_lines():
            if not line:
                continue
            if line == "data: [DONE]":
                got_done = True
                break
            if line.startswith("data: "):
                full_reply += line[6:]
                chunk_count += 1
            elif line.startswith("data:"):
                full_reply += line[5:]
                chunk_count += 1

    print(f"Chunks received: {chunk_count}")
    print("Reconstructed reply snippet:\n", full_reply[:200])
    assert got_done, "Stream did not terminate with [DONE]"
    assert len(full_reply) > 0, "Empty reply received"
    assert chunk_count > 1, f"Expected streaming chunks > 1, got {chunk_count}"
    print("[OK] Ollama SSE streaming verified word-by-word with [DONE]!")

    # 4. Verify /chat/sources and /chat/history
    print("\n=== 4. VERIFY SOURCES & HISTORY ===")
    r_sources = client.get("/chat/sources")
    sources_list = r_sources.json()
    print(f"Total sources in SQLite: {len(sources_list)}")
    has_kepler = any(s["filename"] == "kepler_astronomy.pdf" for s in sources_list)
    print("Kepler source found in list:", has_kepler)
    assert has_kepler, "Kepler source missing from /chat/sources"
    print("[OK] Sources endpoint verified!")

    r_hist = client.get("/chat/history/kepler-session-1")
    hist_list = r_hist.json()
    print(f"Messages in chat history: {len(hist_list)}")
    assert len(hist_list) >= 2, "Chat history does not contain user + assistant messages"
    print("[OK] Chat history endpoint verified!")

    print("\n==========================================")
    print("SUCCESS: ALL 4 VERIFICATION CHECKS PASSED!")
    print("==========================================")

if __name__ == "__main__":
    run_tests()
