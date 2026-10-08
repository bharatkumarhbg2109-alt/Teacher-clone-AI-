# TeachClone 🎓🤖

**TeachClone** is an end-to-end AI Teacher platform that clones real educators' authentic teaching voices, pedagogies, and explanation habits using a 7-layer Teacher DNA extraction pipeline, grounded by hybrid vector RAG retrieval with citations, adaptive checkpoint quizzes, and SM-2 spaced repetition retention scheduling.

> **One Product Architecture**: The primary production codebase lives in **[`teachclone/`](./teachclone/)**. The previous desktop prototype has been archived in **[`legacy/`](./legacy/)**.

---

## 🌟 Core Highlights

- **7-Layer Teacher DNA Extraction**: Analyzes lecture transcripts to extract vocabulary habits, explanation progression, example sources, Socratic questioning, error-correction patterns, transition markers, and emotional tone.
- **Zero Paid API Keys Required**: Operates completely local-first with **Ollama** (`llama3.1:8b`) as the default LLM provider, with optional Anthropic/OpenAI keys only when explicitly configured.
- **DNA Persona Fidelity**: Strictly preserves teacher persona in student doubt chat; verified by automated DNA fidelity evals ensuring $\ge 3$ signature phrases, Layer 2 explanation structure, and zero generic bot boilerplate.
- **SM-2 Spaced Repetition Scheduler**: Canonical SuperMemo SM-2 algorithm scheduling concept reviews, tracking easiness factors, repetition counts, intervals, and mastery scores.
- **Grounded RAG with Citations**: Hybrid dense + sparse vector search with relevance score filtering, producing verifiable `[n]` bracketed citations in streaming answers.
- **Modern Web App**: Next.js 14 + TypeScript frontend (`teachclone/apps/web`) with real-time SSE streaming chat, teacher discovery, interactive quizzes, and gamified progress tracking.

---

## 📁 Repository Structure

```text
Teacher-clone-AI-/
├── PROJECT_DOC.md            # Comprehensive project documentation & requirements
├── docs/                     # End-to-end user journey & guides
│   └── user-journey.md       # Complete 8-stage student & educator click-path
├── teachclone/               # THE PRODUCT
│   ├── apps/
│   │   ├── api/              # FastAPI backend (:8000)
│   │   │   ├── app/main.py   # Application entrypoint & loud router registration
│   │   │   ├── app/models/   # 18 SQLAlchemy async models
│   │   │   ├── app/routers/  # 19 API routers (chat, DNA, media, quizzes, profiles, etc.)
│   │   │   ├── app/services/ # Core services (LLM, DNA extractor, prompt builder, SM-2)
│   │   │   ├── tests/        # 245+ pytest tests (incl. DNA fidelity eval & SM-2)
│   │   │   └── requirements.txt # Unified local requirements (torch, faster-whisper, yt-dlp)
│   │   └── web/              # Next.js 14 web frontend (:3000)
│   │       ├── app/          # App router pages (chat, onboarding, dashboard, quizzes)
│   │       ├── components/   # UI components
│   │       └── lib/          # API & SSE streaming client
│   ├── docs/                 # Architecture & deployment specifications
│   └── docker-compose.yml    # Containerized production stack
└── legacy/                   # Archived prototype (backend, frontend, electron — not maintained)
```

---

## 🚀 Quick Start (Local Development)

### Prerequisites
1. **Ollama**: Installed and running with `llama3.1:8b`:
   ```bash
   ollama serve
   ollama pull llama3.1:8b
   ```
2. **FFmpeg**: Installed on system PATH (see [`teachclone/docs/ffmpeg_setup.md`](./teachclone/docs/ffmpeg_setup.md)).
3. **Python 3.11+** & **Node.js 18+**.

---

### 1. Backend Setup (`teachclone/apps/api`)

```bash
cd teachclone/apps/api

# Create & activate virtual environment
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start backend server on port 8000
uvicorn app.main:app --port 8000 --reload
```

- **Health check**: `curl http://localhost:8000/health` $\rightarrow$ `{"status":"ok"}`
- **Interactive OpenAPI docs**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

### 2. Frontend Setup (`teachclone/apps/web`)

```bash
cd teachclone/apps/web

# Install dependencies
npm install

# Start Next.js development server on port 3000
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the web application.

---

## 🧪 Verification & Testing

### Backend Test Suite (Pytest)
```bash
cd teachclone/apps/api
pytest tests -x -q
```
- Includes all unit tests, error handling, rate limiting, LLM provider abstraction, and:
  - `tests/test_dna_fidelity.py`: Automated DNA Persona Fidelity Evaluation Gate.
  - `tests/test_sm2.py`: SM-2 Spaced Repetition Algorithm & Integration Suite.

### Frontend Type Checking & Production Build
```bash
cd teachclone/apps/web
npx tsc --noEmit
npm run build
```

---

## 📜 Full User Journey
For a step-by-step walkthrough of creating teacher profiles, extracting DNA from video lectures, streaming persona-accurate doubt answers, generating diagnostic checkpoints, and tracking SM-2 concept mastery, see [`docs/user-journey.md`](./docs/user-journey.md).

---

## 📦 Docker Deployment

To launch the full containerized stack:
```bash
cd teachclone
docker compose up -d
```
