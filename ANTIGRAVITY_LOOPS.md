# ANTIGRAVITY_LOOPS.md — 5 Phased Execution Prompts

> **How to use:** Copy-paste **one loop at a time** into your coding agent (Antigravity) as a single prompt.
> Wait for the loop to finish (code written + tests green + committed) before pasting the next.
> Each prompt contains its own self-correction loop: the agent must test, and on failure **diagnose → fix →
> re-test itself (max 3 attempts)** — it must not ask you, and must not proceed with red tests.
> If blocked after 3 attempts, it stops and reports exactly what is blocking.
>
> The prompts are in English intentionally — coding agents follow English instructions most reliably.
> Total: **max 5 loops**. Do not split a loop into sub-loops.

## Global rules (apply to every loop)

1. Before anything else, read `PROJECT_DOC.md` fully. It is the source of truth; code bows to it.
2. Work in the repo root the user opened. Do not create new top-level "Copy" directories.
3. Never commit secrets, API keys, or binary runtime data (`*.db`, `*.sqlite3`, model weights, media files).
4. Never break currently-passing tests. Run the relevant test suite after every change.
5. Small, reviewable commits with clear messages. Commit at the end of each loop.
6. If `PROJECT_DOC.md` contradicts reality, flag it explicitly — do not silently work around it.
7. **Push after every loop.** Each loop ends with `git push` so GitHub stays in sync with local commits.
   If `git push` fails with "no upstream branch", run `git push -u origin HEAD` once, then continue.

---

## LOOP 1 — Resurrect & Boot

**Role:** You are a senior backend engineer. Read `PROJECT_DOC.md` fully first (especially §3, §5, §9, §10).

**Objective:** Make the product (`teacher_project - Copy/`, the SaaS app) boot with all routers registered.
Nothing else matters until `uvicorn app.main:app` starts clean and every feature endpoint is reachable.

**Tasks:**
1. **Recover `app/models/`** (18 SQLAlchemy models). FIRST search the local filesystem for it — it ran on this
   machine before (check the Antigravity workspace, `E:\AI Teacher Clone`, backups, pip caches, anywhere).
   If found: verify it matches the imports in `app/db/base.py` and the routers, then `git add` it.
   If truly lost: rewrite all 18 models from the spec in `app/db/migrations/0001_dna_system.py` + the import
   list in `app/db/base.py`. Every model referenced by any router/service must exist.
2. **Kill silent router drops.** In `apps/api/app/main.py`, `_include_optional()` currently swallows
   `ModuleNotFoundError` when `DEBUG=False`, which is why the API booted as an empty shell with all endpoints
   404ing. Change it so router registration failures **raise loudly** in dev/test (log ERROR and re-raise);
   only in explicit production config may it degrade gracefully, and then it must log a loud warning listing
   exactly which routers were skipped.
3. **Rename** `teacher_project - Copy/` → `teachclone/`. Update every reference: `docker-compose.yml`, docs,
   scripts, and remove the `sys.path` hack in `app/main.py` that imports Project A's `backend/graph/`
   (inline or port whatever it used — do not leave a cross-project import).
4. **Repo hygiene:** add `*.db`, `*.sqlite3`, `chroma/`, `*.bin`, `*.pkl`, `*.graphml`, `dna_reports/*.json`,
   `system_prompts/*`, `uploads/` to `.gitignore`; `git rm --cached` the committed binaries
   (`backend/graph_db/chroma/*`, `*.db` files). Keep `.gitkeep` files so directories still exist on clone.
5. **Fix `start_frontend.bat`** so it launches the product's real frontend wiring (Next.js web app on :3000
   against API :8000), not a mismatched pair. Remove absolute `E:\...` paths; use relative paths.

**Verify (run all):**
- `cd teachclone/apps/api && python -c "from app.main import app; routes=sorted({r.path for r in app.routes}); print(len(routes)); assert len(routes) > 40, routes"` — must print 40+ routes, no exceptions.
- `uvicorn app.main:app --port 8000` boots with no traceback; `curl localhost:8000/health` → 200.
- `curl localhost:8000/dna/health` (or equivalent DNA router health) → reachable, not 404.
- `pytest teachclone/apps/api/tests -x -q` — green (fix or clearly document any pre-existing failure; do not delete failing tests to make them pass).
- `git status` shows no `*.db` / binary files staged.

**Self-heal loop:** After implementing, run the Verify commands. If ANY fail: read the traceback, find the root
cause, fix it, re-run. Repeat until all green or **max 3 fix attempts**. Do not ask the user. Do not move on
with red. If still blocked after 3 attempts: stop, `git stash` nothing, and report exactly which command fails,
the traceback, and what you tried.

**Done when:** API boots clean, 40+ routes registered, health endpoints 200, tests green, no binaries in git.
Then `git add -A && git commit -m "Loop 1: resurrect API — models restored, loud router registration, teachclone rename, repo hygiene" && git push`.

---

## LOOP 2 — Local-first LLM & Media Pipeline

**Role:** You are a senior ML platform engineer. Read `PROJECT_DOC.md` fully first (especially §6, §7.1, §7.2, §10 P0 items 2–3).

**Objective:** The full **video → transcript → teacher DNA** pipeline runs end to end on this machine with
**zero paid API keys**. The product must not depend on Anthropic/OpenAI to function.

**Tasks:**
1. **LLM provider abstraction.** In `teachclone/apps/api/app/services/llm/`, create (or complete) a provider
   interface with at least: `chat(messages, ...)`, `stream_chat(...)`, `embed(texts)`. Implement `OllamaProvider`
   (default; model from env `OLLAMA_MODEL`, default `llama3.1:8b`; host from `OLLAMA_HOST`, default
   `http://localhost:11434`). Keep `AnthropicProvider`/`OpenAIProvider` as optional providers used ONLY when
   their keys are set. Replace every direct Anthropic/paid call in the chat path with the abstraction.
   `claude-opus-4-8` must not be hardcoded anywhere.
2. **One canonical local requirements file.** Merge into a single `requirements.txt` that installs everything
   needed for the local path: `yt-dlp`, `faster-whisper`, `torch` (CPU note), `ffmpeg-python`, plus existing deps.
   Delete or clearly deprecate the fragmented `requirements-local.txt` / `requirements-pinned.txt` duplicates.
   Document ffmpeg system install per OS (Windows/Mac/Linux) in `docs/` and `.env.example` comments.
3. **Wire media → DNA end to end (INLINE_TASKS=true, SQLite, local vectors):**
   `POST /media/youtube` (use a short public test video) → download → audio → faster-whisper transcript →
   `dna_extractor` 7-layer Ollama analysis → DNA report JSON in `dna_reports/` + system prompt in
   `system_prompts/` + stored on the teacher profile. Every stage must log progress; job status endpoint must
   reflect real state (no fake "complete").
4. **TTS graceful degradation:** if no TTS key is configured, chat works without audio (log a warning, return
   text). Piper-local is the default recommendation; document it.

**Verify (run all):**
- `INLINE_TASKS=true uvicorn app.main:app --port 8000` + full pipeline on a real ≤2-minute test video:
  transcript file exists and is non-empty → DNA report JSON exists with all 7 layers populated →
  system prompt file exists and is non-empty → teacher profile shows the DNA.
- `POST /chat/{session_id}/message` with **no** `ANTHROPIC_API_KEY` set returns a streamed answer (Ollama).
- `pytest teachclone/apps/api/tests -x -q` green, including a new `test_llm_provider.py` covering: default is
  Ollama, paid provider used only when key present, no hardcoded model names.

**Self-heal loop:** same as Loop 1 — run Verify; on failure diagnose → fix → re-run, max 3 attempts, then stop
and report precisely. Common traps: whisper model download size (use `tiny`/`base` for the test), ffmpeg missing
from PATH (surface a clear error message telling the user how to install it), Ollama model not pulled
(`ollama pull llama3.1:8b` — print the exact command in the error).

**Done when:** video → DNA works locally with zero paid keys; chat streams via Ollama; tests green.
Then commit and push: `git add -A && git commit -m "Loop 2: local-first LLM provider + media/DNA pipeline runnable with zero paid keys" && git push`.

---

## LOOP 3 — The Vision Loop (DNA → Teacher-styled Answers)

**Role:** You are a senior AI engineer specializing in LLM persona systems. Read `PROJECT_DOC.md` fully first
(especially §1, §7.2, §7.3, §11).

**Objective:** Prove the core vision: a student's doubt gets answered **in their teacher's voice**, grounded in
retrieved content with citations. This is the money loop — protect it with an automated eval.

**Tasks:**
1. **Audit `prompt_builder.py` + chat path** (`POST /chat/{session_id}/message`, SSE). Confirm the built system
   prompt actually contains: the teacher's DNA persona (from Loop 2's system prompt), student level/subject,
   RAG context chunks, and citation rules. Fix any place where the DNA prompt is dropped, truncated, or
   overridden by a generic prompt.
2. **RAG quality:** verify hybrid retrieval returns top-8 relevant chunks; add a distance/score sanity threshold
   so irrelevant chunks don't pollute the answer. Citations `[n]` in the answer must map to real retrieved chunks.
3. **Create the DNA fidelity eval** `teachclone/apps/api/tests/test_dna_fidelity.py` (the most important test in
   the repo): fixture = a sample DNA report + 5 sample student doubts. For each generated answer assert:
   (a) ≥3 of the teacher's signature phrases/patterns from the DNA report appear;
   (b) the answer follows the teacher's explanation structure (from DNA layer 2);
   (c) no generic-chatbot openers (maintain a small denylist, e.g. "As an AI language model").
   The eval must run offline with the local Ollama provider.
4. **Regression-guard `dna_extractor.py`:** do not change its 7-layer logic unless the eval demands it; if you
   touch it, the eval must still pass.

**Verify (run all):**
- `pytest teachclone/apps/api/tests/test_dna_fidelity.py -q` — green (this is the gate).
- Manual SSE check: `POST /chat/{session_id}/message` streams a complete, cited answer; message persisted in DB.
- Full `pytest teachclone/apps/api/tests -x -q` green.

**Self-heal loop:** same as Loop 1 — max 3 diagnose→fix→re-run attempts, then stop and report. If the eval fails
on style (not crashes), iterate on `prompt_builder.py` (stronger persona injection, few-shot examples drawn from
the DNA report, explicit "never break character" instruction) — do not weaken the eval thresholds to make it pass.

**Done when:** fidelity eval green, SSE chat cited + persisted, full suite green.
Then commit and push: `git add -A && git commit -m "Loop 3: teacher-DNA answer transformation with fidelity eval gate" && git push`.

---

## LOOP 4 — Student UX & Consolidation

**Role:** You are a senior full-stack engineer. Read `PROJECT_DOC.md` fully first (especially §4, §5, §8).

**Objective:** A student can complete the whole journey in the web app, and the repo contains exactly **one**
product. Archive the legacy app.

**Tasks:**
1. **Web app wiring** (`teachclone/apps/web`): ensure `NEXT_PUBLIC_API_URL` points at the API via env (no
   hardcoded localhost in prod paths); verify pages work against the Loop-1/2/3 API: onboarding → dashboard →
   `profiles/new` → `profiles/[id]` (DNA report view) → `chat/[sessionId]` (doubt chat, streaming) → quizzes →
   progress. Fix broken API calls, CORS issues, and type errors (`tsc --noEmit` clean).
2. **Full user journey test:** script or document the click-path: create teacher profile → ingest test video →
   DNA generated → open student chat → ask doubt → teacher-styled cited answer streams → generate quiz →
   answer it → XP/progress updates. Every step must work; fix what doesn't.
3. **SM-2 for real:** `FINAL_STATUS.md` claimed an SM-2 scheduler that doesn't exist. Implement the spaced-
   repetition scheduler properly with unit tests, wire it to the review scheduler, or correct the docs to
   remove the claim. No over-claiming.
4. **Consolidation:** move the legacy root app (`backend/`, `frontend/`, `electron/`, root `docker-compose.yml`,
   `.bat` files) into `legacy/` with a `legacy/README.md` saying "archived, not maintained — see teachclone/".
   Update root `README.md` to describe the ONE product and point to `teachclone/`. Delete the triplicated
   vendored JS (keep one copy where it's actually served).

**Verify (run all):**
- `cd teachclone/apps/web && npx tsc --noEmit` clean; `npm run build` succeeds.
- The full user journey (task 2) completes without errors; note the exact steps in `docs/user-journey.md`.
- `pytest teachclone/apps/api/tests -x -q` green (incl. new SM-2 tests).
- Repo has one product: no active code outside `teachclone/` and `legacy/`; root README accurate.

**Self-heal loop:** same as Loop 1 — max 3 attempts, then stop and report.

**Done when:** journey works end to end in the browser, types + tests green, legacy archived, docs accurate.
Then commit and push: `git add -A && git commit -m "Loop 4: student UX journey green, SM-2 real, legacy archived, single product" && git push`.

---

## LOOP 5 — Harden & Ship

**Role:** You are a senior platform/security engineer. Read `PROJECT_DOC.md` fully first (especially §9, §11).

**Objective:** From a **clean clone on a fresh machine**, `docker compose up` yields the working product.
Security basics done. CI green. Docs match reality.

**Tasks:**
1. **Docker end to end:** `teachclone/docker-compose.yml` (api, web, postgres, redis, qdrant, ollama) —
   backend must honor `OLLAMA_HOST` (no hardcoded localhost), frontend served correctly, volumes for data
   (never baked into images), `.dockerignore` excludes binaries/`.git`. Weak defaults removed
   (`POSTGRES_PASSWORD` must come from env, no `teachclone` default).
2. **Security pass:** unauthenticated key-bootstrap endpoints (`/auth/key` style) must be localhost-only or
   removed; rate limiting on chat/media endpoints; no secrets in repo (grep); CORS restricted to the web origin.
3. **CI:** GitHub Actions runs pytest + `tsc --noEmit` + a boot smoke test (import app, 40+ routes, `/health`
   200) on every push. Fix the stale steps (eslint-without-config, dead smoke imports).
4. **Docs sync:** `docs/architecture.md`, `docs/deployment.md`, root `README.md`, and `PROJECT_DOC.md` §5/§6
   must describe the repo as it now is. Delete or correct over-claiming docs (`FINAL_STATUS.md`,
   `DEPLOYMENT_READY.md`, `brain.md` — either verify their claims now or mark them superseded).
5. **Final acceptance:** run the §11 checklist from a clean clone (fresh `git clone` into a temp dir):
   compose up → create profile → ingest sample video → DNA → 5 sample doubts → fidelity eval green →
   pytest green. Record results in `docs/acceptance-2026-10-08.md`.

**Verify (run all):**
- Clean-clone acceptance (§11) all green — this is the ship gate.
- `git log --oneline -5` shows the 5 loop commits; `git status` clean of secrets/binaries.

**Self-heal loop:** same as Loop 1 — max 3 attempts, then stop and report. Docker issues are the usual suspect:
check container logs, env propagation, and volume mounts before changing code.

**Done when:** clean-clone acceptance fully green, CI green, docs synced.
Then commit and push: `git add -A && git commit -m "Loop 5: hardened, dockerized, CI green — clean-clone acceptance passed" && git push`.

---

## After Loop 5

You are done. Write a short `SHIP_REPORT.md` at repo root: what was built, the 5 loop commits, acceptance
results, remaining known limitations, and suggested next features (mobile app, offline mode, more subjects).
Do not start Loop 6.
