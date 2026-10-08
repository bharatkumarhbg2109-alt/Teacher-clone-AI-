# TeachClone — Adaptive AI Teacher (SaaS)

An AI teacher that ingests **any** material (video, video link, audio, PDF, docs, images — of any size),
clones the reference teacher's **style**, and teaches students **adaptively by grade level and subject**,
in **text or audio**. Students with no material of their own can learn from **popular teachers**, and can
**share a customized teacher via a link** (the shared teacher carries its full knowledge, style and voice).
Coaching institutes can embed it in their own student apps.

## Highlights

- **Any input, any size** — YouTube/links, video, audio, PDF, DOCX, PPTX, images (OCR); resumable uploads; chunked processing for multi-hour media.
- **Style cloning** — extracts a teacher's tone, pacing, vocabulary, analogy density and signature phrases.
- **Grade + subject calibration** — Class 6-8 → 9-10 → 11-12 (+ stream) → Graduation → Post-grad → Working professional, for **any subject**, with an optional **"learn ahead"** switch. Feeds the right depth — not too much, not too little.
- **Text and audio** — streaming chat, voice input, and audio answers (per-teacher voice).
- **Inline checkpoints** — quick mid-lecture quizzes that make the teacher adapt (simpler / deeper / re-teach) and build a per-concept mastery map with spaced repetition.
- **Popular-teacher fallback** — a directory of the most-used public teachers.
- **Shareable teachers** — one link shares a customized teacher (clone or read-only), preserving its memory.
- **SaaS platform** — multi-tenant orgs, admin analytics, Stripe billing, public REST API + API keys, and an embeddable widget for institutes.
- **Gamification & enterprise** — XP/streaks/badges/leaderboards, SSO, audit logs, GDPR.

## Architecture

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 (App Router, TypeScript, Tailwind, shadcn/ui) |
| Backend | FastAPI (Python 3.11, async SQLAlchemy 2.0), Celery workers |
| LLM / vision / PDF | Ollama (local llama3.1:8b by default) / Claude / OpenAI |
| Speech-to-text | faster-whisper (local) |
| Embeddings | OpenAI `text-embedding-3-large` or local BGE |
| Audio output (TTS) | OpenAI TTS / ElevenLabs / local Piper |
| Vector DB | Qdrant (hybrid dense + sparse) |
| Data / queue / cache | PostgreSQL, Redis + Celery |
| Object storage | Cloudflare R2 / S3 (prod), MinIO (local) |
| Auth / Payments | Clerk / Stripe (with a local no-account dev mode) |

## Local development

```bash
# 1. Copy env and fill in at least ANTHROPIC_API_KEY
cp .env.example .env

# 2. Boot the whole stack (Postgres, Redis, Qdrant, MinIO, API, worker, web)
docker compose -f docker/docker-compose.yml up --build

# 3. Run DB migrations (first time)
docker compose -f docker/docker-compose.yml exec api alembic upgrade head

# 4. Seed a demo teacher + user
docker compose -f docker/docker-compose.yml exec api python -m scripts.seed_dev
```

- Web: http://localhost:3000
- API docs: http://localhost:8000/docs
- MinIO console: http://localhost:9001

In `DEV_MODE=true` the API bypasses Clerk and uses a local dev user, so M0–M2 run with **only** an Anthropic key.

## Monorepo layout

```
apps/
  web/     Next.js 14 frontend
  api/     FastAPI backend (routers, services, models, tasks, worker)
packages/
  types/   Shared TypeScript types (@teachclone/types)
docker/    docker-compose + Dockerfiles
docs/      Architecture & deployment docs (+ original spec)
scripts/   Dev utilities (seed, qdrant bootstrap)
```

See `docs/architecture.md` for the full design.
