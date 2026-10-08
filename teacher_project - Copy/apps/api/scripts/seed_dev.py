"""Seed a demo public teacher (+ content) so Discover and chat have data.

Run:  python -m scripts.seed_dev
Embeddings are attempted only if an OpenAI key is set; the rest works regardless.
"""
import asyncio

from sqlalchemy import select

from app.config import settings
from app.db.init import init_models
from app.db.session import AsyncSessionLocal
from app.models.media_source import MediaSource
from app.models.teacher_profile import TeacherProfile
from app.models.transcript_chunk import TranscriptChunk
from app.models.user import User
from app.models.user_stats import UserStats

DEMO_CHUNKS = [
    "Newton's first law says an object stays at rest or in uniform motion unless a net force acts on it. This is also called the law of inertia.",
    "Newton's second law relates force, mass and acceleration: F = m times a. A bigger force gives a bigger acceleration; a bigger mass resists acceleration.",
    "Newton's third law states that for every action there is an equal and opposite reaction. When you push a wall, the wall pushes back on you with the same force.",
    "Momentum is mass times velocity. In a closed system with no external force, total momentum is conserved.",
    "Friction is a force that opposes relative motion between surfaces. It converts kinetic energy into heat.",
    "Work is force times displacement in the direction of the force. Energy is the capacity to do work, measured in joules.",
]

DEMO_STYLE = {
    "vocabulary_level": "intermediate",
    "vocabulary_score": 8.5,
    "tone_type": "friendly",
    "tone_confidence": 0.8,
    "explanation_pattern": "example_first",
    "analogy_density": 0.4,
    "avg_sentence_length": 14.0,
    "use_of_humor": 0.2,
    "use_of_questions": 1.5,
    "signature_phrases": ["let's think about", "here's the key idea"],
    "vocabulary_samples": ["force", "acceleration", "momentum", "inertia"],
    "pacing": "moderate",
    "explanation_depth": "moderate",
    "subjects": ["Physics"],
    "raw_analysis": "A friendly physics teacher who leads with everyday examples before stating the rule, and checks understanding with questions.",
}


async def main() -> None:
    await init_models()
    async with AsyncSessionLocal() as db:
        user = (
            await db.execute(select(User).where(User.email == settings.DEV_USER_EMAIL))
        ).scalar_one_or_none()
        if not user:
            user = User(clerk_id="dev_local_user", email=settings.DEV_USER_EMAIL,
                        full_name=settings.DEV_USER_NAME, plan="creator")
            db.add(user)
            await db.flush()
            db.add(UserStats(user_id=user.id))

        existing = (
            await db.execute(
                select(TeacherProfile).where(TeacherProfile.name == "Physics with Newton")
            )
        ).scalar_one_or_none()
        if existing:
            print("Demo teacher already exists:", existing.id)
            await db.commit()
            return

        teacher = TeacherProfile(
            user_id=user.id,
            name="Physics with Newton",
            description="Clear, example-first physics for school and beyond.",
            subject="Physics",
            tts_voice="onyx",
            style_profile=DEMO_STYLE,
            total_sources=1,
            visibility="public",
            session_count=42,
            unique_learners=27,
        )
        db.add(teacher)
        await db.flush()

        source = MediaSource(
            teacher_profile_id=teacher.id,
            uploaded_by=user.id,
            source_type="doc_upload",
            file_name="newton_notes.txt",
            status="completed",
            transcript_chunks=len(DEMO_CHUNKS),
        )
        db.add(source)
        await db.flush()

        chunks = [
            TranscriptChunk(
                media_source_id=source.id,
                chunk_index=i,
                text=text,
                page=1,
                content_type="document",
                token_count=len(text.split()),
            )
            for i, text in enumerate(DEMO_CHUNKS)
        ]
        db.add_all(chunks)
        await db.commit()

        # Embed if possible so retrieval works in the demo.
        if settings.EMBEDDING_PROVIDER in ("hash", "local") or settings.OPENAI_API_KEY:
            try:
                from app.services.embedder import embedder
                from app.services.vector_store import ChunkPoint, vector_store

                await vector_store.ensure_collection()
                vecs = await embedder.embed_texts([c.text for c in chunks])
                points = [
                    ChunkPoint(
                        id=str(c.id),
                        dense_vector=v,
                        sparse_vector=embedder.compute_sparse_vector(c.text),
                        payload={
                            "text": c.text, "media_source_id": str(source.id),
                            "teacher_profile_id": str(teacher.id), "start_time": None,
                            "end_time": None, "page": 1, "chunk_index": c.chunk_index,
                            "content_type": "document",
                        },
                    )
                    for c, v in zip(chunks, vecs)
                ]
                await vector_store.upsert_chunks(points)
                for c in chunks:
                    c.embedding_id = str(c.id)
                await db.commit()
                print("Embedded demo chunks into Qdrant.")
            except Exception as exc:
                print("Skipped embedding:", exc)

        print("Seed complete. Demo teacher:", teacher.id)


if __name__ == "__main__":
    asyncio.run(main())
