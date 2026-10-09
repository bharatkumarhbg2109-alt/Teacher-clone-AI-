# TeachClone — Architecture

## Overview

TeachClone turns any teaching material into an authentic, adaptive AI tutor. A **teacher
profile** owns a set of **media sources** (video lectures, audio, PDFs, documents, images).
A 7-layer extraction pipeline analyzes transcripts via local **Ollama** (`llama3.1:8b` by default)
into a structured **DNA report** and compiles a **system prompt**. Media chunks are indexed
into **Qdrant** (or local vector store) with hybrid dense+sparse vectors.

A **student session** carries the learner's grade level, subject, and goals; on every chat
turn the adaptive **prompt builder** fuses the teacher's DNA persona + student calibration +
retrieved knowledge chunks, streaming an in-character answer with inline `[n]` citations.
Inline diagnostic **checkpoints** and the **SM-2 spaced-repetition scheduler** track concept
mastery and schedule reviews over time.

---

## Processing Pipelines

### 1. Ingestion & DNA Extraction Pipeline
```
Media Input (YouTube / Audio / Video / Docs)
     │
     ├──► yt-dlp & ffmpeg (16kHz mono normalization)
     │
     ├──► faster-whisper (transcription with timestamps)
     │
     ├──► 7-Layer Teacher DNA Extractor (Ollama llama3.1:8b)
     │       ├─ Layer 1: Vocabulary & Code-Switching DNA
     │       ├─ Layer 2: Explanation Structure & Sequence
     │       ├─ Layer 3: Example Sources & Contexts
     │       ├─ Layer 4: Socratic Questioning Habits
     │       ├─ Layer 5: Error Correction & Guidance
     │       ├─ Layer 6: Topic Transition Markers
     │       └─ Layer 7: Emotional Tone & Energy
     │       ▼
     │    DNA Report JSON (`dna_reports/`) + System Prompt (`system_prompts/`)
     │
     └──► Hybrid Embeddings (Dense + Sparse) ──► Qdrant / Local Vector Store
```

### 2. Doubt-Solving & Spaced Repetition Loop
```
Student Question (Level, Subject, Goals)
     │
     ├──► Hybrid Retrieval (Top-8 Chunks with RAG_MIN_SCORE threshold)
     │
     ├──► Prompt Builder (DNA Persona + Citations [n] + Socratic Ending)
     │
     ├──► LLM Provider (Ollama default; optional Anthropic / OpenAI)
     │       ▼
     │    Real-time SSE Token Stream (`event: token`) ──► Assistant Message Persisted
     │
     └──► Checkpoints & SM-2 Retention
             ├─ Dynamic Checkpoint Generation (`POST /sessions/{id}/checkpoint`)
             ├─ Performance Evaluation & Level Adaptation (`deeper` / `hold` / `reteach`)
             ├─ SM-2 Spaced Repetition (`easiness`, `interval`, `repetitions`, `next_review_date`)
             └─ Gamification Engine (XP, Levels, Badges, Streaks)
```

---

## Components

| Layer | Technology | Role |
|---|---|---|
| **Web** | Next.js 14, TypeScript, Tailwind | App Router with SSE streaming chat, teacher discovery, quizzes, progress |
| **API** | FastAPI, SQLAlchemy 2.0 async | 19 routers, 25 services, loud router registration |
| **LLM** | Provider abstraction (Ollama default) | Local-first `llama3.1:8b`; optional Claude/OpenAI when keys set |
| **Audio / STT** | yt-dlp + ffmpeg + faster-whisper | Audio extraction and timestamped transcription |
| **Vectors** | Qdrant (prod) / local vector backend (dev) | Hybrid dense+sparse search, isolated per teacher |
| **Database** | SQLite (local dev) / PostgreSQL (prod) | 18 SQLAlchemy async models |
| **Spaced Repetition** | SuperMemo SM-2 (1987) | Concept mastery tracking, easiness factor, interval review worker |
| **Security & Auth** | Clerk (prod) / DEV_MODE local user (dev) | Rate limiting, CORS origin restrictions, localhost-only key endpoints |
| **Tasks** | INLINE_TASKS (local dev) / Redis + Celery (prod) | Background processing |

---

## Data Model (18 Models)

- `users` · `user_stats` · `user_badges` · `organizations` · `org_members` · `api_keys`
- `teacher_profiles` · `teacher_shares` · `dna_reports`
- `media_sources` · `transcript_chunks` · `processing_jobs`
- `student_sessions` · `messages` · `quizzes`
- `audit_logs` · `usage_logs` · `review_tasks`
