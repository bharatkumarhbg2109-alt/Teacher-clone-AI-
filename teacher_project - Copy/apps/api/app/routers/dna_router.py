"""Teacher DNA endpoints — 100% local extraction (Ollama + faster-whisper).

Extraction runs as a background asyncio task so the dashboard can poll live
progress (no Redis/Celery needed — it fits the project's INLINE_TASKS ethos).

    POST   /dna/extract-from-url     start pipeline from YouTube URL(s) -> job_id
    POST   /dna/extract-from-file    upload a video/audio file (skips Phase 1) -> job_id
    POST   /dna/regenerate/{id}      re-analyze stored transcripts -> job_id
    GET    /dna/status/{job_id}      live extraction progress (poll every 3s)
    GET    /dna/jobs                 active + recent extraction jobs
    GET    /dna/report/{id}          latest DNA report JSON
    GET    /dna/system-prompt/{id}   generated system prompt (text)
    GET    /dna/health               Ollama reachability + installed models
    GET    /dna/system               DB / tool / memory / aggregate stats
    GET    /dna/teachers             admin summary of every teacher + DNA status
    GET    /dna/logs                 recent pipeline log lines
    DELETE /dna/logs                 clear the in-memory log buffer

No paid API is used anywhere in these endpoints.
"""
import asyncio
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import AsyncSessionLocal
from app.dependencies import get_admin_user, get_current_user, get_db
from app.models.audit_log import AuditLog
from app.models.dna_report import DnaReport
from app.models.media_source import MediaSource
from app.models.teacher_profile import TeacherProfile
from app.models.transcript_chunk import TranscriptChunk
from app.models.user import User
from app.services import dna_extractor as dna
from app.services import dna_jobs as jobs
from app.services import dna_system as dnasys

router = APIRouter(prefix="/dna", tags=["dna"])
log = logging.getLogger("teachclone.dna")

# Capture the teachclone logger tree into the ring buffer so /dna/logs works.
jobs.install_log_capture()


class ExtractFromUrlRequest(BaseModel):
    teacher_id: str
    youtube_urls: list[str]
    model: str | None = None  # "llama3.1" | "mistral" | any installed model


async def _owned_teacher(db: AsyncSession, teacher_id: str, user: User) -> TeacherProfile:
    teacher = (
        await db.execute(select(TeacherProfile).where(TeacherProfile.id == teacher_id))
    ).scalar_one_or_none()
    if not teacher:
        raise HTTPException(404, "Teacher profile not found")
    if teacher.user_id != user.id:
        raise HTTPException(403, "Not your teacher profile")
    return teacher


# ===========================================================================
#  Background pipeline runners (own their own DB session — the request's is
#  already closed by the time these run).
# ===========================================================================
async def _analyze_and_persist(
    job_id: str,
    teacher_id: str,
    teacher_name: str,
    user_id: str,
    transcripts: list[str],
    items: list[dict],
    model: str,
    language: str,
) -> None:
    """Phases 4-6 (analyse -> merge -> fingerprint -> prompt) + persistence.

    Mirrors ``dna.build_report_and_prompt`` but reports per-phase progress and
    only persists new transcripts when ``items`` is non-empty (regenerate reuses
    already-stored transcripts).
    """
    valid = [t for t in transcripts if t and t.strip()]
    if not valid:
        jobs.fail(job_id, "No non-empty transcripts to analyze")
        return

    jobs.set_layers_total(job_id, len(valid) * len(jobs.LAYER_ORDER))
    jobs.set_phase(job_id, "dna_analysis", 0, current_index=4)

    try:
        reports: list[dict] = []
        for t in valid:
            layers = await dna.analyze_dna(
                [t],
                model=model,
                on_layer=lambda field, i, done: jobs.on_layer(job_id, field, done),
            )
            reports.append(
                dna.generate_dna_report(
                    layers,
                    teacher_name,
                    analyzed_videos=1,
                    total_words=len(t.split()),
                    language=language,
                    model=model,
                )
            )
        jobs.set_phase(job_id, "dna_analysis", 100, current_index=4)

        # Phase 5 — merge + fingerprint
        jobs.set_phase(job_id, "dna_report", 40, current_index=5)
        log.info("[Phase 5] Merging DNA reports + generating teaching fingerprint")
        final = dna.merge_dna_reports(reports)
        final["teaching_fingerprint"] = await dna._generate_fingerprint(final, model=model)
        jobs.set_phase(job_id, "dna_report", 100, current_index=5)

        # Phase 6 — system prompt
        jobs.set_phase(job_id, "system_prompt", 40, current_index=6)
        log.info("[Phase 6] Generating system prompt")
        system_prompt = await dna.generate_system_prompt(final, model=model)
        jobs.set_phase(job_id, "system_prompt", 100, current_index=6)
        report = final
    except dna.OllamaUnavailable as exc:
        jobs.fail(job_id, f"Ollama unavailable: {exc}")
        return
    except dna.OllamaError as exc:
        jobs.fail(job_id, f"DNA analysis failed: {exc}")
        return

    # Persist with a fresh session (the request session is long gone).
    try:
        async with AsyncSessionLocal() as db:
            source_ids = (
                await dna.persist_transcripts(db, teacher_id, user_id, items) if items else []
            )
            await dna.save_dna_outputs(db, teacher_id, report, system_prompt, model)
            await db.commit()
        for sid in source_ids:
            try:
                await dna.embed_source(sid)
            except Exception as exc:  # noqa: BLE001
                log.warning("[DNA] embedding source %s failed (non-fatal): %s", sid, exc)
    except Exception as exc:  # noqa: BLE001
        log.exception("[DNA] persistence failed for job %s", job_id)
        jobs.fail(job_id, f"Analysis done but saving failed: {exc}")
        return

    log.info("[DNA] job %s complete — teacher '%s'", job_id, teacher_name)
    jobs.finish(job_id)


async def _run_url_job(
    job_id: str,
    teacher_id: str,
    teacher_name: str,
    user_id: str,
    urls: list[str],
    model: str,
) -> None:
    tmp = tempfile.mkdtemp(prefix="dna_url_")
    try:
        n = max(1, len(urls))
        transcripts: list[str] = []
        items: list[dict] = []
        language = ""
        for idx, url in enumerate(urls, 1):
            jobs.set_phase(job_id, "download", (idx - 1) / n * 100, current_index=1)
            log.info("[Phase 1] Downloading video %d/%d: %s", idx, n, url)
            try:
                video_path = await dna.download_video(url, tmp)           # Phase 1
                jobs.merge_stats(job_id, videos_downloaded=idx)
                jobs.set_phase(job_id, "download", idx / n * 100, current_index=1)

                jobs.set_phase(job_id, "audio_extract", (idx - 1) / n * 100, current_index=2)
                log.info("[Phase 2] Extracting audio (%d/%d)", idx, n)
                audio_path = await dna.extract_audio(video_path, tmp)     # Phase 2
                jobs.set_phase(job_id, "audio_extract", idx / n * 100, current_index=2)

                jobs.set_phase(job_id, "transcription", (idx - 1) / n * 100, current_index=3)
                log.info("[Phase 3] Transcribing audio (%d/%d) with Whisper", idx, n)
                tr = await asyncio.to_thread(dna.transcribe_audio, audio_path)  # Phase 3
            except Exception as exc:  # noqa: BLE001
                log.warning("[DNA] Failed to process %s: %s", url, exc)
                continue
            if tr["full_text"].strip():
                transcripts.append(tr["full_text"])
                language = language or tr.get("language", "")
                jobs.merge_stats(
                    job_id,
                    words_transcribed=sum(len(t.split()) for t in transcripts),
                    language_detected=language,
                )
                jobs.set_phase(job_id, "transcription", idx / n * 100, current_index=3)
                items.append(
                    {
                        "text": tr["full_text"],
                        "source_type": "youtube_url",
                        "original_url": url,
                        "duration_seconds": tr.get("duration_seconds"),
                    }
                )

        if not transcripts:
            jobs.fail(job_id, "Could not extract any transcript from the provided URL(s)")
            return
        for phase in ("download", "audio_extract", "transcription"):
            jobs.set_phase(job_id, phase, 100)
        await _analyze_and_persist(
            job_id, teacher_id, teacher_name, user_id, transcripts, items, model, language
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("[DNA] url job %s crashed", job_id)
        jobs.fail(job_id, exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


async def _run_file_job(
    job_id: str,
    teacher_id: str,
    teacher_name: str,
    user_id: str,
    file_path: str,
    filename: str,
    content_type: str | None,
    model: str,
) -> None:
    tmp = os.path.dirname(file_path)
    try:
        # File uploads skip Phase 1 (download) — mark it complete for progress.
        jobs.set_phase(job_id, "download", 100, current_index=2)
        jobs.set_phase(job_id, "audio_extract", 20, current_index=2)
        log.info("[Phase 2] Extracting audio from upload: %s", filename)
        audio_path = await dna.extract_audio(file_path, tmp, cleanup=False)
        jobs.set_phase(job_id, "audio_extract", 100, current_index=2)

        jobs.set_phase(job_id, "transcription", 10, current_index=3)
        log.info("[Phase 3] Transcribing %s with Whisper", filename)
        tr = await asyncio.to_thread(dna.transcribe_audio, audio_path)
        if not tr["full_text"].strip():
            jobs.fail(job_id, "No speech could be transcribed from the file")
            return
        jobs.merge_stats(
            job_id,
            videos_downloaded=1,
            words_transcribed=len(tr["full_text"].split()),
            language_detected=tr.get("language", ""),
        )
        jobs.set_phase(job_id, "transcription", 100, current_index=3)
        items = [
            {
                "text": tr["full_text"],
                "source_type": "dna_upload",
                "file_name": filename,
                "content_type": content_type,
                "duration_seconds": tr.get("duration_seconds"),
            }
        ]
        await _analyze_and_persist(
            job_id, teacher_id, teacher_name, user_id, [tr["full_text"]], items, model,
            tr.get("language", ""),
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("[DNA] file job %s crashed", job_id)
        jobs.fail(job_id, exc)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ===========================================================================
#  Extraction endpoints (return a job id immediately)
# ===========================================================================
@router.post("/extract-from-url")
async def extract_from_url(
    payload: ExtractFromUrlRequest,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    teacher = await _owned_teacher(db, payload.teacher_id, user)
    if not payload.youtube_urls:
        raise HTTPException(400, "Provide at least one YouTube URL")
    model = payload.model or settings.OLLAMA_MODEL
    urls = [u.strip() for u in payload.youtube_urls if u and u.strip()]
    teacher_name, teacher_id, user_id = teacher.name, str(teacher.id), str(user.id)
    await db.commit()  # release the DB lock before the long offline pipeline

    job_id = jobs.create_job(
        teacher_id, teacher_name, model=model,
        whisper_model=settings.DNA_WHISPER_MODEL, source="url", videos_total=len(urls),
    )
    log.info("[DNA] Extraction started — job %s, teacher '%s', %d url(s), model=%s",
             job_id, teacher_name, len(urls), model)
    AuditLog.write(db, user.id, user.email, "dna.extracted", "teacher_profile", teacher_id,
                   meta={"source": "url", "urls_count": len(urls), "model": model, "job_id": job_id})
    asyncio.create_task(_run_url_job(job_id, teacher_id, teacher_name, user_id, urls, model))
    return {"job_id": job_id, "status": "running", "teacher_id": teacher_id}


@router.post("/extract-from-file")
async def extract_from_file(
    teacher_id: str = Form(...),
    model: str | None = Form(default=None),
    file: UploadFile = File(...),
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    teacher = await _owned_teacher(db, teacher_id, user)
    resolved = model or settings.OLLAMA_MODEL
    filename = os.path.basename(file.filename or "upload.bin")
    content_type = file.content_type
    data = await file.read()  # read before the request/session closes
    teacher_name, tid, uid = teacher.name, str(teacher.id), str(user.id)
    await db.commit()

    tmp = tempfile.mkdtemp(prefix="dna_file_")
    path = os.path.join(tmp, filename)
    with open(path, "wb") as f:
        f.write(data)

    job_id = jobs.create_job(
        tid, teacher_name, model=resolved,
        whisper_model=settings.DNA_WHISPER_MODEL, source="file", videos_total=1,
    )
    log.info("[DNA] Extraction started — job %s, teacher '%s', file '%s', model=%s",
             job_id, teacher_name, filename, resolved)
    AuditLog.write(db, user.id, user.email, "dna.extracted", "teacher_profile", tid,
                   meta={"source": "file", "filename": filename, "model": resolved, "job_id": job_id})
    asyncio.create_task(
        _run_file_job(job_id, tid, teacher_name, uid, path, filename, content_type, resolved)
    )
    return {"job_id": job_id, "status": "running", "teacher_id": tid}


@router.post("/regenerate/{teacher_id}")
async def regenerate(
    teacher_id: str,
    model: str | None = None,
    user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Re-run the DNA analysis on the teacher's already-stored transcripts."""
    teacher = await _owned_teacher(db, teacher_id, user)
    rows = (
        (await db.execute(
            select(TranscriptChunk)
            .join(MediaSource, TranscriptChunk.media_source_id == MediaSource.id)
            .where(MediaSource.teacher_profile_id == teacher.id)
            .order_by(TranscriptChunk.media_source_id, TranscriptChunk.chunk_index)
        )).scalars().all()
    )
    if not rows:
        raise HTTPException(400, "This teacher has no stored transcripts to analyze")

    by_source: dict = {}
    for c in rows:
        by_source.setdefault(str(c.media_source_id), []).append(c.text)
    transcripts = [" ".join(parts) for parts in by_source.values()]
    resolved = model or settings.OLLAMA_MODEL
    teacher_name, tid, uid = teacher.name, str(teacher.id), str(user.id)
    await db.commit()

    job_id = jobs.create_job(
        tid, teacher_name, model=resolved,
        whisper_model=settings.DNA_WHISPER_MODEL, source="regenerate",
        videos_total=len(transcripts),
    )
    # Phases 1-3 are skipped (transcripts already exist) — mark them complete.
    for phase in ("download", "audio_extract", "transcription"):
        jobs.set_phase(job_id, phase, 100, current_index=3)
    jobs.merge_stats(
        job_id,
        videos_downloaded=len(transcripts),
        words_transcribed=sum(len(t.split()) for t in transcripts),
    )
    log.info("[DNA] Re-extraction started — job %s, teacher '%s', %d transcript(s)",
             job_id, teacher_name, len(transcripts))
    AuditLog.write(db, user.id, user.email, "dna.extracted", "teacher_profile", tid,
                   meta={"source": "regenerate", "transcript_count": len(transcripts), "model": resolved, "job_id": job_id})
    asyncio.create_task(
        _analyze_and_persist(job_id, tid, teacher_name, uid, transcripts, [], resolved, "")
    )
    return {"job_id": job_id, "status": "running", "teacher_id": tid}


# ===========================================================================
#  Live status / jobs
# ===========================================================================
@router.get("/status/{job_id}")
async def job_status(job_id: str) -> dict:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Unknown job id (jobs reset on server restart)")
    return job


@router.get("/jobs")
async def list_extraction_jobs() -> dict:
    return {"active": jobs.active_jobs(), "recent": jobs.list_jobs(30)}


# ===========================================================================
#  Reports / prompts
# ===========================================================================
@router.get("/report/{teacher_id}")
async def get_report(
    teacher_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    teacher = await _owned_teacher(db, teacher_id, user)
    latest = (
        await db.execute(
            select(DnaReport)
            .where(DnaReport.teacher_profile_id == teacher.id)
            .order_by(DnaReport.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest:
        return latest.report
    if teacher.style_profile:
        return teacher.style_profile
    raise HTTPException(404, "No DNA report yet for this teacher")


@router.get("/system-prompt/{teacher_id}", response_class=PlainTextResponse)
async def get_system_prompt(
    teacher_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> str:
    teacher = await _owned_teacher(db, teacher_id, user)
    if not teacher.system_prompt:
        raise HTTPException(404, "No system prompt generated yet for this teacher")
    return teacher.system_prompt


# ===========================================================================
#  Health / system / logs / teachers  (read-only monitoring, no auth needed)
# ===========================================================================
@router.get("/health")
async def dna_health() -> dict:
    """Ollama reachability + installed models (for the model switcher UI)."""
    health = await dna.ollama_health()
    return {
        **health,
        "default_model": settings.OLLAMA_MODEL,
        "fallback_model": settings.OLLAMA_FALLBACK_MODEL,
        "whisper_model": settings.DNA_WHISPER_MODEL,
    }


@router.get("/system")
async def dna_system_health(db: AsyncSession = Depends(get_db)) -> dict:
    ollama = await dna.ollama_health()
    return {
        "ollama": {
            **ollama,
            "default_model": settings.OLLAMA_MODEL,
            "fallback_model": settings.OLLAMA_FALLBACK_MODEL,
        },
        "whisper_model": settings.DNA_WHISPER_MODEL,
        "database": await dnasys.db_stats(db),
        "tools": await dnasys.tool_versions(),
        "memory": dnasys.memory_stats(),
        "disk": dnasys.disk_stats(),
        "stats": await dnasys.dna_aggregate_stats(db),
        "server_time": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/logs")
async def dna_logs(
    limit: int = Query(default=200, ge=1, le=1000),
    since: int | None = Query(default=None, ge=0),
) -> dict:
    return {"logs": jobs.get_logs(limit=limit, since_seq=since)}


@router.delete("/logs")
async def clear_dna_logs() -> dict:
    jobs.clear_logs()
    return {"status": "ok"}


def _layer_filled(layer: dict | None) -> bool:
    """A DNA layer counts as 'filled' if any of its values is truthy."""
    if not isinstance(layer, dict):
        return False
    for val in layer.values():
        if isinstance(val, (list, dict, str)) and len(val) > 0:
            return True
        if isinstance(val, bool) and val:
            return True
        if isinstance(val, (int, float)) and val:
            return True
    return False


@router.get("/teachers")
async def dna_teachers(db: AsyncSession = Depends(get_db)) -> list[dict]:
    """Admin summary: every teacher + DNA status, word counts, layer flags.

    Intentionally global (all users) — this is a local admin monitoring view.
    """
    profiles = (
        (await db.execute(select(TeacherProfile).order_by(TeacherProfile.created_at.desc())))
        .scalars()
        .all()
    )
    reports = (
        (await db.execute(select(DnaReport).order_by(DnaReport.created_at.desc())))
        .scalars()
        .all()
    )
    latest_by_teacher: dict[str, DnaReport] = {}
    for r in reports:
        key = str(r.teacher_profile_id)
        if key not in latest_by_teacher:  # first seen = newest (desc order)
            latest_by_teacher[key] = r

    active_teacher_ids = {j["teacher_id"] for j in jobs.active_jobs()}

    out: list[dict] = []
    for p in profiles:
        tid = str(p.id)
        rep = latest_by_teacher.get(tid)
        dna_block = None
        status = "none"
        if tid in active_teacher_ids:
            status = "processing"
        if rep is not None:
            report = rep.report or {}
            layer_flags = {k: _layer_filled(report.get(k)) for k in jobs.LAYER_ORDER}
            filled = sum(1 for v in layer_flags.values() if v)
            if status != "processing":
                status = "complete" if filled == len(jobs.LAYER_ORDER) else "partial"
            dna_block = {
                "analyzed_videos": rep.analyzed_videos,
                "total_words": rep.total_words,
                "language": rep.language,
                "model_used": rep.model_used,
                "extraction_date": report.get("extraction_date"),
                "updated_at": rep.created_at.isoformat() if rep.created_at else None,
                "layers": layer_flags,
                "layers_filled": filled,
                "signature_phrases": (report.get("signature_phrases") or [])[:6],
                "teaching_fingerprint": report.get("teaching_fingerprint") or "",
            }
        out.append(
            {
                "id": tid,
                "name": p.name,
                "subject": p.subject,
                "description": p.description,
                "created_at": p.created_at.isoformat() if p.created_at else None,
                "total_sources": p.total_sources,
                "has_dna": rep is not None,
                "status": status,
                "dna": dna_block,
            }
        )
    return out
