"""Analyze uploaded-video keyframes (diagrams, slides, equations, code) with
Claude vision and store them as visual chunks alongside the audio transcript."""
import asyncio
import base64
import glob
import os
import tempfile

from sqlalchemy import func, select

from app.tasks._util import run
from app.worker import celery_app


async def _extract_keyframes(video_path: str, frames_dir: str) -> list[dict]:
    cmd = [
        "ffmpeg", "-i", video_path, "-vf", "select=gt(scene\\,0.35)",
        "-vsync", "vfr", f"{frames_dir}/frame_%06d.jpg", "-loglevel", "quiet", "-y",
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()
    files = sorted(glob.glob(f"{frames_dir}/frame_*.jpg"))
    return [{"path": f, "timestamp": i * 3.5} for i, f in enumerate(files)]


@celery_app.task(name="ai.analyze_frames", bind=True)
def analyze_frames(self, media_source_id: str):
    from app.db.session import AsyncSessionLocal
    from app.models.media_source import MediaSource
    from app.models.transcript_chunk import TranscriptChunk
    from app.services import llm
    from app.services.embedder import embedder
    from app.services.storage import storage_service
    from app.services.vector_store import ChunkPoint, vector_store

    async def _impl():
        async with AsyncSessionLocal() as db:
            source = (
                await db.execute(select(MediaSource).where(MediaSource.id == media_source_id))
            ).scalar_one()
            if source.source_type != "video_upload" or not source.storage_key:
                return
            profile_id = str(source.teacher_profile_id)

            with tempfile.TemporaryDirectory() as tmp:
                video_path = os.path.join(tmp, "video.mp4")
                storage_service.download_to_path(source.storage_key, video_path)
                frames_dir = os.path.join(tmp, "frames")
                os.makedirs(frames_dir)
                frames = await _extract_keyframes(video_path, frames_dir)
                if not frames:
                    return

                visual: list[dict] = []
                BATCH = 4
                instruction = (
                    "These are keyframes from an educational video. For any frame showing a "
                    "diagram, equation, code, slide text, whiteboard or chart, describe it and "
                    "transcribe any visible text verbatim. Ignore plain talking-head frames. "
                    "Give one short paragraph per informative frame."
                )
                for i in range(0, len(frames), BATCH):
                    batch = frames[i : i + BATCH]
                    b64s = []
                    for f in batch:
                        with open(f["path"], "rb") as fh:
                            b64s.append(base64.b64encode(fh.read()).decode())
                    try:
                        desc = await llm.vision_describe(b64s, instruction)
                    except Exception:
                        desc = ""
                    if desc.strip():
                        visual.append({"text": desc.strip(), "ts": batch[0]["timestamp"]})

                if not visual:
                    return

                last_idx = (
                    await db.execute(
                        select(func.max(TranscriptChunk.chunk_index)).where(
                            TranscriptChunk.media_source_id == media_source_id
                        )
                    )
                ).scalar() or 0

                new_chunks = []
                for j, vd in enumerate(visual):
                    c = TranscriptChunk(
                        media_source_id=media_source_id,
                        chunk_index=last_idx + j + 1,
                        text=f"[VISUAL ~{int(vd['ts'])}s] {vd['text']}",
                        start_time=vd["ts"],
                        end_time=vd["ts"] + 10,
                        content_type="visual",
                        token_count=len(vd["text"].split()),
                    )
                    db.add(c)
                    new_chunks.append(c)
                await db.flush()

                dense = await embedder.embed_texts([c.text for c in new_chunks])
                await vector_store.ensure_collection()
                points = []
                for chunk, vec in zip(new_chunks, dense):
                    points.append(
                        ChunkPoint(
                            id=str(chunk.id),
                            dense_vector=vec,
                            sparse_vector=embedder.compute_sparse_vector(chunk.text),
                            payload={
                                "text": chunk.text,
                                "media_source_id": media_source_id,
                                "teacher_profile_id": profile_id,
                                "start_time": chunk.start_time,
                                "end_time": chunk.end_time,
                                "page": None,
                                "chunk_index": chunk.chunk_index,
                                "content_type": "visual",
                            },
                        )
                    )
                    chunk.embedding_id = str(chunk.id)
                await vector_store.upsert_chunks(points)
                await db.commit()

    run(_impl())
    return {"status": "done", "media_source_id": media_source_id}
