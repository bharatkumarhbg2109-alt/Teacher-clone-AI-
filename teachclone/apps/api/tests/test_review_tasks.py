"""Tests for the spaced repetition review checkpoint generation task.

Mocks the database and quiz_generator to test the Celery task logic in isolation.
All imports used inside the task function are patched at their source module.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_uuid():
    return uuid.uuid4()


def _make_session(
    session_id=None,
    student_id=None,
    profile_id=None,
    mastery=None,
    effective_level="intermediate",
    teacher_profile=None,
):
    """Build a mock StudentSession with the given concept_mastery list."""
    session = MagicMock()
    session.id = session_id or _make_uuid()
    session.student_id = student_id or _make_uuid()
    session.teacher_profile_id = profile_id or _make_uuid()
    session.concept_mastery = mastery if mastery is not None else []
    session.current_effective_level = effective_level
    session.teacher_profile = teacher_profile  # may be None
    return session


def _make_profile(subject="mathematics"):
    profile = MagicMock()
    profile.subject = subject
    return profile


def _make_quiz_data(questions=None):
    """Return a dict shaped like quiz_generator.generate_checkpoint output."""
    if questions is None:
        questions = [
            {
                "id": "q1",
                "type": "mcq",
                "concept": "algebra",
                "question": "What is 2+2?",
                "options": {"A": "3", "B": "4", "C": "5", "D": "6"},
                "correct_answer": "B",
                "explanation": "Basic arithmetic.",
                "difficulty": "easy",
            },
            {
                "id": "q2",
                "type": "true_false",
                "concept": "algebra",
                "question": "x^2 is always non-negative for real x.",
                "correct_answer": "true",
                "explanation": "Squares of real numbers are >= 0.",
                "difficulty": "medium",
            },
        ]
    return {"title": "Review: algebra", "questions": questions}


def _make_message(content="Some assistant reply", role="assistant"):
    msg = MagicMock()
    msg.content = content
    msg.role = role
    return msg


def _run_task_with_mocks(mock_db_session, mock_quiz_gen):
    """Helper to invoke generate_review_checkpoints with properly patched dependencies.

    All patches target the *source* modules since review_tasks imports them
    locally inside the task function body.  We also patch the ORM model
    classes so SQLAlchemy mapper init doesn't fire during tests.
    """
    # Dummy classes to stand in for the real ORM models — avoids mapper init.
    # Use MagicMock so attribute access (e.g. StudentSession.concept_mastery)
    # returns a chainable mock instead of raising AttributeError.
    _FakeStudentSession = MagicMock()
    _FakeStudentSession.__name__ = "StudentSession"
    _FakeMessage = MagicMock()
    _FakeMessage.__name__ = "Message"

    # _FakeQuiz needs to store kwargs as real attributes so tests can inspect
    # e.g. quiz.kind == "checkpoint".
    class _FakeQuiz:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    _FakeQuiz.__name__ = "Quiz"

    with (
        patch("app.db.session.AsyncSessionLocal") as mock_factory,
        patch("app.services.quiz_generator.quiz_generator", mock_quiz_gen),
        patch("app.models.student_session.StudentSession", _FakeStudentSession),
        patch("app.models.quiz.Quiz", _FakeQuiz),
        patch("app.models.message.Message", _FakeMessage),
        patch("sqlalchemy.select", side_effect=lambda *a, **kw: MagicMock()),
    ):
        # Make AsyncSessionLocal() return our mock_db_session via async context manager
        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_db_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)
        mock_factory.return_value = mock_cm

        # Import and call the task (imports happen inside the function)
        from app.tasks.review_tasks import generate_review_checkpoints
        return generate_review_checkpoints()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db_session():
    """Provide an AsyncSession mock that tracks added objects."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


@pytest.fixture
def mock_quiz_generator():
    """Provide a mock quiz_generator with generate_checkpoint returning valid data."""
    gen = MagicMock()
    gen.generate_checkpoint = AsyncMock(return_value=_make_quiz_data())
    return gen


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGenerateReviewCheckpoints:
    """Tests for generate_review_checkpoints Celery task."""

    def test_creates_checkpoint_for_shaky_concept(self, mock_db_session, mock_quiz_generator):
        """A session with a 'shaky' concept should produce a quiz checkpoint."""
        mastery = [
            {
                "topic": "algebra",
                "mastery_state": "shaky",
                "last_reviewed_at": None,
            }
        ]
        session = _make_session(mastery=mastery, teacher_profile=_make_profile())
        msg = _make_message("Algebra is the study of symbols.")

        # Wire up the mock DB to return session and messages
        mock_result_sessions = MagicMock()
        mock_result_sessions.scalars.return_value.all.return_value = [session]

        mock_result_msgs = MagicMock()
        mock_result_msgs.scalars.return_value.all.return_value = [msg]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_sessions, mock_result_msgs]
        )

        result = _run_task_with_mocks(mock_db_session, mock_quiz_generator)

        # Verify quiz was created
        assert mock_db_session.add.call_count == 1
        added_quiz = mock_db_session.add.call_args[0][0]
        assert added_quiz.kind == "checkpoint"
        assert len(added_quiz.questions) == 2

        # Verify last_reviewed_at was updated
        assert mastery[0]["last_reviewed_at"] is not None

        # Verify quiz_generator was called
        mock_quiz_generator.generate_checkpoint.assert_called_once()
        call_kwargs = mock_quiz_generator.generate_checkpoint.call_args[1]
        assert call_kwargs["concept"] == "algebra"
        assert call_kwargs["num"] == 2

    def test_skips_mastered_concepts(self, mock_db_session, mock_quiz_generator):
        """Concepts with mastery_state 'mastered' should not generate checkpoints."""
        mastery = [
            {
                "topic": "geometry",
                "mastery_state": "mastered",
            },
            {
                "topic": "algebra",
                "mastery_state": "learning",
            },
        ]
        session = _make_session(mastery=mastery, teacher_profile=_make_profile())

        mock_result_sessions = MagicMock()
        mock_result_sessions.scalars.return_value.all.return_value = [session]
        # Messages query returns empty list (no assistant messages)
        mock_result_msgs = MagicMock()
        mock_result_msgs.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_sessions, mock_result_msgs]
        )

        result = _run_task_with_mocks(mock_db_session, mock_quiz_generator)

        # No quizzes should be created
        assert mock_db_session.add.call_count == 0
        mock_quiz_generator.generate_checkpoint.assert_not_called()

    def test_skips_recently_reviewed_concept(self, mock_db_session, mock_quiz_generator):
        """Concepts reviewed within 24h should be skipped to avoid spam."""
        recent_time = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        mastery = [
            {
                "topic": "calculus",
                "mastery_state": "review_due",
                "last_reviewed_at": recent_time,
            }
        ]
        session = _make_session(mastery=mastery, teacher_profile=_make_profile())

        mock_result_sessions = MagicMock()
        mock_result_sessions.scalars.return_value.all.return_value = [session]
        mock_result_msgs = MagicMock()
        mock_result_msgs.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_sessions, mock_result_msgs]
        )

        result = _run_task_with_mocks(mock_db_session, mock_quiz_generator)

        assert mock_db_session.add.call_count == 0
        mock_quiz_generator.generate_checkpoint.assert_not_called()

    def test_handles_quiz_generator_failure(self, mock_db_session, mock_quiz_generator):
        """If quiz_generator raises, the task should log a warning and continue."""
        mock_quiz_generator.generate_checkpoint = AsyncMock(
            side_effect=RuntimeError("LLM unavailable")
        )
        mastery = [
            {"topic": "algebra", "mastery_state": "shaky", "last_reviewed_at": None},
            {"topic": "geometry", "mastery_state": "review_due", "last_reviewed_at": None},
        ]
        session = _make_session(mastery=mastery, teacher_profile=_make_profile())

        mock_result_sessions = MagicMock()
        mock_result_sessions.scalars.return_value.all.return_value = [session]
        mock_result_msgs = MagicMock()
        mock_result_msgs.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_sessions, mock_result_msgs]
        )

        # Should not raise — failures are caught per-concept
        result = _run_task_with_mocks(mock_db_session, mock_quiz_generator)

        # No quizzes added (both failed)
        assert mock_db_session.add.call_count == 0
        assert result["reviews_created"] == 0

    def test_no_sessions_with_mastery(self, mock_db_session, mock_quiz_generator):
        """If no sessions have mastery data, task returns 0 created."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = _run_task_with_mocks(mock_db_session, mock_quiz_generator)

        assert result["reviews_created"] == 0
        mock_quiz_generator.generate_checkpoint.assert_not_called()

    def test_session_without_teacher_profile_is_skipped(self, mock_db_session, mock_quiz_generator):
        """Sessions with no teacher profile should be skipped."""
        mastery = [{"topic": "algebra", "mastery_state": "shaky"}]
        session = _make_session(mastery=mastery, teacher_profile=None)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [session]

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = _run_task_with_mocks(mock_db_session, mock_quiz_generator)

        assert result["reviews_created"] == 0
        mock_quiz_generator.generate_checkpoint.assert_not_called()

    def test_multiple_sessions_multiple_concepts(self, mock_db_session, mock_quiz_generator):
        """Test with multiple sessions and multiple concepts needing review."""
        mastery1 = [
            {"topic": "algebra", "mastery_state": "shaky", "last_reviewed_at": None},
            {"topic": "geometry", "mastery_state": "review_due", "last_reviewed_at": None},
        ]
        mastery2 = [
            {"topic": "calculus", "mastery_state": "shaky", "last_reviewed_at": None},
        ]
        session1 = _make_session(mastery=mastery1, teacher_profile=_make_profile("math"))
        session2 = _make_session(mastery=mastery2, teacher_profile=_make_profile("math"))

        msg1 = _make_message("Algebra lesson content")
        msg2 = _make_message("Calculus lesson content")

        mock_result_sessions = MagicMock()
        mock_result_sessions.scalars.return_value.all.return_value = [session1, session2]

        # Each session needs its own messages query
        mock_result_msgs1 = MagicMock()
        mock_result_msgs1.scalars.return_value.all.return_value = [msg1]
        mock_result_msgs2 = MagicMock()
        mock_result_msgs2.scalars.return_value.all.return_value = [msg2]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_sessions, mock_result_msgs1, mock_result_msgs2]
        )

        result = _run_task_with_mocks(mock_db_session, mock_quiz_generator)

        # 3 total checkpoints (2 from session1 + 1 from session2)
        assert result["reviews_created"] == 3
        assert mock_db_session.add.call_count == 3
        assert mock_quiz_generator.generate_checkpoint.call_count == 3

    def test_concept_with_topic_fallback(self, mock_db_session, mock_quiz_generator):
        """When 'topic' key is missing, should fall back to 'concept' key."""
        mastery = [
            {
                "concept": "photosynthesis",
                "mastery_state": "review_due",
                "last_reviewed_at": None,
                # Note: no 'topic' key
            }
        ]
        session = _make_session(mastery=mastery, teacher_profile=_make_profile("biology"))

        mock_result_sessions = MagicMock()
        mock_result_sessions.scalars.return_value.all.return_value = [session]

        mock_result_msgs = MagicMock()
        mock_result_msgs.scalars.return_value.all.return_value = []

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_sessions, mock_result_msgs]
        )

        result = _run_task_with_mocks(mock_db_session, mock_quiz_generator)

        assert result["reviews_created"] == 1
        call_kwargs = mock_quiz_generator.generate_checkpoint.call_args[1]
        assert call_kwargs["concept"] == "photosynthesis"

    def test_uses_recent_messages_as_context(self, mock_db_session, mock_quiz_generator):
        """Quiz generator should receive recent assistant messages as context."""
        mastery = [{"topic": "physics", "mastery_state": "shaky", "last_reviewed_at": None}]
        session = _make_session(mastery=mastery, teacher_profile=_make_profile("physics"))

        msg1 = _make_message("Newton's first law states...")
        msg2 = _make_message("Energy is conserved in...")

        mock_result_sessions = MagicMock()
        mock_result_sessions.scalars.return_value.all.return_value = [session]

        mock_result_msgs = MagicMock()
        mock_result_msgs.scalars.return_value.all.return_value = [msg1, msg2]

        mock_db_session.execute = AsyncMock(
            side_effect=[mock_result_sessions, mock_result_msgs]
        )

        result = _run_task_with_mocks(mock_db_session, mock_quiz_generator)

        call_kwargs = mock_quiz_generator.generate_checkpoint.call_args[1]
        assert "Newton" in call_kwargs["context_text"]
        assert "Energy" in call_kwargs["context_text"]
        assert call_kwargs["subject"] == "physics"
        assert call_kwargs["level_label"] == "intermediate"

    def test_empty_mastery_list(self, mock_db_session, mock_quiz_generator):
        """Sessions with empty mastery list should be skipped."""
        session = _make_session(mastery=[], teacher_profile=_make_profile())

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [session]

        mock_db_session.execute = AsyncMock(return_value=mock_result)

        result = _run_task_with_mocks(mock_db_session, mock_quiz_generator)

        assert result["reviews_created"] == 0
