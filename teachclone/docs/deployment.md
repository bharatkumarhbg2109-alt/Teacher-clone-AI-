# Deployment

## Local (Docker) — the fast path

```bash
cp .env.example .env          # fill in ANTHROPIC_API_KEY (and OPENAI_API_KEY for embeddings/TTS)
docker compose -f docker/docker-compose.yml up --build
docker compose -f docker/docker-compose.yml exec api python -m scripts.seed_dev
```

- Web: http://localhost:3000 · API docs: http://localhost:8000/docs · MinIO: http://localhost:9001

`DEV_MODE=true` means no Clerk/Stripe needed — the app uses a local dev user.

## Production checklist

1. **Storage** — Cloudflare R2 or AWS S3 bucket; set `S3_*` (endpoint, keys,
   bucket, public URL). Configure CORS to allow the web origin (expose `ETag`
   for multipart uploads).
2. **Auth** — create a Clerk app; set `CLERK_*` and the web publishable key;
   set `DEV_MODE=false`; point the Clerk webhook at `/webhooks/clerk`.
3. **Payments** — create Stripe products (Pro/Creator/Institution); set
   `STRIPE_*` price ids; point the webhook at `/webhooks/stripe`.
4. **Databases** — managed Postgres (Neon/Railway), Redis (Upstash), Qdrant
   (Qdrant Cloud). Set `DATABASE_URL`, `REDIS_URL`, `QDRANT_URL`.
5. **AI** — set `ANTHROPIC_API_KEY`; choose `EMBEDDING_PROVIDER` /
   `TTS_PROVIDER` and their keys.
6. **Migrate** — `alembic revision --autogenerate -m "init" && alembic upgrade head`
   (or rely on dev create-all for the first boot).
7. **Deploy** — API + worker to Railway/Render/Fly (use `docker/Dockerfile.api`
   and `docker/Dockerfile.worker`); web to Vercel (`apps/web`).
8. **Verify** — run `scripts/seed_dev.py`, open the app, create a teacher,
   upload a PDF/link, and chat.

## Scaling notes

- Run multiple worker replicas; long/large media use the `media` queue, AI
  tasks the `ai` queue.
- Whisper model size (`WHISPER_MODEL`) trades speed for accuracy — use
  `small`/`medium` on GPU workers for production.
