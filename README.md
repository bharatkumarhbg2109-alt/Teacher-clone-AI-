# AI Teacher Clone 🎓🤖

An intelligent, interactive AI Teacher platform powered by Knowledge Graphs, Multimodal Vision, and Retrieval-Augmented Generation (RAG).

[![CI Pipeline](https://github.com/bharatkumarhbg2109-alt/Teacher-clone-AI-/actions/workflows/ci.yml/badge.svg)](https://github.com/bharatkumarhbg2109-alt/Teacher-clone-AI-/actions/workflows/ci.yml)
[![Docker Images](https://github.com/bharatkumarhbg2109-alt/Teacher-clone-AI-/actions/workflows/docker-build.yml/badge.svg)](https://github.com/bharatkumarhbg2109-alt/Teacher-clone-AI-/actions/workflows/docker-build.yml)

---

## 🌟 Key Features

- **Interactive AI Tutoring**: Conversational teacher powered by LLM and local context.
- **Multimodal Vision**: Support for image understanding and diagram explanations via Ollama LLaVA.
- **Knowledge Graph & Curriculum**: Automated concept extraction, prerequisite mapping, and dynamic interactive curriculum generation using NetworkX and Pyvis.
- **Hybrid Retrieval & RAG**: Semantic vector retrieval using ChromaDB combined with keyword and graph-traversal search.
- **SM-2 Spaced Repetition**: Memory retention scheduling for concepts and flashcards.
- **Modern UI**: Fast, responsive React + Vite interface with Zustand state management.
- **Desktop & Docker Ready**: Run as a desktop application (Electron) or completely containerized with Docker and Docker Compose.

---

## 🐳 Quick Start with Docker

The easiest way to run the entire AI Teacher Clone stack is using Docker Compose:

```bash
# Clone the repository
git clone https://github.com/bharatkumarhbg2109-alt/Teacher-clone-AI-.git
cd Teacher-clone-AI-

# Build and start all services
docker compose up --build
```

### Services Started:
- **Frontend**: [http://localhost:5175](http://localhost:5175)
- **Backend API**: [http://localhost:8002](http://localhost:8002)
- **API Documentation**: [http://localhost:8002/docs](http://localhost:8002/docs)
- **Ollama LLM**: [http://localhost:11434](http://localhost:11434)

To run in detached (background) mode:
```bash
docker compose up -d
```

To stop containers:
```bash
docker compose down
```

---

## 💻 Local Setup (Without Docker)

### 1. Backend Setup (FastAPI :8002)
```bash
cd backend
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
python -m uvicorn main:app --host 0.0.0.0 --port 8002 --reload
```

### 2. Frontend Setup (React + Vite :5175)
```bash
cd frontend
npm install
npm run dev
```

### Windows One-Click Launchers:
- Run `setup_env.bat` to configure Python environment.
- Run `start_backend.bat` to launch backend.
- Run `start_frontend.bat` to launch web frontend.

---

## 📁 Repository Structure

```text
├── backend/                  # FastAPI Knowledge Graph & RAG backend (:8002)
│   ├── core/                 # Structured logging & configs
│   ├── graph/                # Concept extraction, visualizer, curriculum
│   ├── graph_db/             # ChromaDB vector store & SQLite database
│   ├── middleware/           # API key auth middleware
│   ├── routers/              # Chat, teach, questions, vision endpoints
│   ├── Dockerfile            # Production Docker image for Backend
│   └── requirements.txt      # Pinned Python dependencies
│
├── frontend/                 # React 18 + Vite frontend (:5175)
│   ├── src/                  # Components, zustand store, api client
│   ├── Dockerfile            # Production multi-stage Nginx Docker image
│   └── nginx.conf            # Nginx reverse proxy configuration
│
├── electron/                 # Electron desktop wrapper (:main.js)
│
├── teacher_project - Copy/   # SaaS multi-tenant platform (Next.js + FastAPI)
│   ├── apps/api              # FastAPI SaaS backend (:8000)
│   ├── apps/web              # Next.js web application (:3000)
│   └── docker-compose.yml    # SaaS multi-container setup (PostgreSQL, Redis, Qdrant)
│
├── .github/workflows/        # CI/CD and automated Docker build pipelines
│   ├── ci.yml                # Pytest, ESLint & SaaS tests
│   └── docker-build.yml      # Builds & pushes Docker images to GHCR
│
└── docker-compose.yml        # Root compose file for full AI Teacher Clone stack
```

---

## 🚀 CI/CD & Automated Container Registry (GHCR)

Every push to the `main` branch automatically triggers GitHub Actions to:
1. Run backend pytest suites and frontend linting.
2. Build optimized multi-platform Docker images.
3. Publish container images directly to GitHub Container Registry (`ghcr.io`):
   - `ghcr.io/bharatkumarhbg2109-alt/teacher-clone-backend:latest`
   - `ghcr.io/bharatkumarhbg2109-alt/teacher-clone-frontend:latest`

---

## 📄 License
This project is open-source and available under the MIT License.
