"""
SM-2 Spaced Repetition Algorithm for concept review scheduling.
Based on the SuperMemo SM-2 algorithm (1987).
"""
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import math

@dataclass
class ConceptCard:
    concept_id: str
    student_id: str
    easiness: float = 2.5       # EF: easiness factor (min 1.3)
    interval: int = 1            # days until next review
    repetitions: int = 0         # consecutive correct answers
    next_review: Optional[datetime] = None
    mastery_score: float = 0.0   # 0.0 to 1.0

def sm2_update(card: ConceptCard, quality: int) -> ConceptCard:
    """
    Update card after a review.
    quality: 0-5 (0=blackout, 3=correct with difficulty, 5=perfect)
    Returns updated card.
    """
    # Clamp quality
    quality = max(0, min(5, quality))
    
    if quality < 3:
        # Failed — reset repetitions
        card.repetitions = 0
        card.interval = 1
    else:
        # Passed
        if card.repetitions == 0:
            card.interval = 1
        elif card.repetitions == 1:
            card.interval = 6
        else:
            card.interval = round(card.interval * card.easiness)
        card.repetitions += 1
    
    # Update easiness factor
    card.easiness = max(1.3, card.easiness + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    
    # Schedule next review
    card.next_review = datetime.utcnow() + timedelta(days=card.interval)
    
    # Update mastery score (0–1)
    # Based on: repetitions, easiness, quality
    card.mastery_score = min(1.0, (card.repetitions / 8) * (card.easiness / 2.5) * (quality / 5))
    
    return card

def get_due_concepts(cards: list[ConceptCard]) -> list[ConceptCard]:
    """Return cards due for review today."""
    now = datetime.utcnow()
    return [
        c for c in cards
        if c.next_review is None or c.next_review <= now
    ]

def quality_from_checkpoint_score(score: float, max_score: float) -> int:
    """Convert checkpoint score (0–100%) to SM-2 quality (0–5)."""
    pct = score / max_score if max_score > 0 else 0
    if pct >= 0.9:  return 5
    if pct >= 0.75: return 4
    if pct >= 0.6:  return 3
    if pct >= 0.4:  return 2
    if pct >= 0.2:  return 1
    return 0
