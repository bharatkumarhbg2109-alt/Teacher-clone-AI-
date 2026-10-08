# TeachClone End-to-End User Journey

This document details the complete student and educator journey through TeachClone, verifying every stage from teacher creation and video DNA extraction to adaptive doubt chat, checkpoint quizzes, SM-2 spaced repetition scheduling, and gamification.

---

## Architecture Flow

```
[Web App / Next.js :3000]
         │
         ▼
[FastAPI :8000] ──► [SQLite / PostgreSQL]
         │
         ├──► [yt-dlp + ffmpeg + faster-whisper] ──► Audio & Transcript
         │
         ├──► [Ollama llama3.1:8b] ───────────────► 7-Layer Teacher DNA
         │
         ├──► [Hybrid Vector Search] ────────────► Top-8 Grounded Knowledge Chunks
         │
         ├──► [Prompt Builder] ──────────────────► Teacher-Persona System Prompt
         │
         ├──► [Chat SSE Stream] ─────────────────► Token-by-Token Styled Answer [n]
         │
         ├──► [Checkpoint Quizzes] ──────────────► Dynamic Assessment & Level Adaptation
         │
         └──► [SM-2 Spaced Repetition] ──────────► EF, Intervals, & Concept Mastery
```

---

## The 8 Journey Stages

### Stage 1: Educator Onboarding & Teacher Profile Creation
- **UI Route:** `/profiles/new`
- **API Call:** `POST /profiles`
- **Payload:**
  ```json
  {
    "name": "Prof. Alok Sharma",
    "subject": "Physics",
    "description": "Celebrated Physics professor known for making abstract mechanics intuitive and vivid.",
    "tts_voice": "en_US-lessac-medium"
  }
  ```
- **Response:** `201 Created` with generated profile `id`.

### Stage 2: Media Ingestion & Audio Transcription
- **UI Route:** `/profiles/[id]` (Knowledge Tab)
- **API Call:** `POST /media/youtube` (or file upload `POST /media/upload`)
- **Payload:**
  ```json
  {
    "url": "https://www.youtube.com/watch?v=...",
    "teacher_profile_id": "<teacher_id>"
  }
  ```
- **Processing:**
  - `yt-dlp` downloads audio
  - `ffmpeg` extracts and normalizes 16kHz mono audio
  - `faster-whisper` (model: `base` / `small`) transcribes audio with timestamps
  - Text chunks indexed into vector store with dense and sparse embeddings.

### Stage 3: 7-Layer Teacher DNA Extraction
- **API Call:** Automatic inline task or `POST /dna/extract-from-url`
- **Output:**
  - Layer 1: Vocabulary & code-switching DNA (`vocabulary_dna`)
  - Layer 2: Explanation structure & sequence (`explanation_dna`)
  - Layer 3: Example sources & styles (`example_dna`)
  - Layer 4: Questioning & Socratic style (`question_dna`)
  - Layer 5: Error correction & guiding behavior (`correction_dna`)
  - Layer 6: Topic transition signals (`transition_dna`)
  - Layer 7: Emotional resonance & energy (`emotion_dna`)
  - Generated DNA JSON stored in `dna_reports/<teacher_id>_dna.json` and on `TeacherProfile.style_profile`.
  - Compiled system prompt written to `system_prompts/<teacher_id>_prompt.txt` and `TeacherProfile.system_prompt`.
- **Verification:** `GET /dna/report/{teacher_id}` returns `200 OK` with all 7 layers populated.

### Stage 4: Student Session Initiation
- **UI Route:** `/dashboard` or `/discover` -> Start Learning
- **API Call:** `POST /sessions`
- **Payload:**
  ```json
  {
    "teacher_profile_id": "<teacher_id>",
    "student_profile": {
      "subject": "Physics",
      "level": "undergrad",
      "goal": "Master angular momentum and rotational dynamics",
      "learning_style": "examples"
    }
  }
  ```
- **Response:** `201 Created` with `session_id`, initial XP awarded (+20 XP for `session_started`).

### Stage 5: Doubt-Solving Chat with Teacher DNA Persona
- **UI Route:** `/chat/[sessionId]`
- **API Call:** `POST /chat/{session_id}/message`
- **Payload:**
  ```json
  {
    "content": "Why does a spinning top not fall over when tilted, and how does torque cause precession?",
    "want_audio": false
  }
  ```
- **SSE Stream Protocol:**
  - `event: token` -> streams tokens chunk-by-chunk in real time.
  - The answer naturally includes $\ge 3$ teacher signature phrases (e.g., *"Notice the physics here"*, *"Core mechanism"*, *"Here is the twist"*).
  - Grounded with reference knowledge citations `[1]`.
  - Concludes with a Socratic check question.
  - `event: done` -> returns `{"message_id": "<uuid>", "citations": [...], "audio_url": null}`.
- **Persistence:** Message persisted to SQLite `messages` table with role `assistant`, model `llama3.1:8b`.

### Stage 6: Mid-Lecture Checkpoint Quiz Generation
- **UI Action:** Click "Check Understanding" in chat
- **API Call:** `POST /sessions/{session_id}/checkpoint`
- **Payload:**
  ```json
  {
    "concept": "Angular Momentum and Precession",
    "num_questions": 2
  }
  ```
- **Response:** `200 OK` with dynamic diagnostic multiple-choice and conceptual questions tailored to student level.

### Stage 7: Quiz Submission & SM-2 Spaced Repetition Update
- **API Call:** `POST /checkpoints/{quiz_id}/submit`
- **Payload:**
  ```json
  {
    "answers": {
      "q1": "B",
      "q2": "Torque alters angular momentum perpendicular to spin axis."
    }
  }
  ```
- **Adaptive Actions:**
  - Scores answers against rubrics.
  - Adapts student effective difficulty (`deeper`, `hold`, `reteach`).
  - Converts performance score to SM-2 quality rating ($q \in [0, 5]$).
  - Calculates updated SM-2 parameters for each concept:
    - Easiness Factor ($EF \ge 1.3$)
    - Interval ($I = 1 \rightarrow 6 \rightarrow \text{round}(I \times EF)$)
    - Consecutive repetitions
    - `next_review_date` (ISO date)
    - `mastery_score` ($0.0 - 1.0$)
- **Response:** `200 OK` with score, adaptation guidance, and mastered / review concept lists.

### Stage 8: Progress & Gamification Retention Tracking
- **UI Route:** `/progress`
- **API Call:** `GET /users/me/stats`
- **Response:**
  ```json
  {
    "xp_total": 50,
    "level": 1,
    "streak_days": 1,
    "longest_streak": 1,
    "sessions_completed": 1,
    "quizzes_completed": 1,
    "perfect_quizzes": 0,
    "sources_processed": 1,
    "badges": []
  }
  ```
- **Spaced Repetition Review Worker:** Background service (`app.services.review_scheduler`) periodically evaluates `get_due_reviews()` across all active sessions, logging or notifying when `today >= next_review_date` for shaky/review concepts.
