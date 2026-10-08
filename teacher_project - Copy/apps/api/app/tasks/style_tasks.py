"""Extract/merge the teacher's style DNA across all their sources.

Preferred path: the local 7-layer DNA pipeline (Ollama). If Ollama is
unreachable, falls back to the legacy statistical style extractor so uploads
never hard-fail. Both paths are 100% local (no paid API)."""
import logging

from sqlalchemy import select

from app.config import settings
from app.tasks._util import run
from app.worker import celery_app

log = logging.getLogger("teachclone.dna")


@celery_app.task(name="ai.extract_style", bind=True)
def extract_style(self, media_source_id: str):
    from app.db.session import AsyncSessionLocal
    from app.models.media_source import MediaSource
    from app.models.teacher_profile import TeacherProfile
    from app.models.transcript_chunk import TranscriptChunk
    from app.services import dna_extractor, style_extractor as style_mod
    from app.services.gamification import award_xp
    from app.services.style_extractor import style_extractor

    async def _impl():
        async with AsyncSessionLocal() as db:
            source = (
                await db.execute(select(MediaSource).where(MediaSource.id == media_source_id))
            ).scalar_one()

            all_chunks = (
                (await db.execute(
                    select(TranscriptChunk)
                    .join(MediaSource, TranscriptChunk.media_source_id == MediaSource.id)
                    .where(
                        MediaSource.teacher_profile_id == source.teacher_profile_id,
                        TranscriptChunk.content_type.in_(["audio", "document"]),
                    )
                    .order_by(TranscriptChunk.media_source_id, TranscriptChunk.chunk_index)
                )).scalars().all()
            )
            if not all_chunks:
                return

            teacher = (
                await db.execute(
                    select(TeacherProfile).where(TeacherProfile.id == source.teacher_profile_id)
                )
            ).scalar_one()

            used_dna = False
            if settings.USE_DNA_PIPELINE:
                # One transcript string per media source (enables multi-video merge).
                by_source: dict = {}
                for c in all_chunks:
                    by_source.setdefault(str(c.media_source_id), []).append(c.text)
                transcripts = [" ".join(parts) for parts in by_source.values()]
                try:
                    await style_mod.extract_style(
                        teacher.id, transcripts,
                        teacher_name=teacher.name, db=db, save=True,
                    )
                    used_dna = True
                    log.info("DNA style extraction complete for teacher %s", teacher.id)
                except dna_extractor.OllamaUnavailable as exc:
                    log.warning("Ollama unavailable (%s) — falling back to legacy style", exc)
                except Exception as exc:  # noqa: BLE001
                    log.warning("DNA extraction failed (%s) — falling back to legacy style", exc)

            if not used_dna:
                new_profile = await style_extractor.extract(all_chunks)
                teacher.style_profile = style_extractor.merge_profiles(
                    teacher.style_profile, new_profile
                )

            teacher.total_sources = (teacher.total_sources or 0)
            await db.commit()

            # Reward the uploader.
            await award_xp(db, source.uploaded_by, "source_processed")
            await db.commit()

    run(_impl())
