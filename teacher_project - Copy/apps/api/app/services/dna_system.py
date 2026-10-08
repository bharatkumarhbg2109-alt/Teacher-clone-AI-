"""System-health facts for the admin dashboard's /dna/system endpoint.

Everything here is cheap and best-effort: database size + table counts,
external-tool versions (ffmpeg / yt-dlp), the configured Whisper model, and
process/host memory. Anything unavailable degrades to ``None`` rather than
raising, so the dashboard can render partial data instead of a 500.
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

# ---------------------------------------------------------------------------
#  Database
# ---------------------------------------------------------------------------
def _sqlite_path() -> str | None:
    url = settings.DATABASE_URL
    if not url.startswith("sqlite"):
        return None
    # sqlite+aiosqlite:///./teachclone.db  -> "./teachclone.db"
    tail = url.split(":///", 1)[-1]
    if not tail or tail == ":memory:":
        return None
    return os.path.abspath(tail)


async def db_stats(db: AsyncSession) -> dict:
    info: dict = {
        "type": "SQLite" if settings.DATABASE_URL.startswith("sqlite") else "PostgreSQL",
        "file": None,
        "size_bytes": None,
        "tables": None,
        "row_counts": {},
    }
    path = _sqlite_path()
    if path:
        info["file"] = os.path.basename(path)
        try:
            info["size_bytes"] = os.path.getsize(path)
        except OSError:
            info["size_bytes"] = None

    # Row counts for the tables the dashboard cares about. Import defensively
    # so a missing/renamed model never breaks the endpoint.
    counters: list[tuple[str, str]] = [
        ("users", "app.models.user:User"),
        ("teacher_profiles", "app.models.teacher_profile:TeacherProfile"),
        ("dna_reports", "app.models.dna_report:DnaReport"),
        ("media_sources", "app.models.media_source:MediaSource"),
        ("transcript_chunks", "app.models.transcript_chunk:TranscriptChunk"),
        ("messages", "app.models.message:Message"),
        ("student_sessions", "app.models.student_session:StudentSession"),
    ]
    for label, ref in counters:
        module_name, cls_name = ref.split(":")
        try:
            module = __import__(module_name, fromlist=[cls_name])
            model = getattr(module, cls_name)
            count = (await db.execute(select(func.count()).select_from(model))).scalar_one()
            info["row_counts"][label] = int(count)
        except Exception:  # noqa: BLE001 — missing table/model is fine
            continue

    info["tables"] = len(info["row_counts"])
    return info


# ---------------------------------------------------------------------------
#  DNA aggregate stats (for the Overview metric cards)
# ---------------------------------------------------------------------------
async def dna_aggregate_stats(db: AsyncSession) -> dict:
    from app.models.dna_report import DnaReport
    from app.models.media_source import MediaSource
    from app.models.teacher_profile import TeacherProfile

    async def _count(stmt) -> int:
        try:
            return int((await db.execute(stmt)).scalar_one())
        except Exception:  # noqa: BLE001
            return 0

    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    total_teachers = await _count(select(func.count()).select_from(TeacherProfile))
    teachers_with_dna = await _count(
        select(func.count(func.distinct(DnaReport.teacher_profile_id)))
    )
    reports_total = await _count(select(func.count()).select_from(DnaReport))
    reports_today = await _count(
        select(func.count()).select_from(DnaReport).where(DnaReport.created_at >= today)
    )
    media_total = await _count(select(func.count()).select_from(MediaSource))
    words_total = await _count(select(func.coalesce(func.sum(DnaReport.total_words), 0)))

    return {
        "total_teachers": total_teachers,
        "teachers_with_dna": teachers_with_dna,
        "dna_reports_total": reports_total,
        "dna_reports_today": reports_today,
        "media_sources_total": media_total,
        "words_transcribed_total": words_total,
    }


# ---------------------------------------------------------------------------
#  External tool versions (cached — subprocesses are relatively expensive)
# ---------------------------------------------------------------------------
_tool_cache: dict = {"at": 0.0, "data": None}
_TOOL_TTL = 60.0


def _run_version(args: list[str], pattern: str) -> dict:
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, timeout=8, check=False
        )
    except (FileNotFoundError, OSError):
        return {"available": False, "version": None}
    except subprocess.TimeoutExpired:
        return {"available": False, "version": None, "error": "timeout"}
    out = (proc.stdout or "") + "\n" + (proc.stderr or "")
    match = re.search(pattern, out)
    return {"available": proc.returncode == 0, "version": match.group(1) if match else None}


def _tool_versions_sync() -> dict:
    ffmpeg = _run_version(["ffmpeg", "-version"], r"ffmpeg version (\S+)")
    ytdlp = _run_version(["yt-dlp", "--version"], r"(\d[\d.]+)")
    whisper_available = False
    try:
        import faster_whisper  # noqa: F401

        whisper_available = True
    except Exception:  # noqa: BLE001
        whisper_available = False
    return {
        "ffmpeg": ffmpeg,
        "yt_dlp": ytdlp,
        "whisper": {
            "available": whisper_available,
            "model": settings.DNA_WHISPER_MODEL,
            "engine": "faster-whisper",
        },
    }


async def tool_versions() -> dict:
    import asyncio

    now = time.monotonic()
    if _tool_cache["data"] is not None and (now - _tool_cache["at"]) < _TOOL_TTL:
        return _tool_cache["data"]
    data = await asyncio.to_thread(_tool_versions_sync)
    _tool_cache.update(at=now, data=data)
    return data


# ---------------------------------------------------------------------------
#  Memory (psutil if present, otherwise a graceful stub)
# ---------------------------------------------------------------------------
def memory_stats() -> dict:
    try:
        import psutil
    except Exception:  # noqa: BLE001
        return {"available": False}
    try:
        vm = psutil.virtual_memory()
        proc = psutil.Process()
        return {
            "available": True,
            "process_rss_bytes": int(proc.memory_info().rss),
            "system_total_bytes": int(vm.total),
            "system_used_bytes": int(vm.used),
            "system_percent": float(vm.percent),
        }
    except Exception:  # noqa: BLE001
        return {"available": False}


def disk_stats() -> dict:
    try:
        import shutil

        path = _sqlite_path() or os.getcwd()
        usage = shutil.disk_usage(os.path.dirname(path) if os.path.isfile(path) else path)
        return {
            "available": True,
            "total_bytes": int(usage.total),
            "used_bytes": int(usage.used),
            "free_bytes": int(usage.free),
        }
    except Exception:  # noqa: BLE001
        return {"available": False}
