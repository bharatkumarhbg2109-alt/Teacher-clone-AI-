"""SM-2 Spaced Repetition Algorithm for concept review scheduling.

Based on Piotr Wozniak's SuperMemo SM-2 algorithm (1987).
Calculates repetition intervals, easiness factors, and review due dates
based on response quality ratings (0-5).
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


@dataclass
class ConceptCard:
    concept_id: str
    student_id: str
    easiness: float = 2.5       # EF: easiness factor (minimum 1.3)
    interval: int = 1            # days until next review
    repetitions: int = 0         # consecutive successful reviews
    next_review: Optional[datetime] = None
    mastery_score: float = 0.0   # 0.0 to 1.0


def sm2_update(card: ConceptCard, quality: int, now: Optional[datetime] = None) -> ConceptCard:
    """Update concept card after review based on response quality (0-5).

    quality: 0-5
      0: complete blackout
      1: incorrect response; correct one remembered
      2: incorrect response; correct one seemed easy to recall
      3: correct response with serious difficulty
      4: correct response after a hesitation
      5: perfect response

    Returns updated card with new repetitions count, easiness, interval, and next_review.
    """
    quality = max(0, min(5, quality))
    ref_time = now or datetime.now(timezone.utc)

    if quality < 3:
        # Failed review: reset consecutive repetitions, interval restarts at 1 day
        card.repetitions = 0
        card.interval = 1
    else:
        # Successful review: step through SM-2 interval progression
        if card.repetitions == 0:
            card.interval = 1
        elif card.repetitions == 1:
            card.interval = 6
        else:
            card.interval = max(1, round(card.interval * card.easiness))
        card.repetitions += 1

    # Update Easiness Factor (EF)
    # EF' = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    card.easiness = max(1.3, card.easiness + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))

    # Schedule next review timestamp
    card.next_review = ref_time + timedelta(days=card.interval)

    # Calculate normalized mastery score [0.0, 1.0]
    card.mastery_score = min(
        1.0,
        (min(card.repetitions, 6) / 6.0) * (min(card.easiness, 2.5) / 2.5) * (quality / 5.0),
    )

    return card


def get_due_concepts(cards: list[ConceptCard], now: Optional[datetime] = None) -> list[ConceptCard]:
    """Return cards due for review as of the reference time."""
    ref_time = now or datetime.now(timezone.utc)
    return [
        c for c in cards
        if c.next_review is None or c.next_review <= ref_time
    ]


def quality_from_checkpoint_score(score: float, max_score: float) -> int:
    """Convert score (e.g. correct answers out of total) to SM-2 quality rating (0-5)."""
    if max_score <= 0:
        return 0
    pct = score / max_score
    if pct >= 0.9:
        return 5
    if pct >= 0.75:
        return 4
    if pct >= 0.6:
        return 3
    if pct >= 0.4:
        return 2
    if pct >= 0.2:
        return 1
    return 0
