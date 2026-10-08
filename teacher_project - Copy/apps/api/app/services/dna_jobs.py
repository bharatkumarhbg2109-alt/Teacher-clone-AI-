"""In-memory job registry + log buffer for the Teacher DNA admin dashboard.

Both stores are process-local and best-effort — they reset when the API
restarts. They exist so the admin dashboard can show *live* extraction
progress and recent pipeline logs without adding a Redis/Celery dependency,
matching the project's INLINE_TASKS / no-infra local ethos.

Nothing here touches the database or blocks the event loop; the extraction
work itself runs in a background asyncio task (see ``dna_router``).
"""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone

# The six pipeline phases, in order, keyed exactly as the dashboard expects.
PHASES = [
    "download",
    "audio_extract",
    "transcription",
    "dna_analysis",
    "dna_report",
    "system_prompt",
]

# The 7 DNA layers, in analysis order (field names used across the pipeline).
LAYER_ORDER = [
    "vocabulary_dna",
    "explanation_dna",
    "example_dna",
    "question_dna",
    "correction_dna",
    "transition_dna",
    "emotion_dna",
]

_LOCK = threading.RLock()
_JOBS: dict[str, dict] = {}
_JOB_ORDER: "deque[str]" = deque(maxlen=100)  # ids of the last 100 jobs


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
#  Job lifecycle
# ---------------------------------------------------------------------------
def create_job(
    teacher_id: str,
    teacher_name: str,
    *,
    model: str,
    whisper_model: str,
    source: str,
    videos_total: int = 0,
) -> str:
    """Register a new running job and return its id."""
    job_id = uuid.uuid4().hex[:12]
    with _LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "teacher_id": str(teacher_id),
            "teacher_name": teacher_name,
            "model": model,
            "whisper_model": whisper_model,
            "source": source,  # "url" | "file"
            "status": "running",  # running | complete | failed
            "current_phase": 1,
            "current_layer": None,
            "phase_progress": {p: 0 for p in PHASES},
            "layers_done": [],
            "layers_total": len(LAYER_ORDER),
            "_layers_completed": 0,
            "stats": {
                "videos_downloaded": 0,
                "videos_total": videos_total,
                "words_transcribed": 0,
                "language_detected": "",
            },
            "started_at": _now_iso(),
            "_started_monotonic": time.monotonic(),
            "finished_at": None,
            "eta_seconds": None,
            "error": None,
        }
        _JOB_ORDER.append(job_id)
    return job_id


def set_phase(job_id: str, phase: str, pct: float, *, current_index: int | None = None) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job or phase not in job["phase_progress"]:
            return
        job["phase_progress"][phase] = max(0, min(100, int(pct)))
        if current_index is not None:
            job["current_phase"] = current_index
        _recompute_eta(job)


def set_layers_total(job_id: str, total: int) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job:
            job["layers_total"] = max(1, int(total))


def on_layer(job_id: str, field: str, done: bool) -> None:
    """Progress hook passed to ``dna_extractor.analyze_dna``."""
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["current_layer"] = field
        job["current_phase"] = 4
        if done:
            job["_layers_completed"] += 1
            if field not in job["layers_done"]:
                job["layers_done"].append(field)
        total = job.get("layers_total") or len(LAYER_ORDER)
        pct = min(100, int(job["_layers_completed"] / total * 100))
        job["phase_progress"]["dna_analysis"] = pct
        _recompute_eta(job)


def merge_stats(job_id: str, **stats) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        for key, val in stats.items():
            if val is not None:
                job["stats"][key] = val


def finish(job_id: str) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["status"] = "complete"
        for phase in PHASES:
            job["phase_progress"][phase] = 100
        job["current_phase"] = len(PHASES)
        job["current_layer"] = None
        job["finished_at"] = _now_iso()
        job["eta_seconds"] = 0


def fail(job_id: str, error) -> None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if not job:
            return
        job["status"] = "failed"
        job["error"] = str(error)[:500]
        job["current_layer"] = None
        job["finished_at"] = _now_iso()
        job["eta_seconds"] = None


def _recompute_eta(job: dict) -> None:
    """Crude ETA: extrapolate elapsed time by overall percent complete."""
    done = sum(job["phase_progress"].values())
    total = len(PHASES) * 100
    frac = (done / total) if total else 0
    elapsed = time.monotonic() - job["_started_monotonic"]
    if 0.02 < frac < 1:
        job["eta_seconds"] = max(0, int(elapsed / frac - elapsed))
    elif frac >= 1:
        job["eta_seconds"] = 0


# ---------------------------------------------------------------------------
#  Reads (return copies without private fields)
# ---------------------------------------------------------------------------
def _public(job: dict) -> dict:
    return {k: v for k, v in job.items() if not k.startswith("_")}


def get(job_id: str) -> dict | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        return _public(job) if job else None


def list_jobs(limit: int = 30) -> list[dict]:
    with _LOCK:
        ids = list(_JOB_ORDER)[-limit:][::-1]
        return [_public(_JOBS[i]) for i in ids if i in _JOBS]


def active_jobs() -> list[dict]:
    with _LOCK:
        return [_public(j) for j in _JOBS.values() if j["status"] == "running"]


# ===========================================================================
#  Ring log buffer — captures the ``teachclone`` logger for the Logs page
# ===========================================================================
class _RingLogHandler(logging.Handler):
    def __init__(self, capacity: int = 800) -> None:
        super().__init__()
        self.buf: "deque[dict]" = deque(maxlen=capacity)
        self._seq = 0
        self._lock = threading.Lock()

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D401
        try:
            with self._lock:
                self._seq += 1
                self.buf.append(
                    {
                        "seq": self._seq,
                        "ts": datetime.fromtimestamp(
                            record.created, tz=timezone.utc
                        ).isoformat(),
                        "level": record.levelname,
                        "logger": record.name,
                        "message": record.getMessage(),
                    }
                )
        except Exception:  # noqa: BLE001 — logging must never raise
            pass


_ring = _RingLogHandler()
_installed = False


def install_log_capture() -> None:
    """Attach the ring buffer to the ``teachclone`` logger tree (idempotent)."""
    global _installed
    if _installed:
        return
    lg = logging.getLogger("teachclone")
    lg.addHandler(_ring)
    if lg.level == logging.NOTSET or lg.level > logging.INFO:
        lg.setLevel(logging.INFO)
    _installed = True


def get_logs(limit: int = 200, since_seq: int | None = None) -> list[dict]:
    """Return recent log lines, optionally only those newer than ``since_seq``.

    Level/category/search filtering is done client-side so the same raw feed
    powers every filter tab without extra round-trips.
    """
    with _ring._lock:
        items = list(_ring.buf)
    if since_seq is not None:
        items = [x for x in items if x["seq"] > since_seq]
    return items[-limit:]


def clear_logs() -> None:
    with _ring._lock:
        _ring.buf.clear()
