# TeachClone — How to Start

Two servers must run. Start the **backend first**, then the **frontend**.
Easiest: double-click `start_backend.bat`, then `start_frontend.bat`.

## Backend (FastAPI → http://localhost:8000)
```bat
cd "E:\AI Teacher Clone\teacher_project - Copy\apps\api"
"C:\Users\bhara\anaconda3\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Health check: open http://localhost:8000/health → `{"status":"ok",...}`

## Frontend (Next.js → http://localhost:3000)
```bat
cd "E:\AI Teacher Clone\teacher_project - Copy\apps\web"
npm run dev
```
Open http://localhost:3000  ·  Admin dashboard: http://localhost:3000/admin

## Notes
- The backend runs on the **Anaconda** Python (`C:\Users\bhara\anaconda3\python.exe`),
  which has every dependency installed. The bundled `apps/api/.venv` is broken
  and should not be used.
- Local "no-infra" mode is on (`INLINE_TASKS=true`, SQLite, local storage/vectors),
  so **no Docker, Redis, or Qdrant is required**. Media ingestion runs in-process.
- Adding a YouTube link downloads + transcribes the audio inline, so the request
  can take 30–90 s for a short video before it shows as **Ready**.
- If the browser shows an unexpected 404 on a page that should exist, the Next
  dev cache is stale: stop the frontend, delete `apps/web/.next`, and run
  `npm run dev` again.

## What was fixed (see FIX_REPORT.txt for detail)
Missing Python packages (`sse_starlette`, `anthropic`, `qdrant_client`, `celery`,
`yt_dlp`) were causing whole API routers to be silently dropped → the frontend's
"Add YouTube" call hit a non-existent route and showed **"Not Found"**. Those
packages are now installed (with pinned compatible versions), Celery is
configured for Redis-free in-process tasks, and yt-dlp is invoked in a
PATH-independent way.
