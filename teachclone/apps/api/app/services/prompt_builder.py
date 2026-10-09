"""Builds the adaptive teaching system prompt with high-fidelity DNA persona injection.

Two persona bases:
  * DNA-first — uses the compiled DNA system prompt (from teacher_profile.system_prompt
    or synthesized from style_profile DNA layers), plus a mandatory persona execution block.
  * Legacy fallback — composed from style_profile fields for pre-DNA teachers.

The per-turn dynamic block (student level/subject/pace + retrieved knowledge + citation
and length rules) is appended to guarantee grounded answers with citations.
"""
import json
import re
from typing import Any

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


def _extract_style_data(teacher_profile: Any) -> dict:
    style = getattr(teacher_profile, "style_profile", None)
    if not style:
        return {}
    if isinstance(style, str):
        try:
            return json.loads(style)
        except Exception:
            return {}
    if isinstance(style, dict):
        return style
    return {}


def _get_signature_phrases(style: dict, dna_prompt: str) -> list[str]:
    phrases = []
    if style.get("signature_phrases"):
        for p in style["signature_phrases"]:
            if p and str(p).strip():
                phrases.append(str(p).strip())
    voc = style.get("vocabulary_dna", {})
    if isinstance(voc, dict) and voc.get("top_phrases"):
        for p in voc["top_phrases"]:
            if p and str(p).strip() and str(p).strip() not in phrases:
                phrases.append(str(p).strip())

    # Fallback to scanning dna_prompt for phrases if style was sparse
    if len(phrases) < 3 and dna_prompt:
        matches = re.findall(r"['\"]([^'\"]{4,50})['\"]", dna_prompt)
        for m in matches:
            m_clean = m.strip()
            if m_clean and m_clean not in phrases and not m_clean.startswith("http"):
                phrases.append(m_clean)

    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped = []
    for p in phrases:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            deduped.append(p)
    return deduped


def _get_explanation_order(style: dict) -> list[str]:
    exp = style.get("explanation_dna", {})
    if isinstance(exp, dict) and exp.get("explanation_order"):
        order = exp["explanation_order"]
        if isinstance(order, list):
            return [str(s).strip() for s in order if s and str(s).strip()]
    return [
        "Intuitive hook or scenario",
        "Core principle & physical mechanism",
        "Step-by-step concrete application",
        "Socratic check / thought-provoking question",
    ]


def _get_opening_examples(style: dict) -> list[str]:
    exp = style.get("explanation_dna", {})
    if isinstance(exp, dict) and exp.get("opening_examples"):
        exs = exp["opening_examples"]
        if isinstance(exs, list):
            return [str(e).strip() for e in exs if e and str(e).strip()]
    return []


def _get_socratic_questions(style: dict) -> list[str]:
    q_dna = style.get("question_dna", {})
    if isinstance(q_dna, dict) and q_dna.get("actual_questions"):
        qs = q_dna["actual_questions"]
        if isinstance(qs, list):
            return [str(q).strip() for q in qs if q and str(q).strip()]
    return []


def _persona_mandate_block(
    teacher_name: str,
    sig_phrases: list[str],
    explanation_order: list[str],
    opening_examples: list[str],
    socratic_questions: list[str] | None = None,
) -> str:
    parts = [
        "=== MANDATORY TEACHER PERSONA EXECUTION ===",
        f"You are {teacher_name}. The student came to YOU because they want YOUR specific teaching voice, "
        "not a neutral textbook or generic automated assistant.",
    ]

    if sig_phrases:
        formatted_phrases = "\n".join(f"  - \"{p}\"" for p in sig_phrases[:12])
        parts.append(
            "\n1. SIGNATURE PHRASES & VERBAL HABITS (MANDATORY):\n"
            "You MUST naturally weave at least 3 of your signature phrases/patterns into your response:\n"
            f"{formatted_phrases}\n"
            "Students recognize you by these characteristic verbal habits. Do not omit them."
        )

    if explanation_order:
        steps_summary = " -> ".join(explanation_order)
        formatted_steps = "\n".join(f"  Step {i}: {step}" for i, step in enumerate(explanation_order, 1))
        parts.append(
            f"\n2. EXPLANATION STRUCTURE (LAYER 2 DNA):\n"
            f"Follow your exact explanation progression ({steps_summary}):\n"
            f"{formatted_steps}\n"
            "- Step 1: Open immediately with your characteristic hook or intuitive analogy.\n"
            "- Step 2: Establish the core principle or mechanism clearly.\n"
            "- Step 3: Walk through the concrete application or step-by-step breakdown.\n"
            "- Final Step: Conclude your explanation with a direct Socratic thought question (ending with '?')."
        )

    if opening_examples:
        formatted_openings = "\n".join(f"  - \"{ex}\"" for ex in opening_examples[:3])
        parts.append(
            f"\n3. HOW YOU TYPICALLY OPEN EXPLANATIONS:\n"
            f"{formatted_openings}"
        )

    if socratic_questions:
        formatted_qs = "\n".join(f"  - \"{q}\"" for q in socratic_questions[:3])
        parts.append(
            f"\n4. HOW YOU CONCLUDE WITH A SOCRATIC QUESTION:\n"
            "End your answer with a thought-provoking conceptual question styled like:\n"
            f"{formatted_qs}"
        )

    parts.append(
        "\n5. FORBIDDEN AI BEHAVIORS (STRICT):\n"
        "- NEVER begin with generic bot greetings or disclaimers: "
        "\"Certainly!\", \"Sure!\", \"Sure, I can help with that\", \"Great question!\", "
        "\"That's an interesting question!\", \"As an AI language model\", \"Hello! How can I assist you?\".\n"
        f"- Open directly in character as {teacher_name} from the very first word.\n"
        "- Never say \"I am an AI\" or break character.\n"
        "- NEVER end your response with a flat statement or summary — the final sentence MUST be a Socratic question ending with '?'."
    )

    return "\n".join(parts)


def build_system_prompt(teacher_profile: Any, session: Any, context_results: Any, turn: int = 0) -> str:
    """Assemble the full system prompt for one chat turn."""
    style = _extract_style_data(teacher_profile)
    dna_prompt = getattr(teacher_profile, "system_prompt", None) or ""
    teacher_name = getattr(teacher_profile, "name", "the teacher")

    # If dna_prompt is empty but style contains DNA layers, synthesize full DNA system prompt
    if not dna_prompt.strip() and ("vocabulary_dna" in style or "explanation_dna" in style or "signature_phrases" in style):
        from app.services import dna_extractor
        dna_prompt = dna_extractor._fallback_system_prompt(style)

    sig_phrases = _get_signature_phrases(style, dna_prompt)
    explanation_order = _get_explanation_order(style)
    opening_examples = _get_opening_examples(style)
    socratic_questions = _get_socratic_questions(style)

    mandate = _persona_mandate_block(teacher_name, sig_phrases, explanation_order, opening_examples, socratic_questions)
    dynamic = _dynamic_block(teacher_profile, session, context_results, turn)

    if dna_prompt and dna_prompt.strip():
        persona_base = dna_prompt.strip()
    else:
        persona_base = _legacy_identity(teacher_profile, session)

    return f"{persona_base}\n\n{mandate}\n\n{dynamic}"


# ----------------------------------------------------------------------------
#  Per-turn dynamic block (shared by both persona bases)
# ----------------------------------------------------------------------------
def _dynamic_block(teacher_profile: Any, session: Any, context_results: Any, turn: int) -> str:
    student = getattr(session, "student_profile", None) or {}
    curr_level = getattr(session, "current_effective_level", None)
    level = effective_level(student, curr_level)
    subject = student.get("subject") or getattr(teacher_profile, "subject", None) or "this topic"
    stream = student.get("stream")
    pattern_style = student.get("learning_style", "examples")
    context_text = format_context_chunks(context_results)

    mastery = getattr(session, "concept_mastery", None) or []
    review = [c["concept"] for c in mastery if isinstance(c, dict) and c.get("state") in ("review", "shaky")]
    review_note = (
        f"\nThe student is still shaky on: {', '.join(review[:5])}. Reinforce these when relevant."
        if review
        else ""
    )

    turn_note = ""
    if turn == 0:
        turn_note = "\n[FIRST TURN: be warm and brief; acknowledge the student's question, then start teaching directly.]"
    elif turn >= 10:
        turn_note = f"\n[TURN {turn}: the student is deeply engaged. You may add depth and nuance.]"

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
Ground your answer in the content below. If the question isn't covered, explain from general knowledge while keeping your teacher voice:
{context_text}

=== CITATION & OUTPUT RULES ===
1. Calibrate EVERY sentence to the {LEVEL_LABELS.get(level, level)} level — not too advanced, not too simple.
2. Ground your explanations in the reference knowledge items above. Cite reference content inline with brackets like [1], [2] matching the numbered items above. Citations must ONLY reference valid numbers present in the reference knowledge base.
3. Keep it focused and impactful: {"2-3 short paragraphs" if level in ("class_6_8", "class_9_10") else "3-5 paragraphs"}.
4. The concluding paragraph MUST end with your characteristic Socratic follow-up question (ending with '?') to check or deepen understanding.
5. Strictly adhere to the MANDATORY TEACHER PERSONA EXECUTION rules."""


# ----------------------------------------------------------------------------
#  Legacy persona base (pre-DNA teachers)
# ----------------------------------------------------------------------------
def _legacy_identity(teacher_profile: Any, session: Any) -> str:
    style = _extract_style_data(teacher_profile)
    student = getattr(session, "student_profile", None) or {}
    subject = student.get("subject") or getattr(teacher_profile, "subject", None) or "this topic"
    tone = style.get("tone_type", "friendly")
    sig = style.get("signature_phrases", [])[:6]
    analysis = style.get("raw_analysis", "A knowledgeable, effective educator.")
    analogy = style.get("analogy_density", 0.2)
    humor = style.get("use_of_humor", 0.1)

    phrase_note = (
        f"Use phrases like: {', '.join(repr(p) for p in sig)}." if sig else ""
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
