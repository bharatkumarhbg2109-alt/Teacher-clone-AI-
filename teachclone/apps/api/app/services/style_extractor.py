"""Teacher-style extraction.

Two paths, both 100% local (no paid API):

  * ``extract_style(teacher_profile_id, transcripts)`` — the NEW default. Runs
    the full 7-layer DNA pipeline (Ollama) → DNA report → system prompt → save.
  * ``StyleExtractor.extract(chunks)`` — the LEGACY statistical path, kept for
    backward compatibility. Its LLM classification now uses Ollama too (the
    Anthropic dependency has been removed).
"""
import logging
import re
from collections import Counter

from app.services import dna_extractor

log = logging.getLogger("teachclone.dna")

ANALOGY_PATTERN = re.compile(
    r"\b(like|imagine|think of|similar to|just as|as if|picture this|consider|"
    r"analogous|metaphor|kind of like)\b",
    re.IGNORECASE,
)

# JSON shape for the legacy Ollama classification pass.
_STYLE_SCHEMA_HINT = (
    '{"tone_type": "strict|friendly|socratic|storytelling|energetic|calm", '
    '"tone_confidence": 0.0, '
    '"explanation_pattern": "analogy_first|example_first|theory_first|problem_first|narrative", '
    '"use_of_humor": 0.0, "pacing": "slow|moderate|fast", '
    '"explanation_depth": "surface|moderate|deep", "subjects": [], "raw_analysis": "..."}'
)


# ============================================================================
#  NEW: DNA pipeline entry point (Ollama, offline)
# ============================================================================
async def extract_style(
    teacher_profile_id,
    transcripts: list[str],
    *,
    teacher_name: str = "the teacher",
    model: str | None = None,
    language: str = "",
    db=None,
    save: bool = True,
) -> dict:
    """Run the DNA pipeline over raw transcript strings and (optionally) save.

    Returns the DNA report dict (which is stored as ``style_profile``). When
    ``save`` is true a DB session is required (passed in, or opened here).
    """
    report, system_prompt = await dna_extractor.build_report_and_prompt(
        transcripts, teacher_name, model=model, language=language
    )
    if save:
        if db is not None:
            await dna_extractor.save_dna_outputs(
                db, teacher_profile_id, report, system_prompt, model or "", write_files=True
            )
        else:
            from app.db.session import AsyncSessionLocal

            async with AsyncSessionLocal() as own_db:
                await dna_extractor.save_dna_outputs(
                    own_db, teacher_profile_id, report, system_prompt, model or "", write_files=True
                )
                await own_db.commit()
    return report


# ============================================================================
#  LEGACY: statistical + Ollama classification (backward compatible)
# ============================================================================
class StyleExtractor:
    async def extract(self, chunks) -> dict:
        full_text = " ".join(c.text for c in chunks)
        words = full_text.split()
        if not words:
            return self._default_profile()

        sentences = [s for s in re.split(r"[.!?]+", full_text) if len(s.strip()) > 10]
        avg_sentence_length = len(words) / max(len(sentences), 1)
        analogy_density = len(ANALOGY_PATTERN.findall(full_text)) / max(len(words) / 1000, 0.1)
        use_of_questions = full_text.count("?") / max(len(words) / 1000, 0.1)

        tokens = [w.lower().strip(".,!?;:'\"") for w in words if len(w) > 1]
        ngrams = [" ".join(tokens[i : i + 3]) for i in range(len(tokens) - 2)]
        ngrams += [" ".join(tokens[i : i + 4]) for i in range(len(tokens) - 3)]
        stop_starts = ("the ", "and ", "but ", "so ", "in ", "of ", "to ", "a ", "that ",
                       "this ", "it ", "we ", "you ", "i ")
        counter = Counter(ngrams)
        sig = [
            p for p, _ in counter.most_common(40)
            if not any(p.startswith(s) for s in stop_starts) and counter[p] >= 2
        ][:8]

        word_freq = Counter(w.lower().strip(".,!?;:'\"()[]{}") for w in words if len(w) > 3)
        STOP = {"the", "and", "that", "this", "with", "from", "have", "will", "your",
                "what", "when", "there", "which", "they", "their", "would", "about"}
        vocab = [w for w, _ in word_freq.most_common(60) if w not in STOP][:10]

        avg_wl = sum(len(w) for w in words) / max(len(words), 1)
        vocab_score = round(max(1, min(18, avg_wl * 1.9 + avg_sentence_length * 0.06)), 1)

        llm_part = await self._llm_classify(full_text[:6000])

        return {
            "vocabulary_level": self._to_level(vocab_score),
            "vocabulary_score": vocab_score,
            "avg_sentence_length": round(avg_sentence_length, 1),
            "analogy_density": round(analogy_density, 2),
            "use_of_questions": round(use_of_questions, 2),
            "signature_phrases": sig,
            "vocabulary_samples": vocab,
            **llm_part,
        }

    def _to_level(self, score: float) -> str:
        if score < 6:
            return "elementary"
        if score < 10:
            return "intermediate"
        if score < 14:
            return "advanced"
        return "technical"

    async def _llm_classify(self, text: str) -> dict:
        """Classify tone/pattern/pacing with the local Ollama model (no paid API)."""
        prompt = (
            "Analyze this educational transcript/notes and classify the teacher's style.\n\n"
            f"CONTENT:\n{text}\n\n"
            "Return the tone, explanation pattern, humor level (0-1), pacing, depth, the "
            "subjects covered, and a 2-3 sentence description of what makes this teacher "
            "effective.\n\nReturn ONLY valid JSON in exactly this shape:\n"
            f"{_STYLE_SCHEMA_HINT}"
        )
        try:
            result = await dna_extractor.ollama_json(prompt)
            return {**self._default_llm(), **(result if isinstance(result, dict) else {})}
        except Exception as exc:  # noqa: BLE001
            log.warning("Ollama style classification failed (%s) — using defaults", exc)
            return self._default_llm()

    def _default_profile(self) -> dict:
        return {
            "vocabulary_level": "intermediate",
            "vocabulary_score": 8.0,
            "avg_sentence_length": 15.0,
            "analogy_density": 0.2,
            "use_of_questions": 1.0,
            "signature_phrases": [],
            "vocabulary_samples": [],
            **self._default_llm(),
        }

    def _default_llm(self) -> dict:
        return {
            "tone_type": "friendly",
            "tone_confidence": 0.5,
            "explanation_pattern": "example_first",
            "use_of_humor": 0.1,
            "pacing": "moderate",
            "explanation_depth": "moderate",
            "subjects": [],
            "raw_analysis": "A clear, encouraging educator.",
        }

    def merge_profiles(self, existing: dict | None, new: dict) -> dict:
        if not existing:
            return new
        merged = {**new}
        for k in ["vocabulary_score", "avg_sentence_length", "analogy_density",
                  "use_of_questions", "use_of_humor"]:
            if k in existing and k in new:
                merged[k] = round((existing[k] + new[k]) / 2, 2)
        phrases = list(
            dict.fromkeys(existing.get("signature_phrases", []) + new.get("signature_phrases", []))
        )
        merged["signature_phrases"] = phrases[:10]
        subjects = list(
            dict.fromkeys(existing.get("subjects", []) + new.get("subjects", []))
        )
        merged["subjects"] = subjects[:10]
        return merged


style_extractor = StyleExtractor()
