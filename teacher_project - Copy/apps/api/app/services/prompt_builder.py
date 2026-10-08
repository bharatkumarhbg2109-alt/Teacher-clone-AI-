"""Builds the adaptive teaching system prompt.

Two persona bases:
  * NEW — if ``teacher_profile.system_prompt`` is set (a DNA-extracted teacher),
    that ultra-detailed prompt is used as the persona base.
  * LEGACY — otherwise the persona is composed from ``style_profile`` fields
    (backward compatible with pre-DNA teachers).

Either way the per-turn dynamic block (student level/subject/pace + retrieved
knowledge + citation & length rules) is appended so RAG chat keeps working.
Re-evaluated every turn — never cached.
"""
from app.services.levels import (
    LEVEL_INSTRUCTIONS,
    LEVEL_LABELS,
    effective_level,
)
from app.services.retrieval import format_context_chunks

STYLE_INSTRUCTIONS = {
    "examples": "ALWAYS lead with a concrete real-world example before any theory. Make it specific and vivid.",
    "theory": "Lead with the underlying principle. State the rule clearly, then illustrate with examples.",
    "qa": "Engage Socratically. After each point, ask one targeted question. Guide discovery rather than dumping the full answer.",
    "storytelling": "Frame explanations as a short story: why it matters -> the problem -> the resolution (the concept).",
}

TONE_STYLES = {
    "friendly": "Warm, encouraging, conversational. Use 'you' and 'we'. Celebrate progress.",
    "strict": "Precise and direct. No filler. Correct errors immediately. Hold high standards.",
    "socratic": "Never just give the answer. Ask guiding questions. Let the student discover.",
    "storytelling": "Narrative voice. Use metaphors. Make the abstract feel alive.",
    "energetic": "High energy. Show genuine excitement. Use emphasis. Be contagious.",
    "calm": "Patient and measured. Never rush. Every question is valid.",
}


def build_system_prompt(teacher_profile, session, context_results, turn: int = 0) -> str:
    """Assemble the full system prompt for one chat turn."""
    dna_prompt = getattr(teacher_profile, "system_prompt", None)
    dynamic = _dynamic_block(teacher_profile, session, context_results, turn)

    if dna_prompt and dna_prompt.strip():
        # NEW: DNA persona base + the per-turn calibration/knowledge/rules.
        return f"{dna_prompt.strip()}\n\n{dynamic}"

    # LEGACY: compose the persona from style_profile, then the dynamic block.
    return f"{_legacy_identity(teacher_profile, session)}\n\n{dynamic}"


# ----------------------------------------------------------------------------
#  Per-turn dynamic block (shared by both persona bases)
# ----------------------------------------------------------------------------
def _dynamic_block(teacher_profile, session, context_results, turn: int) -> str:
    student = session.student_profile or {}
    level = effective_level(student, session.current_effective_level)
    subject = student.get("subject") or teacher_profile.subject or "this topic"
    stream = student.get("stream")
    pattern_style = student.get("learning_style", "examples")
    context_text = format_context_chunks(context_results)

    mastery = session.concept_mastery or []
    review = [c["concept"] for c in mastery if c.get("state") in ("review", "shaky")]
    review_note = (
        f"\nThe student is still shaky on: {', '.join(review[:5])}. Reinforce these when relevant."
        if review
        else ""
    )

    turn_note = ""
    if turn == 0:
        turn_note = "\n[FIRST TURN: be warm and brief; acknowledge the student's goal, then start teaching.]"
    elif turn >= 10:
        turn_note = f"\n[TURN {turn}: the student is engaged. You may add depth and nuance.]"

    ahead_note = ""
    if student.get("learn_ahead"):
        ahead_note = (
            "\nThe student wants to LEARN AHEAD of their class — go beyond the "
            "standard syllabus for their grade, but keep it understandable at the level below."
        )

    stream_note = f" (stream: {stream})" if stream else ""

    return f"""=== YOUR STUDENT (this turn) ==={turn_note}{ahead_note}{review_note}
Teaching: **{subject}**
Level: {LEVEL_LABELS.get(level, level)}{stream_note} — {LEVEL_INSTRUCTIONS.get(level, LEVEL_INSTRUCTIONS["undergrad"])}
Goal: {student.get("goal", "Learn this subject well")}
Prior knowledge: {student.get("prior_knowledge", "Not specified")}
Preferred structure: {STYLE_INSTRUCTIONS.get(pattern_style, STYLE_INSTRUCTIONS["examples"])}

=== REFERENCE KNOWLEDGE BASE ===
Prefer the content below. If the question isn't covered, say "The reference material doesn't cover this directly — from general knowledge..." and then answer.
{context_text}

=== RULES ===
1. Calibrate EVERY sentence to the {LEVEL_LABELS.get(level, level)} level — not too advanced, not too simple.
2. Cite specific reference content inline as [1], [2]… matching the numbered items above.
3. Keep it focused: {"2-3 short paragraphs" if level in ("class_6_8", "class_9_10") else "3-6 paragraphs"}.
4. End with exactly ONE Socratic follow-up question (not yes/no) to check or deepen understanding.
5. Never break character or say "As an AI". Give the final teaching answer directly — no meta-commentary about your reasoning."""


# ----------------------------------------------------------------------------
#  Legacy persona base (pre-DNA teachers)
# ----------------------------------------------------------------------------
def _legacy_identity(teacher_profile, session) -> str:
    style = teacher_profile.style_profile or {}
    student = session.student_profile or {}
    subject = student.get("subject") or teacher_profile.subject or "this topic"
    tone = style.get("tone_type", "friendly")
    sig = style.get("signature_phrases", [])[:4]
    analysis = style.get("raw_analysis", "A knowledgeable, effective educator.")
    analogy = style.get("analogy_density", 0.2)
    humor = style.get("use_of_humor", 0.1)

    phrase_note = (
        f"Occasionally use phrases like: {', '.join(repr(p) for p in sig)}." if sig else ""
    )
    analogy_note = (
        "Aim for at least one analogy per explanation."
        if analogy > 0.25
        else "Use analogies only when they genuinely clarify."
    )
    humor_note = "Include light, natural humor." if humor > 0.35 else ""

    return f"""You are an AI teacher embodying the teaching style of {teacher_profile.name}, teaching **{subject}**.

=== YOUR TEACHING IDENTITY ===
{analysis}
Tone: {TONE_STYLES.get(tone, TONE_STYLES["friendly"])}
{analogy_note}
{humor_note}
{phrase_note}""".rstrip()
