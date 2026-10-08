"""Unit and integration tests for the SM-2 spaced repetition scheduler."""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock
import pytest

from app.services.sm2_scheduler import (
    ConceptCard,
    get_due_concepts,
    quality_from_checkpoint_score,
    sm2_update,
)
from app.routers.quizzes import _update_mastery


def test_card_initial_defaults():
    card = ConceptCard(concept_id="torque", student_id="student-1")
    assert card.easiness == 2.5
    assert card.interval == 1
    assert card.repetitions == 0
    assert card.next_review is None
    assert card.mastery_score == 0.0


def test_sm2_first_successful_repetition():
    base_time = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
    card = ConceptCard(concept_id="torque", student_id="student-1")
    
    # Perfect answer (quality=5)
    updated = sm2_update(card, quality=5, now=base_time)
    assert updated.repetitions == 1
    assert updated.interval == 1
    # EF formula: 2.5 + 0.1 - (5 - 5) * (...) = 2.6
    assert round(updated.easiness, 2) == 2.6
    assert updated.next_review == base_time + timedelta(days=1)
    assert updated.mastery_score > 0.0


def test_sm2_second_and_third_repetition():
    base_time = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
    card = ConceptCard(concept_id="torque", student_id="student-1")
    
    # Repetition 1
    card = sm2_update(card, quality=4, now=base_time)
    assert card.repetitions == 1
    assert card.interval == 1

    # Repetition 2
    card = sm2_update(card, quality=4, now=base_time)
    assert card.repetitions == 2
    assert card.interval == 6

    # Repetition 3: interval = round(6 * EF)
    ef_before = card.easiness
    card = sm2_update(card, quality=4, now=base_time)
    assert card.repetitions == 3
    expected_interval = round(6 * ef_before)
    assert card.interval == expected_interval
    assert card.next_review == base_time + timedelta(days=expected_interval)


def test_sm2_failure_resets_repetitions_and_interval():
    base_time = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
    # Advanced card with 4 consecutive repetitions
    card = ConceptCard(
        concept_id="faraday_law",
        student_id="student-1",
        easiness=2.5,
        interval=35,
        repetitions=4,
    )
    # Failure (quality=1)
    updated = sm2_update(card, quality=1, now=base_time)
    assert updated.repetitions == 0
    assert updated.interval == 1
    assert updated.next_review == base_time + timedelta(days=1)


def test_sm2_minimum_easiness_floor():
    base_time = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
    card = ConceptCard(
        concept_id="hard_concept",
        student_id="student-1",
        easiness=1.4,
        interval=1,
        repetitions=0,
    )
    # Repeated complete blackouts
    for _ in range(5):
        card = sm2_update(card, quality=0, now=base_time)
    assert card.easiness == 1.3  # clamped to minimum 1.3


def test_quality_from_checkpoint_score():
    assert quality_from_checkpoint_score(0, 0) == 0
    assert quality_from_checkpoint_score(0, 10) == 0
    assert quality_from_checkpoint_score(3, 10) == 1
    assert quality_from_checkpoint_score(5, 10) == 2
    assert quality_from_checkpoint_score(7, 10) == 3
    assert quality_from_checkpoint_score(8, 10) == 4
    assert quality_from_checkpoint_score(10, 10) == 5


def test_get_due_concepts():
    now = datetime(2026, 10, 9, 12, 0, 0, tzinfo=timezone.utc)
    card_due_none = ConceptCard("c1", "s1", next_review=None)
    card_due_past = ConceptCard("c2", "s1", next_review=now - timedelta(days=1))
    card_due_now = ConceptCard("c3", "s1", next_review=now)
    card_future = ConceptCard("c4", "s1", next_review=now + timedelta(days=2))

    due = get_due_concepts([card_due_none, card_due_past, card_due_now, card_future], now=now)
    due_ids = {c.concept_id for c in due}
    assert due_ids == {"c1", "c2", "c3"}
    assert "c4" not in due_ids


def test_quiz_mastery_sm2_integration():
    mock_session = MagicMock()
    mock_session.student_id = "student-123"
    mock_session.concept_mastery = []

    concept_stats = {
        "Angular Momentum": (4, 4),   # 100% -> quality 5
        "Lenz Law": (1, 4),           # 25% -> quality 1
    }

    mastered, review = _update_mastery(mock_session, concept_stats)
    assert "Angular Momentum" in mastered
    assert "Lenz Law" in review

    # Check that SM-2 fields are properly recorded
    mastery_dict = {m["concept"]: m for m in mock_session.concept_mastery}
    
    am = mastery_dict["Angular Momentum"]
    assert am["repetitions"] == 1
    assert am["interval"] == 1
    assert am["easiness"] == 2.6
    assert am["next_review_date"] is not None
    assert am["mastery_score"] > 0

    ll = mastery_dict["Lenz Law"]
    assert ll["repetitions"] == 0
    assert ll["interval"] == 1
    assert ll["easiness"] < 2.5
    assert ll["next_review_date"] is not None
