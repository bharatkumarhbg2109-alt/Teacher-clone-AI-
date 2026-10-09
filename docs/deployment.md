# TeachClone — Deployment Guide

## 1. Local Development (Docker Compose)

The entire TeachClone stack can be launched via Docker Compose:

```bash
cd teachclone

# Copy and review environment template
cp .env.example .env

# Build and start all services (API, Web, PostgreSQL, Redis, Qdrant, Ollama)
docker compose up --build
```

### Services Available:
- **Web App**: [http://localhost:3000](http://localhost:3000)
- **API Server**: [http://localhost:8000](http://localhost:8000)
- **API Interactive Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **Qdrant Dashboard**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

---

## 2. Local Native Run (Zero Docker, Zero Paid API Keys)

TeachClone runs completely natively without Docker or paid API keys:

### Step 1: Ollama Server
```bash
ollama serve
ollama pull llama3.1:8b
```

### Step 2: FastAPI Backend (`teachclone/apps/api`)
```bash
cd teachclone/apps/api
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

### Step 3: Next.js Frontend (`teachclone/apps/web`)
```bash
cd teachclone/apps/web
npm install
npm run dev
```

---

## 3. Production Deployment Checklist

1. **Database**: Managed PostgreSQL (e.g., Supabase, Neon, AWS RDS). Set `DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname`.
2. **Vectors**: Qdrant Cloud or self-hosted cluster. Set `VECTOR_BACKEND=qdrant`, `QDRANT_URL=https://...`, `QDRANT_API_KEY=...`.
3. **Cache & Queue**: Redis cluster. Set `REDIS_URL=redis://...` and `INLINE_TASKS=false`.
4. **LLM Provider**:
   - Production self-hosted Ollama on GPU instance (`OLLAMA_HOST=...`), or
   - Anthropic (`LLM_PROVIDER=anthropic`, `ANTHROPIC_API_KEY=...`), or
   - OpenAI (`LLM_PROVIDER=openai`, `OPENAI_API_KEY=...`).
5. **Security & Secrets**:
   - `DEV_MODE=false` (enforces full JWT auth via Clerk).
   - Set strong `SECRET_KEY` (32+ random characters).
   - Set `POSTGRES_PASSWORD` securely via environment variables.
   - Restrict `ALLOWED_ORIGINS` to the exact frontend domain (e.g. `https://app.teachclone.com`).
6. **Web App**: Deploy `teachclone/apps/web` to Vercel or containerized with `teachclone/apps/web/Dockerfile`, setting `NEXT_PUBLIC_API_URL`.
