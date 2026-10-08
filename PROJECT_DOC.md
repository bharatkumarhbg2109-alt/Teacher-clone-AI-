# PROJECT_DOC.md — AI Teacher Clone ("TeachClone")

> **How to use this document (for AI coding agents):** This is the single source of truth for this repository.
> Read it fully before writing any code. It defines the product vision, the architecture decision,
> the repo map, the core pipelines, conventions, and the definition of done. If code contradicts this
> document, fix the code — not the document. If the document is wrong, say so explicitly and propose
> the correction instead of silently working around it.

---

## 1. Vision

**One-line:** Every student gets answers in *their own class teacher's* voice, language, and explanation style — not generic AI answers.

**The problem:** When students study online and get a doubt, they can only clear it in a live class with their teacher.
Otherwise they use Google or AI chatbots. Those give raw, general explanations that don't match *how their teacher
explains*. Result: the doubt is "answered" but not 100% cleared, because the teacher's way of explaining —
their examples, their step-by-step approach, their language — is missing.

**The solution (3 stages):**
1. **Ingest** the teacher's videos (YouTube link or file upload) → transcribe them.
2. **Extract the teacher's "DNA"** — teaching style, speech patterns, problem-solving approach, explanation patterns,
   signature phrases, difficulty calibration — into a structured DNA report, then compile it into a system prompt.
3. **Transform** any raw/general answer (from search or an LLM) into the teacher's context and language, so the
   student receives the answer *as their teacher would have explained it*.

**The human teacher is the reference point for the entire product.** Every design decision should be justifiable
as "this makes the output closer to what the student's real teacher would say."

---

## 2. Target users & customers

| Segment | Who | How they use it |
|---|---|---|
| Students (primary user) | School / high-school / college / tuition students, online **and** offline | Ask doubts in chat, get teacher-styled answers, practice questions, track progress |
| Teachers / institutes (customer) | Schools, colleges, tuition centres, coaching institutes | Upload their lecture videos, get their "teacher clone" (DNA profile), share with students |
| Parents / admins | Institute owners | Dashboard, usage analytics, billing |

---

## 3. Architecture decision (binding)

A full audit (2026-10-08) found **two separate products** in this repo:

| | `backend/` + `frontend/` + `electron/` (repo root) | `teacher_project - Copy/` |
|---|---|---|
| What it is | Single-user local RAG tutor (PDF Q&A, teach mode, quizzes, knowledge graph) | Multi-tenant SaaS implementing the **full vision**: video ingestion → teacher DNA extraction → teacher-styled answers |
| LLM | Ollama (local, free) | DNA pipeline: Ollama (local). Chat: Anthropic Claude (paid) |
| Boot state | Boots (needs Ollama) | **Broken as committed** — `app/models/` (18 SQLAlchemy models) was never committed; all feature routers 404 |

**Decision: the SaaS codebase (`teacher_project - Copy/`) is THE product.** It contains ~70% of the vision in real,
working code (video pipeline, 7-layer DNA extractor, style-transforming chat). The root app is a generic PDF tutor
with no teacher-DNA concept at all.

**Consolidation plan (execute in this order):**
1. Rename `teacher_project - Copy/` → `teachclone/` (the "- Copy" name is tech debt; update all path references,
   `docker-compose.yml`, docs, and the `sys.path` hack in `apps/api/app/main.py` that imports from the root backend).
2. Restore `app/models/` (see §10.1 — check the author's local disk first; it ran there).
3. Make the LLM layer **provider-pluggable with Ollama as default** (local-first; paid providers optional) so the
   full loop works with zero API cost. See §7.
4. Fix Docker Compose so `docker compose up` works end to end (Ollama host env, route coverage, no committed binaries).
5. Move the root `backend/`+`frontend/`+`electron/` app to `legacy/` (or an archive branch) once the SaaS app is
   green. Do **not** maintain both. Do **not** delete until the SaaS app demonstrably covers its useful features
   (RAG chat, question practice, knowledge graph).

---

## 4. System architecture (the product)

```
┌─────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│  Teacher    │      │  Media pipeline  │      │  DNA pipeline       │
│  uploads    │─────▶│  yt-dlp → ffmpeg │─────▶│  faster-whisper     │
│  video/URL  │      │  (audio extract) │      │  transcript         │
└─────────────┘      └──────────────────┘      └─────────┬───────────┘
                                                       ▼
                                              ┌─────────────────────┐
                                              │  dna_extractor.py   │
                                              │  7-layer Ollama     │
                                              │  analysis           │
                                              └─────────┬───────────┘
                                                        ▼
                                              ┌─────────────────────┐
                                              │  DNA report (JSON)  │
                                              │  + generated system │
                                              │  prompt             │
                                              └─────────┬───────────┘
                                                        ▼
┌─────────────┐      ┌──────────────────┐      ┌─────────────────────┐
│  Student    │      │  Chat pipeline   │◀─────│  prompt_builder.py  │
│  asks doubt │─────▶│  RAG retrieve    │      │  DNA persona + RAG  │
│             │      │  → LLM (Ollama)  │      │  context + citation │
│             │      │  → SSE stream    │      │  rules              │
└─────────────┘      └──────────────────┘      └─────────────────────┘
```

**Core services** (`teachclone/apps/api/app/services/`):
- `audio_extractor.py`, `transcriber.py` — video → audio → transcript (yt-dlp, ffmpeg, faster-whisper)
- `dna_extractor.py` (1119 lines) — 7-layer Ollama analysis → DNA report; `dna_system.py` — DNA jobs/state
- `prompt_builder.py` — builds the teacher-persona system prompt (DNA + student level/subject + RAG context + citation rules)
- `llm/` — LLM provider abstraction (**must support Ollama; Anthropic/OpenAI optional**)
- `vector_store.py` (+ local fallback), `embedder.py` — RAG retrieval
- `quiz_generator.py`, `review scheduler / SM-2`, `gamification.py` — practice & retention
- `tts_service.py` — text-to-speech (OpenAI/ElevenLabs/Piper; optional, degrades gracefully)
- `billing.py`, `organizations`, `share`, `embed`, `analytics`, `gdpr` — SaaS surface

**Frontend** (`teachclone/apps/web`, Next.js + TypeScript): landing, onboarding, dashboard,
`profiles/[id]` (teacher DNA profile), `chat/[sessionId]` (student doubt chat), discover, progress, orgs, admin,
embeddable widget (`public/teachclone-widget.js`).

---

## 5. Repository map (after consolidation)

```
Teacher-clone-AI-/
├── PROJECT_DOC.md            ← this file (repo root)
├── ANTIGRAVITY_LOOPS.md       ← phased execution prompts for the coding agent
├── teachclone/                ← THE product (renamed from "teacher_project - Copy")
│   ├── apps/api/              ← FastAPI :8000
│   │   ├── app/main.py        ← create_app(), router registration (NO silent drops — see §9)
│   │   ├── app/config.py      ← pydantic-settings; all secrets from env, never hardcoded
│   │   ├── app/models/        ← 18 SQLAlchemy models (MUST exist — see §10.1)
│   │   ├── app/routers/       ← 19 routers (auth, profiles, media, dna_*, chat, quizzes, …)
│   │   ├── app/services/      ← 25 services (DNA, media, LLM, RAG, TTS, billing, …)
│   │   ├── app/db/            ← base.py, session.py, migrations/ (alembic)
│   │   ├── app/schemas/       ← Pydantic request/response models
│   │   ├── app/tasks/         ← background jobs (INLINE_TASKS=true for local dev)
│   │   ├── tests/             ← pytest suite (must stay green)
│   │   └── requirements*.txt  ← ONE canonical requirements file for local dev
│   ├── apps/web/              ← Next.js :3000 (NEXT_PUBLIC_API_URL → API)
│   ├── packages/types/        ← shared types
│   ├── docker-compose.yml     ← api, web, postgres, redis, qdrant, ollama
│   └── docs/                  ← architecture.md, deployment.md (kept in sync)
└── legacy/                    ← old root app (backend/frontend/electron), archived, not maintained
```

---

## 6. Tech stack (canonical)

| Layer | Choice |
|---|---|
| API | FastAPI 0.111+, Uvicorn, Pydantic v2, sse-starlette (streaming chat) |
| DB | SQLAlchemy 2.0 async; **SQLite** for local dev (`DATABASE_URL=sqlite+aiosqlite:///./teachclone.db`), PostgreSQL in prod; Alembic migrations |
| Vectors | Qdrant (prod) / file-local backend (dev); embeddings: local model first, OpenAI optional, deterministic-hash fallback for tests |
| Media | yt-dlp → ffmpeg → faster-whisper (CPU-friendly default; document GPU option) |
| LLM | **Provider abstraction, Ollama default** (`llama3.1:8b`; vision optional). Anthropic/OpenAI supported via env keys but never required |
| DNA extraction | Ollama, 7-layer analysis (see §7.2) |
| TTS | Piper (local, default) / OpenAI / ElevenLabs (optional) |
| Auth | Clerk (prod) / DEV_MODE local user (dev); JWT |
| Billing | Stripe (routers + webhooks; stub-safe in dev) |
| Web | Next.js (TypeScript), `NEXT_PUBLIC_API_URL` env-driven (no hardcoded localhost in prod paths) |
| Infra | Docker Compose; GitHub Actions CI (pytest + typecheck + smoke boot) |

---

## 7. Core pipelines (must keep working)

### 7.1 Media ingestion
`POST /media/youtube` or file upload → yt-dlp download → ffmpeg audio extraction → faster-whisper
transcription → transcript stored, linked to `MediaSource` → triggers DNA extraction job.
Background tasks run inline when `INLINE_TASKS=true` (local dev), via Celery+Redis in prod.

### 7.2 Teacher DNA extraction (the crown jewel — do not regress)
`dna_extractor.py`: 7-layer Ollama analysis of the transcript producing a DNA report covering —
1. speech & language patterns (vocabulary level, signature phrases, code-switching e.g. Hinglish),
2. explanation structure (how answers are built: hook → steps → example → recap),
3. problem-solving approach (how the teacher attacks a question),
4. pedagogical moves (analogies, mnemonics, checks for understanding),
5. tone & persona (strict/friendly/motivational),
6. difficulty calibration (how they simplify vs challenge),
7. subject-specific patterns.
Output: DNA report JSON (`dna_reports/`) + compiled system prompt (`system_prompts/`), stored on the teacher profile.
**Any change here must be validated against the DNA eval (see §11).**

### 7.3 Doubt-solving chat (the money loop)
`POST /chat/{session_id}/message` (SSE) → quota check → RAG retrieve (top-8 chunks, hybrid) →
`prompt_builder.build_system_prompt()` (DNA persona + student level/subject + RAG context + citation rules) →
LLM streams answer → `[n]` citations parsed → message persisted → optional TTS → usage/XP logged.
**The answer must read as the teacher, not as a generic chatbot.** Raw/general knowledge is only the *input*;
the teacher's DNA is the *transformation*.

### 7.4 Practice & retention
`quiz_generator` → quizzes from DNA + curriculum; SM-2 spaced-repetition scheduler; gamification (XP, streaks).

---

## 8. Key API surface

- `GET /health` — liveness (must not require DB/models)
- `/profiles` — teacher profiles (create, get, list); DNA report & system prompt attached
- `/media/*` — youtube ingest, file upload, job status
- `/dna/*` — extract-from-url, extract-from-file, regenerate, status, jobs, report, system-prompt, logs
- `/sessions`, `/chat/{session_id}/message` (SSE) — student sessions & doubt chat
- `/quizzes`, `/voice` (TTS), `/share`, `/discover`, `/embed`, `/analytics`, `/billing`, `/organizations`, `/export`, `/gdpr`, `/v1`

---

## 9. Coding conventions & guardrails (for agents)

1. **No silent failures.** The `_include_optional()` pattern that swallowed `ModuleNotFoundError` caused months of
   "it doesn't work" with zero errors. Router/service registration failures must **raise loudly** in dev/test.
   Catch-and-log is allowed only at the outer edge with a clear ERROR log line.
2. **Env-driven config.** All secrets/URLs/model names come from `app/config.py` (pydantic-settings). No hardcoded
   `localhost` in backend code — read `OLLAMA_HOST`-style env vars with sensible local fallbacks.
3. **One product.** Don't add features to `legacy/`. Don't create new top-level "Copy" directories. Ever.
4. **No binaries in git.** Runtime data (`*.db`, `chroma.sqlite3`, `*.bin`, `*.pkl`, `*.graphml`, model weights,
   `dna_reports/` outputs) is gitignored. Seed data lives in `tests/fixtures/`.
5. **Tests stay green.** `pytest` suite + the DNA eval + boot smoke test must pass before any commit.
6. **Migrations for schema changes.** Never hand-edit the dev SQLite file as "the fix" — write an Alembic migration.
7. **Small, reviewable commits** with messages describing *why*, not just *what*.

---

## 10. Known issues backlog (from 2026-10-08 audit — fix in Loop order, §12)

### P0 — product is dead until fixed
1. **`app/models/` missing from git** (18 SQLAlchemy models; ~20 routers import them). → Check the author's local
   disk first (it ran there — likely `E:\AI Teacher Clone\...` or the Antigravity workspace); if found, commit it.
   If lost, rewrite from `app/db/migrations/0001_dna_system.py` + the import list in `app/db/base.py`.
2. **Chat hard-requires paid `ANTHROPIC_API_KEY`** (`claude-opus-4-8`). → Make LLM provider-pluggable, Ollama default.
3. **Video/DNA pipeline unrunnable in local mode**: `requirements-local.txt` omits `yt-dlp`, `faster-whisper`,
   `torch`, and ffmpeg isn't documented. → One canonical requirements file; document ffmpeg install per OS.

### P1 — broken workflows / hygiene
4. `start_frontend.bat` launches the wrong frontend (Next.js :3000 instead of the product's web app wiring).
5. 22MB+ committed binaries (`chroma.sqlite3`, `ingestor.db`, `teachclone.db`, …) → gitignore + untrack.
6. Cross-project `sys.path` hack in `main.py` importing Project A's `backend/graph/` → remove after consolidation.
7. `FINAL_STATUS.md` over-claims (SM-2 scheduler file doesn't exist) → implement SM-2 for real with tests, or correct docs.
8. Weak default `POSTGRES_PASSWORD: teachclone` in compose; unauthenticated key endpoints must be localhost-only.

### P2 — polish
9. nginx/route coverage gaps; hardcoded `http://localhost:8002` in frontend clients → env-driven `NEXT_PUBLIC_API_URL`.
10. Vendored JS triplicated; dead deps; Electron spawns system python without recovery (legacy — low priority).

---

## 11. Definition of done (acceptance criteria for the whole program)

The program is done when, **from a clean clone on a fresh machine**:
1. `docker compose up` (or the documented local path: `uvicorn` + `npm run dev` + `ollama serve`) brings up API + web with zero manual fixes.
2. A teacher profile is created; a sample lecture video/URL is ingested; a DNA report + system prompt is generated.
3. A student asks 5 sample doubts; **all 5 answers are judged teacher-styled** by the DNA eval script
   (checks: signature phrases/patterns from the DNA report present; explanation structure matches the teacher's;
   no generic-chatbot phrasing), with correct RAG citations.
4. `pytest` fully green; boot smoke test passes; CI green.
5. No secrets in repo; no binaries in git; docs (`docs/architecture.md`, this file) match reality.

**DNA eval script** (`apps/api/tests/test_dna_fidelity.py` — create if missing): given a fixture DNA report and
sample Q&A, assert the generated answer contains ≥3 of the teacher's signature patterns and follows the teacher's
explanation structure. This is the automated guardian of the vision — the single most important test in the repo.

---

## 12. Roadmap → agent loops

Execution is split into **5 sequential loops** (see `ANTIGRAVITY_LOOPS.md`). Each loop is copy-pasted to the coding
agent as one prompt; the agent implements, tests, self-fixes (max 3 attempts), and commits before the next loop:

1. **Loop 1 — Resurrect & Boot:** restore `app/models/`, kill silent router drops, rename to `teachclone/`,
   repo hygiene (gitignore binaries), fix `.bat` scripts. Done when API boots with all routers registered.
2. **Loop 2 — Local-first LLM & media pipeline:** provider abstraction (Ollama default), canonical requirements,
   video → transcript → DNA runs end to end locally with zero paid keys.
3. **Loop 3 — The vision loop:** DNA → prompt_builder → chat transformation; DNA fidelity eval; SSE chat green.
4. **Loop 4 — Student UX & consolidation:** web app wired to working API, full user journey (profile → video →
   DNA → doubt → teacher-styled answer → quiz), SM-2 real, legacy archived.
5. **Loop 5 — Harden & ship:** security pass, `docker compose up` from clean clone, CI green, docs synced,
   final acceptance (§11) all green.

---

## 13. Glossary

- **Teacher DNA**: structured profile of *how* a teacher teaches (style, speech, solving approach, explanation
  patterns) — extracted from videos, stored as JSON, compiled into a system prompt.
- **DNA report**: the JSON artifact of extraction (`dna_reports/`).
- **Transformation**: the step where a raw/general answer is rewritten into the teacher's voice via the DNA system prompt.
- **INLINE_TASKS**: dev mode where background jobs run synchronously (no Celery/Redis needed).
- **Legacy**: the old root `backend/`+`frontend/`+`electron/` app — archived, not maintained.
