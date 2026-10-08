"""Grade ladder — the ordered levels the teacher calibrates to.

Ascending difficulty. Used for calibration, "learn ahead", and checkpoint-driven
adaptation (stepping up/down).
"""

LEVEL_ORDER = [
    "class_6_8",
    "class_9_10",
    "class_11_12",
    "undergrad",
    "postgrad",
    "professional",
]

LEVEL_LABELS = {
    "class_6_8": "Class 6-8",
    "class_9_10": "Class 9-10",
    "class_11_12": "Class 11-12",
    "undergrad": "Graduation",
    "postgrad": "Post-graduate",
    "professional": "Working professional",
}

# Per-level vocabulary + depth guidance. This is what makes the teacher feed
# "not too much, not too little".
LEVEL_INSTRUCTIONS = {
    "class_6_8": (
        "Talk to an 11-13 year old. Very simple, short sentences. Everyday analogies "
        "(sports, food, games, phones). Explain any new word the moment you use it. "
        "Show a concrete example before any rule. No heavy jargon."
    ),
    "class_9_10": (
        "Talk to a 14-16 year old (secondary school). Clear, simple language. Relate "
        "to school subjects and daily life. Brief analogies. Define technical terms "
        "right after using them. Include one worked example per concept."
    ),
    "class_11_12": (
        "Senior-secondary level (16-18). Board/entrance-exam depth. Precise terminology "
        "is fine if defined once. Use exam-style examples and step-by-step derivations "
        "where relevant. Connect to the chosen stream."
    ),
    "undergrad": (
        "University level. Assume solid school fundamentals. Use precise terminology; "
        "define specialised sub-field terms. Mention trade-offs, assumptions and caveats. "
        "Reference how ideas connect across the subject."
    ),
    "postgrad": (
        "Expert vocabulary assumed. Focus on nuance, edge cases, proofs/derivations and "
        "depth over basics. Compare competing approaches and reference established work."
    ),
    "professional": (
        "Peer-level, applied communication. Dense and precise. Use jargon freely, assume "
        "hands-on experience, and emphasise practical application, pitfalls and best practice."
    ),
}


def index_of(level: str) -> int:
    try:
        return LEVEL_ORDER.index(level)
    except ValueError:
        return LEVEL_ORDER.index("undergrad")


def step_level(level: str, direction: str) -> str:
    """direction: 'simpler' (down) | 'deeper' (up)."""
    i = index_of(level)
    if direction == "simpler":
        i = max(0, i - 1)
    elif direction == "deeper":
        i = min(len(LEVEL_ORDER) - 1, i + 1)
    return LEVEL_ORDER[i]


def effective_level(student_profile: dict, current_effective_level: str | None) -> str:
    """Resolve the level the teacher should actually teach at:
    the drifted effective level if set, else target (when learning ahead),
    else the stated level."""
    if current_effective_level:
        return current_effective_level
    if student_profile.get("learn_ahead"):
        target = student_profile.get("target_level")
        if target:
            return target
        return step_level(student_profile.get("level", "undergrad"), "deeper")
    return student_profile.get("level", "undergrad")
