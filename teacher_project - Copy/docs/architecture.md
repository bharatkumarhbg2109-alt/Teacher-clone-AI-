# TeachClone — Architecture

## Overview

TeachClone turns any teaching material into an adaptive AI tutor. A **teacher
profile** owns a set of **media sources** (links, videos, audio, PDFs, docs,
images). A background pipeline transcribes/extracts them into **chunks**, embeds
them into **Qdrant**, and extracts a **style profile**. A **student session**
carries the learner's grade level, subject and pace; on every chat turn the
adaptive **prompt builder** fuses the cloned style + the student's calibration +
retrieved knowledge, and Claude streams a level-appropriate answer with
citations (and optional audio). Inline **checkpoints** close the loop — the
teacher goes simpler / deeper / re-teaches based on the student's answers.

## Pipeline

```
Input ─► normalize ─► extract ───────────────► chunk ─► embed ─► Qdrant
        (link/file)   audio: whisper                     (dense+sparse hybrid)
                      docs:  PyMuPDF/docx/pptx/OCR
                      video: keyframes ─► Claude vision
                                        │
                                        └► style extraction ─► StyleProfile

Chat: student(level+subject+pace) ─► retrieve ─► build_system_prompt ─► Claude
         ▲                                                                │
         └──────────── checkpoint result adapts level/mastery ◄──────────┘
```

## Components

| Layer | Tech | Notes |
|---|---|---|
| Web | Next.js 14 (App Router) | Client-side app; dev-mode needs no auth |
| API | FastAPI (async SQLAlchemy 2.0) | Routers → services → models |
| Worker | Celery + Redis | Ingestion + AI tasks (media, doc, embed, style, vision, clone) |
| LLM/vision/PDF | Claude `claude-opus-4-8` | Streaming chat, structured JSON, vision, native PDF |
| STT | faster-whisper | Local, any length |
| Embeddings | OpenAI or local BGE | `EMBEDDING_PROVIDER` |
| TTS | OpenAI / ElevenLabs / Piper | `TTS_PROVIDER` |
| Vectors | Qdrant | Hybrid dense+sparse, isolated per teacher |
| Data | PostgreSQL | 16 tables |
| Storage | S3/R2/MinIO | Presigned single + multipart (any size) |

## Data model (key tables)

users · organizations · org_members · teacher_profiles · teacher_shares ·
media_sources · transcript_chunks · processing_jobs · student_sessions ·
messages · quizzes · api_keys · audit_logs · user_stats · user_badges ·
usage_logs.

## Adaptive engine

- **Grade ladder** (`services/levels.py`): `class_6_8 → class_9_10 → class_11_12
  → undergrad → postgrad → professional`, each with vocabulary/depth guidance.
- **Learn-ahead**: raises the effective teaching level above the stated one.
- **Checkpoints**: `submit_checkpoint` scores answers, updates per-concept
  mastery (spaced review), and steps the effective level up/down.

## Sharing & discovery

- Every teacher can be **public** (listed in `/discover`), **unlisted** (link
  only), or **private**.
- A share link (`/t/{token}`) opens a teacher in **view** mode (learn from the
  original) or **clone** mode (fork a personal copy; a background task copies the
  knowledge base and re-embeds it under the fork). Popularity
  (`unique_learners`, `session_count`) powers the "most used" ranking.

## Security notes

- `DEV_MODE` bypasses Clerk for local dev only. Set it false + configure Clerk
  for production.
- Vector search always filters by `teacher_profile_id` (no cross-teacher leak).
- Share links are owner-controlled and revocable.
