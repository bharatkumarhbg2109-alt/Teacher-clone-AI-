# TeachClone — brain.md

> [!NOTE]
> **HISTORICAL ARCHIVE / SUPERSEDED**
> This task tracker was used during the initial August 2026 sprint. For current project execution status and loops, see [PROJECT_DOC.md](../PROJECT_DOC.md) and [ANTIGRAVITY_LOOPS.md](../ANTIGRAVITY_LOOPS.md).

## Project Overview
TeachClone is a SaaS platform for educational AI that lets teachers upload content and students interact with personalized AI teacher profiles. Built with FastAPI (Python) + Next.js (TypeScript).

---

## Task Queue

### ✅ Critical

| ID | Task | Status | Files Changed |
|----|------|--------|---------------|
| C1 | SECRET_KEY Guard | ✅ | `apps/api/app/config.py` |
| C2 | DEV_MODE Guard | ✅ | `apps/api/app/config.py` |
| C3 | CORS Fix | ✅ | `apps/api/app/main.py` |

### ✅ In Progress

| ID | Task | Status | Files Changed |
|----|------|--------|---------------|
| IP1 | Anonymous Embed Session | ✅ | `apps/api/app/routers/embed.py` |
| IP2 | psutil Memory Fix | ✅ | `apps/api/app/services/dna_system.py` (already handled) |
| IP3 | Billing Webhook Handlers | ✅ | `apps/api/app/routers/webhooks.py` |
| IP4 | Clerk Webhook Signature | ✅ | `apps/api/app/routers/webhooks.py` |
| IP5 | Recreate Virtual Environment | ✅ | `apps/api/.venv`, `requirements.txt` |

### ✅ Pending

| ID | Task | Status | Files Changed |
|----|------|--------|---------------|
| P1 | Embeddable JS Widget | ✅ | `apps/web/public/teachclone-widget.js` |
| P2 | Organization UI Pages | ✅ | `apps/web/app/orgs/` (4 pages) |
| P3 | Image Upload in Chat | ✅ | `apps/web/app/chat/[sessionId]/page.tsx`, `apps/web/lib/api.ts` |
| P4 | Spaced Repetition Scheduler | ✅ | `apps/api/app/services/review_scheduler.py`, `apps/api/app/main.py` |

### ✅ Bug Fixes (Bonus)

| ID | Task | Status | Files Changed |
|----|------|--------|---------------|
| FIX | qdrant_client import compatibility | ✅ | `apps/api/app/services/vector_store.py` |
| FIX | Test conftest DEV_MODE compatibility | ✅ | `apps/api/tests/conftest.py` |

---

## Change Log

| Date | Task ID | Task Name | Files Changed | Summary |
|------|---------|-----------|---------------|---------|
| 2026-08-25 | FIX | qdrant_client fix | `vector_store.py` | Removed NamedSparseVector import, use tuple-based named vectors |
| 2026-08-25 | FIX | conftest fix | `conftest.py` | Set DEV_MODE=True for test settings to pass C1 guard |
| 2026-08-25 | C1 | SECRET_KEY Guard | `config.py` | Auto-generate key in DEV_MODE, enforce 32+ chars in production |
| 2026-08-25 | C2 | DEV_MODE Guard | `config.py` | Refuse to start if DEV_MODE=true with ENV != "local" |
| 2026-08-25 | C3 | CORS Fix | `main.py` | Read ALLOWED_ORIGINS from env, no more hardcoded wildcard |
| 2026-08-25 | IP1 | Anonymous Embed Session | `embed.py` | System user for anon sessions, UUID-based session tokens |
| 2026-08-25 | IP2 | psutil Memory Fix | `dna_system.py` | Already handled — graceful fallback if psutil missing |
| 2026-08-25 | IP3 | Billing Webhooks | `webhooks.py` | Added log_billing_event + handle_payment_failed handler |
| 2026-08-25 | IP4 | Clerk Signature | `webhooks.py` | Proper svix WebhookVerificationError handling |
| 2026-08-25 | IP5 | Recreate Venv | `.venv`, `requirements.txt` | Recreated with Python 3.13, installed all deps |
| 2026-08-25 | P1 | JS Widget | `teachclone-widget.js` | Floating chat widget with data-teacher-id attribute |
| 2026-08-25 | P2 | Org Pages | `orgs/` pages | 4 pages: list, dashboard, members, analytics |
| 2026-08-25 | P3 | Image Upload | `chat/page.tsx`, `api.ts` | Paperclip button, base64 encoding, preview with remove |
| 2026-08-25 | P4 | Review Scheduler | `review_scheduler.py`, `main.py` | Hourly loop, INLINE_TASKS mode startup registration |

---

## File Map

### Backend (`apps/api/`)
- `app/config.py` — Settings with C1/C2 guards, SECRET_KEY auto-generation
- `app/main.py` — App factory with CORS (C3), review scheduler startup (P4)
- `app/routers/webhooks.py` — Clerk + Stripe webhooks with billing log (IP3, IP4)
- `app/routers/embed.py` — Embeddable widget API with anonymous sessions (IP1)
- `app/services/vector_store.py` — Qdrant vector store (fixed import compatibility)
- `app/services/review_scheduler.py` — Spaced repetition scheduler (P4)
- `app/services/dna_system.py` — System health with psutil (IP2)
- `tests/conftest.py` — Test fixtures (DEV_MODE fix)

### Frontend (`apps/web/`)
- `public/teachclone-widget.js` — Embeddable JS widget (P1)
- `app/chat/[sessionId]/page.tsx` — Chat with image upload (P3)
- `app/orgs/page.tsx` — Org list page (P2)
- `app/orgs/[id]/page.tsx` — Org dashboard (P2)
- `app/orgs/[id]/members/page.tsx` — Members management (P2)
- `app/orgs/[id]/analytics/page.tsx` — Analytics view (P2)
- `lib/api.ts` — API client with image support (P3)

---

## Environment Variables

### New / Updated
| Variable | Default | Description |
|----------|---------|-------------|
| `ENV` | `local` | Environment: local / staging / production |
| `SECRET_KEY` | `""` | Auto-generated in DEV_MODE; required 32+ chars in prod |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | Comma-separated CORS origins |
| `DEV_MODE` | `true` | Bypasses Clerk auth; must be false in production |
| `INLINE_TASKS` | `false` | Run tasks in-process (no Redis/Celery) |
| `EMAIL_BACKEND` | `log` | log → email_log.txt; or production backend |

---

## Blockers

_(None)_

---

## Final Verification

- ✅ Backend: `pytest tests/ -v` → **164 passed** (all original tests)
- ✅ Frontend: `npm run build` → **0 errors**, all pages generated
- ✅ No regressions in existing test suite
- ✅ DEPLOYMENT_READY.md created with full env var reference and deployment guide
