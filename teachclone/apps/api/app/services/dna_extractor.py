"""Teacher DNA extractor — a fully-local, 100% offline pipeline.

    Video/Audio  ─► download (yt-dlp)  ─► audio (ffmpeg)  ─► transcript (whisper)
                 ─► 7-layer DNA analysis (Ollama)  ─► DNA report  ─► system prompt

NO paid APIs are used anywhere in this module:
  - LLM analysis .......... Ollama (Llama 3.1 / Mistral) at OLLAMA_BASE_URL
  - Speech-to-text ........ faster-whisper (local model)
  - Video download ........ yt-dlp
  - Audio extraction ...... FFmpeg

Downloading a YouTube video (Phase 1) inherently needs internet; the rest of
the pipeline — transcription and all analysis — runs offline. Use the
`extract-from-file` endpoint for a fully air-gapped run.
"""
from __future__ import annotations

import asyncio
import glob
import json
import logging
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

log = logging.getLogger("teachclone.dna")


# ============================================================================
#  Ollama client (local LLM — no paid API)
# ============================================================================
class OllamaError(RuntimeError):
    """Any Ollama failure."""


class OllamaUnavailable(OllamaError):
    """Ollama server is not reachable (is `ollama serve` running?)."""


class OllamaModelError(OllamaError):
    """The requested model is missing / errored (try `ollama pull <model>`)."""


def _generate_url() -> str:
    return settings.OLLAMA_BASE_URL.rstrip("/") + "/api/generate"


def _payload(prompt: str, model: str, num_predict: int, *, think: bool) -> dict:
    p = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": settings.OLLAMA_TEMPERATURE,
            "num_predict": num_predict,
            "num_ctx": settings.OLLAMA_NUM_CTX,
        },
    }
    if think:
        # Disable chain-of-thought so reasoning models (qwen3, deepseek-r1, …)
        # put their answer in `response` instead of an empty string. Harmless
        # for plain instruct models (llama3.1, mistral).
        p["think"] = False
    return p


async def _ollama_call(prompt: str, model: str, *, num_predict: int, timeout: int) -> str:
    async with httpx.AsyncClient(timeout=timeout) as client:
        # First attempt disables thinking; if an older Ollama / a model without
        # thinking support rejects the flag, retry once without it.
        for send_think in (True, False):
            try:
                resp = await client.post(
                    _generate_url(), json=_payload(prompt, model, num_predict, think=send_think)
                )
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                raise OllamaUnavailable(
                    f"Cannot reach Ollama at {settings.OLLAMA_BASE_URL} — is `ollama serve` running?"
                ) from exc
            except httpx.HTTPError as exc:
                raise OllamaError(f"Ollama request failed: {exc}") from exc

            if resp.status_code == 404:
                raise OllamaModelError(
                    f"Ollama model '{model}' not found. Run: ollama pull {model}"
                )
            if resp.status_code >= 400:
                body = resp.text[:300]
                if send_think and "think" in body.lower():
                    continue  # this Ollama/model doesn't accept `think` — retry plain
                raise OllamaError(f"Ollama error {resp.status_code}: {body}")

            data = resp.json()
            text = data.get("response") or ""
            # Reasoning fallback: if the answer landed in `thinking`, salvage it
            # (JSON parsing downstream will still find the object).
            if not text and data.get("thinking"):
                text = data["thinking"]
            return text
    return ""


async def ollama_generate(
    prompt: str,
    model: str | None = None,
    *,
    num_predict: int | None = None,
    timeout: int | None = None,
) -> str:
    """Generate text; falls back to OLLAMA_FALLBACK_MODEL if the primary errors."""
    primary = model or settings.OLLAMA_MODEL
    np = num_predict or settings.OLLAMA_NUM_PREDICT
    to = timeout or settings.OLLAMA_TIMEOUT
    try:
        return await _ollama_call(prompt, primary, num_predict=np, timeout=to)
    except OllamaModelError:
        fallback = settings.OLLAMA_FALLBACK_MODEL
        if fallback and fallback != primary:
            log.warning("Model '%s' unavailable; falling back to '%s'", primary, fallback)
            return await _ollama_call(prompt, fallback, num_predict=np, timeout=to)
        raise


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of a model response (tolerates fences / prose)."""
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


async def ollama_json(prompt: str, model: str | None = None) -> dict:
    """Generate and parse JSON. Retries once with a stricter instruction."""
    raw = await ollama_generate(prompt, model=model)
    try:
        return _extract_json(raw)
    except (json.JSONDecodeError, ValueError):
        strict = prompt + (
            "\n\nIMPORTANT: Respond with ONE valid JSON object ONLY. "
            "No markdown, no code fences, no explanation before or after."
        )
        raw2 = await ollama_generate(strict, model=model)
        return _extract_json(raw2)  # may raise; caller supplies a default


async def ollama_health() -> dict:
    """Check the Ollama server and list installed models."""
    url = settings.OLLAMA_BASE_URL.rstrip("/") + "/api/tags"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            models = [m.get("name") for m in resp.json().get("models", [])]
            return {"reachable": True, "models": models, "base_url": settings.OLLAMA_BASE_URL}
    except Exception as exc:  # noqa: BLE001
        return {"reachable": False, "error": str(exc)[:200], "base_url": settings.OLLAMA_BASE_URL}


# ============================================================================
#  PHASE 1 — video download (yt-dlp)
# ============================================================================
async def download_video(url: str, output_dir: str) -> str:
    """Download a single video as MP4. Returns the file path.

    Raises RuntimeError with a friendly message for private/unavailable videos.
    """
    os.makedirs(output_dir, exist_ok=True)
    before = set(glob.glob(os.path.join(output_dir, "*")))
    out_tmpl = os.path.join(output_dir, "%(id)s.%(ext)s")
    # Prefer a yt-dlp on PATH; else run the installed module with the current
    # interpreter (the console script isn't always on PATH on Windows).
    _ytdlp = shutil.which("yt-dlp")
    cmd = [
        *([_ytdlp] if _ytdlp else [sys.executable, "-m", "yt_dlp"]),
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--no-playlist", "--no-warnings",
        "-o", out_tmpl, url,
    ]
    log.info("[Phase 1] Downloading %s", url)
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    assert proc.stdout is not None
    async for raw in proc.stdout:
        line = raw.decode(errors="ignore").rstrip()
        if "[download]" in line and "%" in line:
            log.info("  %s", line)
    await proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(
            f"yt-dlp failed for {url} (video may be private, region-locked or unavailable)"
        )

    after = set(glob.glob(os.path.join(output_dir, "*")))
    new = sorted(after - before, key=os.path.getmtime, reverse=True)
    mp4s = [p for p in new if p.lower().endswith(".mp4")] or new
    if not mp4s:
        raise RuntimeError(f"yt-dlp produced no file for {url}")
    log.info("[Phase 1] Downloaded -> %s", mp4s[0])
    return mp4s[0]


async def download_videos(urls: list[str], output_dir: str) -> list[str]:
    """Download several URLs; skips (and logs) any that fail. Returns paths."""
    paths: list[str] = []
    for url in urls:
        try:
            paths.append(await download_video(url, output_dir))
        except Exception as exc:  # noqa: BLE001
            log.warning("[Phase 1] Skipping %s: %s", url, exc)
    return paths


# ============================================================================
#  PHASE 2 — audio extraction (FFmpeg)
# ============================================================================
async def extract_audio(video_path: str, output_dir: str, *, cleanup: bool = True) -> str:
    """Extract mono 16 kHz WAV (optimal for Whisper). Deletes the MP4 after."""
    os.makedirs(output_dir, exist_ok=True)
    out_path = os.path.join(output_dir, Path(video_path).stem + ".wav")
    cmd = [
        "ffmpeg", "-i", video_path, "-vn",
        "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
        "-y", out_path, "-loglevel", "error",
    ]
    log.info("[Phase 2] Extracting audio -> %s", out_path)
    proc = await asyncio.create_subprocess_exec(*cmd, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr.decode(errors='ignore')[:400]}")
    if cleanup:
        try:
            os.remove(video_path)
        except OSError:
            pass
    return out_path


# ============================================================================
#  PHASE 3 — speech-to-text (faster-whisper, offline)
# ============================================================================
_whisper_models: dict[str, object] = {}


def _get_whisper(model_name: str):
    if model_name not in _whisper_models:
        try:
            import av
            _orig_av_open = av.open

            def _safe_av_open(*args, **kwargs):
                kwargs.pop("metadata_errors", None)
                return _orig_av_open(*args, **kwargs)

            av.open = _safe_av_open
        except Exception:
            pass

        from faster_whisper import WhisperModel  # lazy: heavy import

        log.info("[Phase 3] Loading faster-whisper model '%s'…", model_name)
        _whisper_models[model_name] = WhisperModel(
            model_name,
            device=settings.WHISPER_DEVICE,
            compute_type=settings.WHISPER_COMPUTE_TYPE,
        )
    return _whisper_models[model_name]


def transcribe_audio(audio_path: str, model: str | None = None) -> dict:
    """Transcribe a WAV/audio file (auto language: Hindi / English / Hinglish).

    Blocking (CPU/GPU bound) — call via ``asyncio.to_thread`` from async code.
    """
    model_name = model or settings.DNA_WHISPER_MODEL
    whisper = _get_whisper(model_name)
    log.info("[Phase 3] Transcribing %s (model=%s)", audio_path, model_name)
    segments, info = whisper.transcribe(
        audio_path,
        beam_size=5,
        language=None,  # auto-detect
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )
    seg_list: list[dict] = []
    parts: list[str] = []
    for s in segments:  # generator — streams, so any length works
        txt = s.text.strip()
        if not txt:
            continue
        seg_list.append({"start": round(s.start, 2), "end": round(s.end, 2), "text": txt})
        parts.append(txt)
    full_text = " ".join(parts).strip()
    log.info("[Phase 3] Done: %d segments, lang=%s", len(seg_list), info.language)
    return {
        "full_text": full_text,
        "segments": seg_list,
        "language": info.language,
        "duration_seconds": int(getattr(info, "duration", 0) or 0),
    }


# ============================================================================
#  PHASE 4 — 7-layer deep DNA analysis (Ollama)
# ============================================================================
# Each layer: (human name, report field, prompt template, default factory).
# Templates use a literal {transcript} placeholder inserted via str.replace
# (NOT .format — the JSON examples contain literal braces).

_L1 = """Analyze this teaching transcript carefully.
Extract VOCABULARY DNA:

1. Top 30 most frequently used words/phrases (excluding common words)
2. Technical terms the teacher uses and HOW they introduce them
3. Hindi words used: list them
4. English words used: list them
5. Hindi-to-English ratio (e.g., 70% Hindi, 30% English)
6. Complexity level: Simple/Medium/Advanced
7. Words teacher NEVER uses or avoids

Transcript:
{transcript}

Return ONLY valid JSON, no explanation:
{"top_phrases": ["phrase1", "phrase2"], "technical_terms": {"term": "how_introduced"}, "hindi_words": [], "english_words": [], "hindi_english_ratio": "70:30", "complexity": "simple/medium/advanced", "avoided_words": []}"""

_L2 = """Analyze this teaching transcript.
Extract EXPLANATION DNA — how does this teacher explain concepts?

1. What comes FIRST when explaining? (definition/analogy/example/question)
2. What comes SECOND?
3. What comes THIRD?
4. Does teacher repeat key points? How many times?
5. How long is a typical explanation? (short/medium/long)
6. Does teacher build from simple to complex or complex to simple?
7. Extract 5 real examples of how teacher STARTS an explanation

Transcript:
{transcript}

Return ONLY valid JSON:
{"explanation_order": ["first", "second", "third"], "repeats_key_points": true, "repeat_count": 2, "explanation_length": "medium", "direction": "simple_to_complex", "opening_examples": ["exact quote 1", "exact quote 2"]}"""

_L3 = """Analyze this teaching transcript.
Extract EXAMPLE DNA — what kind of examples does this teacher use?

1. Where do examples come from? (daily life/science/sports/food/technology/Indian context)
2. Top 3 example sources with actual examples from transcript
3. How long are examples? (one-liner/short story/detailed)
4. Does teacher use same examples repeatedly?
5. Extract 10 actual examples teacher used (exact words)
6. Does teacher relate to students' personal life?

Transcript:
{transcript}

Return ONLY valid JSON:
{"example_sources": ["daily_life", "indian_context"], "top_sources_with_examples": {"source1": "actual example"}, "example_length": "short_story", "reuses_examples": true, "actual_examples": ["exact quote 1"], "relates_to_student_life": true}"""

_L4 = """Analyze this teaching transcript.
Extract QUESTION DNA — how does this teacher ask questions?

1. Question types used: (direct/hint-based/fill-blank/socratic/comparison/reverse)
2. Most common question type
3. Does teacher go easy to hard or random?
4. How long after explanation does teacher ask question?
5. Does teacher give hints when student is stuck?
6. Extract 10 actual questions teacher asked (exact words)
7. How does teacher respond to wrong answers in questions?

Transcript:
{transcript}

Return ONLY valid JSON:
{"question_types": ["socratic", "hint_based"], "dominant_type": "socratic", "difficulty_pattern": "easy_to_hard", "hint_giver": true, "actual_questions": ["exact question 1"], "wrong_answer_response": "description of pattern"}"""

_L5 = """Analyze this teaching transcript.
Extract CORRECTION DNA — how does this teacher handle wrong answers?

1. Is correction style: gentle/direct/encouraging/strict?
2. Exact phrases used when student is wrong (extract real quotes)
3. Does teacher explain again or just say wrong?
4. Does teacher give hints after wrong answer?
5. Does teacher praise effort even when wrong?
6. Extract 5 real correction moments from transcript

Transcript:
{transcript}

Return ONLY valid JSON:
{"correction_style": "gentle/direct/encouraging/strict", "correction_phrases": ["exact phrase 1"], "re_explains": true, "gives_hints": true, "praises_effort": true, "real_correction_examples": ["full correction moment 1"]}"""

_L6 = """Analyze this teaching transcript.
Extract TRANSITION DNA — how does teacher move between topics?

1. Exact phrases used to transition (extract real quotes)
2. Does teacher summarize before moving on?
3. Does teacher connect new topic to previous one?
4. How does teacher signal "this is important"?
5. How does teacher signal "moving on now"?
6. Extract 8 actual transition phrases

Transcript:
{transcript}

Return ONLY valid JSON:
{"summarizes_before_moving": true, "connects_topics": true, "importance_signals": ["yeh bahut important hai"], "transition_phrases": ["ab hum dekhenge"]}"""

_L7 = """Analyze this teaching transcript.
Extract EMOTION DNA — when and how does teacher show emotions?

1. When does teacher get EXCITED? (what topics/moments)
2. When does teacher get SERIOUS? (what topics/moments)
3. When does teacher show HUMOR? Extract actual jokes/funny moments
4. How does teacher MOTIVATE students? Extract real phrases
5. Teacher's overall energy: high/medium/calm
6. Does teacher share personal stories/experiences?

Transcript:
{transcript}

Return ONLY valid JSON:
{"gets_excited_when": ["moment"], "gets_serious_when": ["moment"], "humor_examples": ["funny quote"], "motivation_phrases": ["phrase"], "overall_energy": "high/medium/calm", "shares_personal_stories": true}"""


def _default_vocabulary() -> dict:
    return {"top_phrases": [], "technical_terms": {}, "hindi_words": [], "english_words": [],
            "hindi_english_ratio": "", "complexity": "medium", "avoided_words": []}


def _default_explanation() -> dict:
    return {"explanation_order": [], "repeats_key_points": False, "repeat_count": 0,
            "explanation_length": "medium", "direction": "simple_to_complex", "opening_examples": []}


def _default_example() -> dict:
    return {"example_sources": [], "top_sources_with_examples": {}, "example_length": "short",
            "reuses_examples": False, "actual_examples": [], "relates_to_student_life": False}


def _default_question() -> dict:
    return {"question_types": [], "dominant_type": "", "difficulty_pattern": "", "hint_giver": False,
            "actual_questions": [], "wrong_answer_response": ""}


def _default_correction() -> dict:
    return {"correction_style": "encouraging", "correction_phrases": [], "re_explains": False,
            "gives_hints": False, "praises_effort": False, "real_correction_examples": []}


def _default_transition() -> dict:
    return {"summarizes_before_moving": False, "connects_topics": False,
            "importance_signals": [], "transition_phrases": []}


def _default_emotion() -> dict:
    return {"gets_excited_when": [], "gets_serious_when": [], "humor_examples": [],
            "motivation_phrases": [], "overall_energy": "medium", "shares_personal_stories": False}


_LAYERS = [
    ("VOCABULARY", "vocabulary_dna", _L1, _default_vocabulary),
    ("EXPLANATION", "explanation_dna", _L2, _default_explanation),
    ("EXAMPLE", "example_dna", _L3, _default_example),
    ("QUESTION", "question_dna", _L4, _default_question),
    ("CORRECTION", "correction_dna", _L5, _default_correction),
    ("TRANSITION", "transition_dna", _L6, _default_transition),
    ("EMOTION", "emotion_dna", _L7, _default_emotion),
]


async def analyze_dna(transcripts: list[str], model: str | None = None, on_layer=None) -> dict:
    """Run all 7 DNA layers over the transcript(s) using Ollama.

    A single layer failing (bad JSON, etc.) falls back to that layer's empty
    default so the pipeline always returns a complete 7-layer structure.
    Raises OllamaUnavailable only if Ollama itself is unreachable.

    ``on_layer`` is an optional progress hook called as
    ``on_layer(field, index, done)`` — ``done=False`` when a layer starts and
    ``done=True`` when it finishes — so callers (the admin dashboard job runner)
    can report which layer is currently being analyzed.
    """
    combined = "\n\n".join(t for t in transcripts if t and t.strip())
    transcript = combined[: settings.DNA_TRANSCRIPT_CHAR_LIMIT]
    if not transcript.strip():
        raise OllamaError("No transcript text to analyze")

    layers: dict = {}
    for i, (name, field, template, default) in enumerate(_LAYERS, 1):
        prompt = template.replace("{transcript}", transcript)
        log.info("[Phase 4] Layer %d/7: %s DNA", i, name)
        if on_layer:
            try:
                on_layer(field, i, False)
            except Exception:  # noqa: BLE001 — progress must never break the run
                pass
        try:
            result = await ollama_json(prompt, model=model)
            if not isinstance(result, dict):
                raise ValueError("layer did not return an object")
            layers[field] = {**default(), **result}
        except OllamaUnavailable:
            raise  # server down — abort the whole run
        except Exception as exc:  # noqa: BLE001
            log.warning("[Phase 4] Layer %s failed (%s) — using default", name, exc)
            layers[field] = default()
        if on_layer:
            try:
                on_layer(field, i, True)
            except Exception:  # noqa: BLE001
                pass
    return layers


# ============================================================================
#  PHASE 5 — DNA report generation
# ============================================================================
def _collect_signature_phrases(layers: dict) -> list[str]:
    """Union of the most identity-defining phrases across layers (≤20)."""
    voc = layers.get("vocabulary_dna", {})
    tr = layers.get("transition_dna", {})
    corr = layers.get("correction_dna", {})
    emo = layers.get("emotion_dna", {})
    pool: list[str] = []
    pool += _as_str_list(voc.get("top_phrases"))[:12]
    pool += _as_str_list(tr.get("transition_phrases"))
    pool += _as_str_list(tr.get("importance_signals"))
    pool += _as_str_list(corr.get("correction_phrases"))
    pool += _as_str_list(emo.get("motivation_phrases"))
    seen: dict[str, None] = {}
    for p in pool:
        key = p.strip()
        if key and key not in seen:
            seen[key] = None
    return list(seen.keys())[:20]


def generate_dna_report(
    layers: dict,
    teacher_name: str,
    *,
    analyzed_videos: int,
    total_words: int,
    language: str = "",
    model: str = "",
) -> dict:
    """Combine the 7 layers into a Master DNA report."""
    return {
        "teacher_name": teacher_name,
        "analyzed_videos": analyzed_videos,
        "total_transcript_words": total_words,
        "language": language,
        "model_used": model,
        "extraction_date": datetime.now(timezone.utc).date().isoformat(),
        "vocabulary_dna": layers.get("vocabulary_dna", _default_vocabulary()),
        "explanation_dna": layers.get("explanation_dna", _default_explanation()),
        "example_dna": layers.get("example_dna", _default_example()),
        "question_dna": layers.get("question_dna", _default_question()),
        "correction_dna": layers.get("correction_dna", _default_correction()),
        "transition_dna": layers.get("transition_dna", _default_transition()),
        "emotion_dna": layers.get("emotion_dna", _default_emotion()),
        "signature_phrases": _collect_signature_phrases(layers),
        "teaching_fingerprint": "",  # filled by _generate_fingerprint
    }


async def _generate_fingerprint(report: dict, model: str | None = None) -> str:
    """One-paragraph identity summary (Ollama, with a deterministic fallback)."""
    prompt = (
        "In ONE vivid paragraph (3-5 sentences), summarise what makes this teacher's "
        "style unique, based on this DNA. Write plain prose only, no headings.\n\n"
        + json.dumps(_trim_report_for_prompt(report), ensure_ascii=False)[:4000]
    )
    try:
        text = (await ollama_generate(prompt, model=model, num_predict=400)).strip()
        if len(text) >= 60:
            return text
    except Exception as exc:  # noqa: BLE001
        log.warning("Fingerprint generation failed (%s) — using fallback", exc)
    emo = report.get("emotion_dna", {})
    voc = report.get("vocabulary_dna", {})
    return (
        f"{report.get('teacher_name', 'This teacher')} teaches with "
        f"{emo.get('overall_energy', 'balanced')} energy and a "
        f"{voc.get('complexity', 'medium')}-complexity vocabulary, "
        f"favouring {report.get('example_dna', {}).get('example_length', 'short')} examples and a "
        f"{report.get('correction_dna', {}).get('correction_style', 'supportive')} correction style."
    )


# ============================================================================
#  PHASE 6 — ultra-detailed system prompt generation
# ============================================================================
_PROMPT_ENGINEER = """You are a prompt engineer.
Based on this Teacher DNA Report, write an ultra-detailed system prompt
that will make an AI model behave EXACTLY like this teacher.

The system prompt must include:
1. Teacher's exact identity and subject
2. All signature phrases (with instructions to use them naturally)
3. Exact explanation pattern (order: first do X, then Y, then Z)
4. Example style (where to get examples from, how long)
5. Question style (when to ask, what type, difficulty progression)
6. Correction style (exact phrases to use, how to handle wrong answers)
7. Transition style (how to move between topics)
8. Emotion rules (when to be excited, serious, humorous)
9. Language rules (exact Hindi:English ratio)
10. What NOT to do (behaviors to avoid)

DNA Report:
{dna_report_json}

Write the system prompt in second person ("You are...", "You always...", "When student is wrong, you say...").
Make it extremely specific — not generic instructions.
Include actual phrases and examples from the DNA.
Minimum 500 words."""


async def generate_system_prompt(dna_report: dict, model: str | None = None) -> str:
    """Turn the DNA report into an ultra-detailed persona system prompt."""
    prompt = _PROMPT_ENGINEER.replace(
        "{dna_report_json}", json.dumps(dna_report, ensure_ascii=False, indent=2)
    )
    log.info("[Phase 6] Generating system prompt via Ollama")
    try:
        text = (await ollama_generate(prompt, model=model, num_predict=3000)).strip()
        if len(text) >= 200:
            return text
        log.warning("[Phase 6] System prompt too short — using deterministic fallback")
    except Exception as exc:  # noqa: BLE001
        log.warning("[Phase 6] Ollama prompt generation failed (%s) — using fallback", exc)
    return _fallback_system_prompt(dna_report)


def _fallback_system_prompt(r: dict) -> str:
    """Deterministic, detailed system prompt built directly from the DNA.

    Used when Ollama is unavailable for Phase 6 so the pipeline always yields a
    usable prompt (keeps the run fully offline-safe)."""
    name = r.get("teacher_name", "the teacher")
    voc = r.get("vocabulary_dna", {})
    exp = r.get("explanation_dna", {})
    exm = r.get("example_dna", {})
    q = r.get("question_dna", {})
    corr = r.get("correction_dna", {})
    tr = r.get("transition_dna", {})
    emo = r.get("emotion_dna", {})
    sig = _as_str_list(r.get("signature_phrases"))
    order = _as_str_list(exp.get("explanation_order")) or ["example", "explanation", "check"]
    corr_phrases = _as_str_list(corr.get("correction_phrases"))[:5]
    transitions = _as_str_list(tr.get("transition_phrases"))[:6]
    ratio = voc.get("hindi_english_ratio") or "match the student"

    lines = [
        f"You are an AI teacher that speaks and teaches EXACTLY like {name}.",
        r.get("teaching_fingerprint", ""),
        "",
        "IDENTITY & LANGUAGE:",
        f"- Vocabulary complexity: {voc.get('complexity', 'medium')}.",
        f"- Hindi:English mix — keep it around {ratio}. Never drift fully to one language if the teacher mixes.",
        f"- Overall energy: {emo.get('overall_energy', 'medium')}.",
    ]
    if sig:
        lines.append("- Use these signature phrases naturally (do not overuse): "
                     + "; ".join(repr(p) for p in sig[:12]) + ".")
    lines += [
        "",
        "HOW YOU EXPLAIN (follow this order every time):",
        "  " + " -> ".join(order),
        f"- Typical explanation length: {exp.get('explanation_length', 'medium')}.",
        f"- Build direction: {exp.get('direction', 'simple_to_complex')}.",
    ]
    if exp.get("repeats_key_points"):
        lines.append(f"- Repeat key points about {exp.get('repeat_count', 2)} time(s) for emphasis.")
    lines += [
        "",
        "EXAMPLES:",
        f"- Draw examples from: {', '.join(_as_str_list(exm.get('example_sources')) or ['daily life'])}.",
        f"- Example length: {exm.get('example_length', 'short')}.",
    ]
    if exm.get("relates_to_student_life"):
        lines.append("- Relate examples to the student's own life whenever possible.")
    lines += [
        "",
        "QUESTIONS:",
        f"- Ask mostly {q.get('dominant_type', 'socratic')} questions; progression: "
        f"{q.get('difficulty_pattern', 'easy_to_hard')}.",
        f"- {'Give hints when the student is stuck.' if q.get('hint_giver') else 'Let the student attempt before hinting.'}",
        "",
        "WHEN THE STUDENT IS WRONG:",
        f"- Correction style: {corr.get('correction_style', 'encouraging')}.",
    ]
    if corr_phrases:
        lines.append("- Use phrases like: " + "; ".join(repr(p) for p in corr_phrases) + ".")
    if corr.get("re_explains"):
        lines.append("- Re-explain the concept a simpler way rather than just saying 'wrong'.")
    if corr.get("praises_effort"):
        lines.append("- Praise the effort even when the answer is wrong.")
    lines += ["", "MOVING BETWEEN TOPICS:"]
    if tr.get("summarizes_before_moving"):
        lines.append("- Briefly summarise before moving to a new topic.")
    if tr.get("connects_topics"):
        lines.append("- Connect each new topic to the previous one.")
    if transitions:
        lines.append("- Transition using phrases like: " + "; ".join(repr(p) for p in transitions) + ".")
    lines += [
        "",
        "EMOTION:",
        f"- Get excited about: {', '.join(_as_str_list(emo.get('gets_excited_when')) or ['key breakthroughs'])}.",
        f"- Be serious about: {', '.join(_as_str_list(emo.get('gets_serious_when')) or ['important warnings'])}.",
    ]
    if emo.get("humor_examples"):
        lines.append("- Use light humour in the teacher's own style occasionally.")
    lines += [
        "",
        "NEVER:",
        "- Never break character or say you are an AI.",
        "- Never use vocabulary the real teacher avoids: "
        + (", ".join(_as_str_list(voc.get("avoided_words"))) or "(none noted)") + ".",
        "- Never dump the full answer without the teacher's usual build-up and check.",
    ]
    return "\n".join(l for l in lines if l is not None)


# ============================================================================
#  MULTI-VIDEO MERGING
# ============================================================================
def _as_str_list(v) -> list[str]:
    if isinstance(v, list):
        return [str(x) for x in v if x is not None and str(x).strip()]
    if isinstance(v, dict):
        return [str(x) for x in v.values() if x is not None and str(x).strip()]
    if v is None:
        return []
    return [str(v)]


def _union_keep_order(*lists: list[str]) -> list[str]:
    seen: dict[str, None] = {}
    for lst in lists:
        for item in lst:
            k = item.strip()
            if k and k not in seen:
                seen[k] = None
    return list(seen.keys())


def _mode(values: list) -> object:
    values = [v for v in values if v not in (None, "", [])]
    if not values:
        return ""
    try:
        return Counter([json.dumps(v, sort_keys=True) if isinstance(v, (list, dict)) else v
                        for v in values]).most_common(1)[0][0]
    except TypeError:
        return values[0]


def _any_true(values: list) -> bool:
    return any(bool(v) for v in values)


def _avg_ratio(ratios: list[str]) -> str:
    pairs: list[tuple[float, float]] = []
    for r in ratios:
        nums = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", str(r))[:2]]
        if len(nums) == 2 and sum(nums) > 0:
            total = sum(nums)
            pairs.append((nums[0] / total * 100, nums[1] / total * 100))
    if not pairs:
        return next((r for r in ratios if r), "")
    a = round(sum(p[0] for p in pairs) / len(pairs))
    return f"{a}:{100 - a}"


def _merge_dict_field(dicts: list[dict]) -> dict:
    out: dict = {}
    for d in dicts:
        if isinstance(d, dict):
            out.update({str(k): v for k, v in d.items()})
    return out


def merge_dna_reports(reports: list[dict]) -> dict:
    """Merge per-video DNA reports into one stronger, more accurate report."""
    if len(reports) == 1:
        return reports[0]

    def layer(name: str) -> list[dict]:
        return [r.get(name, {}) or {} for r in reports]

    voc, exp, exm = layer("vocabulary_dna"), layer("explanation_dna"), layer("example_dna")
    q, corr, tr, emo = (layer("question_dna"), layer("correction_dna"),
                        layer("transition_dna"), layer("emotion_dna"))

    # signature phrases: union with frequency, ordered by how many videos used them
    freq: Counter = Counter()
    for r in reports:
        for p in _as_str_list(r.get("signature_phrases")):
            freq[p.strip()] += 1
    signature = [p for p, _ in freq.most_common(20) if p]

    merged = {
        "teacher_name": reports[0].get("teacher_name", ""),
        "analyzed_videos": sum(r.get("analyzed_videos", 1) for r in reports),
        "total_transcript_words": sum(r.get("total_transcript_words", 0) for r in reports),
        "language": _mode([r.get("language") for r in reports]) or "",
        "model_used": reports[0].get("model_used", ""),
        "extraction_date": datetime.now(timezone.utc).date().isoformat(),
        "vocabulary_dna": {
            "top_phrases": _union_keep_order(*[_as_str_list(d.get("top_phrases")) for d in voc])[:30],
            "technical_terms": _merge_dict_field([d.get("technical_terms", {}) for d in voc]),
            "hindi_words": _union_keep_order(*[_as_str_list(d.get("hindi_words")) for d in voc]),
            "english_words": _union_keep_order(*[_as_str_list(d.get("english_words")) for d in voc]),
            "hindi_english_ratio": _avg_ratio([d.get("hindi_english_ratio", "") for d in voc]),
            "complexity": _mode([d.get("complexity") for d in voc]) or "medium",
            "avoided_words": _union_keep_order(*[_as_str_list(d.get("avoided_words")) for d in voc]),
        },
        "explanation_dna": {
            "explanation_order": max((_as_str_list(d.get("explanation_order")) for d in exp),
                                     key=len, default=[]),
            "repeats_key_points": _any_true([d.get("repeats_key_points") for d in exp]),
            "repeat_count": round(sum(d.get("repeat_count", 0) or 0 for d in exp) / max(len(exp), 1)),
            "explanation_length": _mode([d.get("explanation_length") for d in exp]) or "medium",
            "direction": _mode([d.get("direction") for d in exp]) or "simple_to_complex",
            "opening_examples": _union_keep_order(*[_as_str_list(d.get("opening_examples")) for d in exp]),
        },
        "example_dna": {
            "example_sources": _union_keep_order(*[_as_str_list(d.get("example_sources")) for d in exm]),
            "top_sources_with_examples": _merge_dict_field(
                [d.get("top_sources_with_examples", {}) for d in exm]),
            "example_length": _mode([d.get("example_length") for d in exm]) or "short",
            "reuses_examples": _any_true([d.get("reuses_examples") for d in exm]),
            "actual_examples": _union_keep_order(*[_as_str_list(d.get("actual_examples")) for d in exm]),
            "relates_to_student_life": _any_true([d.get("relates_to_student_life") for d in exm]),
        },
        "question_dna": {
            "question_types": _union_keep_order(*[_as_str_list(d.get("question_types")) for d in q]),
            "dominant_type": _mode([d.get("dominant_type") for d in q]) or "",
            "difficulty_pattern": _mode([d.get("difficulty_pattern") for d in q]) or "",
            "hint_giver": _any_true([d.get("hint_giver") for d in q]),
            "actual_questions": _union_keep_order(*[_as_str_list(d.get("actual_questions")) for d in q]),
            "wrong_answer_response": next(
                (d.get("wrong_answer_response") for d in q if d.get("wrong_answer_response")), ""),
        },
        "correction_dna": {
            "correction_style": _mode([d.get("correction_style") for d in corr]) or "encouraging",
            "correction_phrases": _union_keep_order(
                *[_as_str_list(d.get("correction_phrases")) for d in corr]),
            "re_explains": _any_true([d.get("re_explains") for d in corr]),
            "gives_hints": _any_true([d.get("gives_hints") for d in corr]),
            "praises_effort": _any_true([d.get("praises_effort") for d in corr]),
            "real_correction_examples": _union_keep_order(
                *[_as_str_list(d.get("real_correction_examples")) for d in corr]),
        },
        "transition_dna": {
            "summarizes_before_moving": _any_true([d.get("summarizes_before_moving") for d in tr]),
            "connects_topics": _any_true([d.get("connects_topics") for d in tr]),
            "importance_signals": _union_keep_order(*[_as_str_list(d.get("importance_signals")) for d in tr]),
            "transition_phrases": _union_keep_order(*[_as_str_list(d.get("transition_phrases")) for d in tr]),
        },
        "emotion_dna": {
            "gets_excited_when": _union_keep_order(*[_as_str_list(d.get("gets_excited_when")) for d in emo]),
            "gets_serious_when": _union_keep_order(*[_as_str_list(d.get("gets_serious_when")) for d in emo]),
            "humor_examples": _union_keep_order(*[_as_str_list(d.get("humor_examples")) for d in emo]),
            "motivation_phrases": _union_keep_order(*[_as_str_list(d.get("motivation_phrases")) for d in emo]),
            "overall_energy": _mode([d.get("overall_energy") for d in emo]) or "medium",
            "shares_personal_stories": _any_true([d.get("shares_personal_stories") for d in emo]),
        },
        "signature_phrases": signature,
        "teaching_fingerprint": "",
    }
    return merged


def _trim_report_for_prompt(report: dict) -> dict:
    """A compact copy of the report for the fingerprint prompt."""
    keep = ("teacher_name", "vocabulary_dna", "explanation_dna", "example_dna",
            "question_dna", "correction_dna", "transition_dna", "emotion_dna",
            "signature_phrases")
    return {k: report.get(k) for k in keep}


# ============================================================================
#  HIGH-LEVEL ORCHESTRATION (Phases 4-6) + persistence
# ============================================================================
async def build_report_and_prompt(
    transcripts: list[str],
    teacher_name: str,
    *,
    model: str | None = None,
    language: str = "",
) -> tuple[dict, str]:
    """Phases 4-6: per-video DNA -> merge -> fingerprint -> system prompt."""
    reports: list[dict] = []
    for t in transcripts:
        if not t or not t.strip():
            continue
        layers = await analyze_dna([t], model=model)
        reports.append(
            generate_dna_report(
                layers, teacher_name,
                analyzed_videos=1, total_words=len(t.split()),
                language=language, model=(model or settings.OLLAMA_MODEL),
            )
        )
    if not reports:
        raise OllamaError("No non-empty transcripts to analyze")

    final = merge_dna_reports(reports)
    final["teaching_fingerprint"] = await _generate_fingerprint(final, model=model)
    system_prompt = await generate_system_prompt(final, model=model)
    return final, system_prompt


def _legacy_compat(report: dict) -> dict:
    """Map DNA fields onto the legacy style_profile keys the old prompt_builder
    and the web profile page read, so DNA teachers degrade gracefully even on
    the legacy path."""
    voc = report.get("vocabulary_dna", {})
    emo = report.get("emotion_dna", {})
    energy = (emo.get("overall_energy") or "medium").lower()
    tone = {"high": "energetic", "calm": "calm", "medium": "friendly"}.get(energy, "friendly")
    return {
        "tone_type": tone,
        "vocabulary_level": voc.get("complexity", "intermediate"),
        "explanation_pattern": "example_first",
        "pacing": {"high": "fast", "calm": "slow"}.get(energy, "moderate"),
        "analogy_density": 0.3,
        "use_of_humor": 0.4 if emo.get("humor_examples") else 0.1,
        "signature_phrases": report.get("signature_phrases", []),
        "raw_analysis": report.get("teaching_fingerprint", ""),
    }


def _write_backup_files(teacher_profile_id: str, report: dict, system_prompt: str) -> None:
    try:
        os.makedirs(settings.DNA_REPORTS_DIR, exist_ok=True)
        os.makedirs(settings.SYSTEM_PROMPTS_DIR, exist_ok=True)
        with open(os.path.join(settings.DNA_REPORTS_DIR, f"{teacher_profile_id}_dna.json"),
                  "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        with open(os.path.join(settings.SYSTEM_PROMPTS_DIR, f"{teacher_profile_id}_prompt.txt"),
                  "w", encoding="utf-8") as f:
            f.write(system_prompt)
    except OSError as exc:
        log.warning("Could not write DNA backup files: %s", exc)


async def save_dna_outputs(
    db: AsyncSession,
    teacher_profile_id,
    report: dict,
    system_prompt: str,
    model: str,
    *,
    write_files: bool = True,
) -> None:
    """Persist the DNA report + system prompt to the DB (and backup files).

    Operates within the caller's transaction (flush only). The caller commits.
    """
    from app.models.dna_report import DnaReport
    from app.models.teacher_profile import TeacherProfile

    teacher = (
        await db.execute(select(TeacherProfile).where(TeacherProfile.id == teacher_profile_id))
    ).scalar_one()

    teacher.style_profile = {**report, **_legacy_compat(report)}
    teacher.system_prompt = system_prompt

    db.add(
        DnaReport(
            teacher_profile_id=teacher.id,
            teacher_name=report.get("teacher_name", "") or teacher.name,
            analyzed_videos=report.get("analyzed_videos", 0),
            total_words=report.get("total_transcript_words", 0),
            language=report.get("language") or None,
            model_used=model,
            report=report,
            system_prompt=system_prompt,
        )
    )
    await db.flush()
    if write_files:
        _write_backup_files(str(teacher_profile_id), report, system_prompt)
    log.info("[Phase 5] DNA report saved for teacher %s", teacher_profile_id)


# ============================================================================
#  Transcript persistence + offline embedding (so DNA teachers can also teach)
# ============================================================================
_CHUNK_WORDS = 300
_CHUNK_OVERLAP = 30


def chunk_transcript(text: str) -> list[str]:
    words = text.split()
    chunks: list[str] = []
    i = 0
    while i < len(words):
        window = words[i : i + _CHUNK_WORDS]
        if not window:
            break
        chunks.append(" ".join(window))
        if i + _CHUNK_WORDS >= len(words):
            break
        i += _CHUNK_WORDS - _CHUNK_OVERLAP
    return chunks


async def persist_transcripts(
    db: AsyncSession,
    teacher_profile_id,
    uploaded_by,
    items: list[dict],
) -> list[str]:
    """Store each transcript as a MediaSource + TranscriptChunk rows (so the
    teacher gains knowledge and `regenerate` can re-run on them). Returns the
    media_source ids. Embedding is a separate step (``embed_source``) run AFTER
    the caller commits — this keeps a single SQLite writer at a time."""
    from app.models.media_source import MediaSource
    from app.models.transcript_chunk import TranscriptChunk

    source_ids: list[str] = []
    for it in items:
        text = (it.get("text") or "").strip()
        if not text:
            continue
        src = MediaSource(
            teacher_profile_id=teacher_profile_id,
            uploaded_by=uploaded_by,
            source_type=it.get("source_type", "dna_upload"),
            original_url=it.get("original_url"),
            file_name=it.get("file_name"),
            content_type=it.get("content_type"),
            duration_seconds=it.get("duration_seconds"),
            status="completed",
        )
        db.add(src)
        await db.flush()

        chunk_objs = [
            TranscriptChunk(
                media_source_id=src.id,
                chunk_index=i,
                text=chunk,
                content_type="audio",
                token_count=len(chunk.split()),
            )
            for i, chunk in enumerate(chunk_transcript(text))
        ]
        db.add_all(chunk_objs)
        src.transcript_chunks = len(chunk_objs)
        await db.flush()
        source_ids.append(str(src.id))
    return source_ids


async def embed_source(media_source_id: str) -> None:
    """Embed one source's chunks into the vector store, offline. Self-contained
    (own session), and safe to call AFTER the transcripts are committed. Mirrors
    the ordering of the normal ``embed_and_store`` task (write vectors, then set
    embedding_id) so SQLite only ever has one writer at a time. Best-effort."""
    from app.db.session import AsyncSessionLocal
    from app.models.media_source import MediaSource
    from app.models.transcript_chunk import TranscriptChunk
    from app.services.embedder import embedder
    from app.services.vector_store import ChunkPoint, vector_store

    async with AsyncSessionLocal() as db:
        source = (
            await db.execute(select(MediaSource).where(MediaSource.id == media_source_id))
        ).scalar_one_or_none()
        if source is None:
            return
        profile_id = str(source.teacher_profile_id)
        chunks = (
            (await db.execute(
                select(TranscriptChunk)
                .where(
                    TranscriptChunk.media_source_id == media_source_id,
                    TranscriptChunk.embedding_id.is_(None),
                )
                .order_by(TranscriptChunk.chunk_index)
            )).scalars().all()
        )
        if not chunks:
            return
        dense = await embedder.embed_texts([c.text for c in chunks])  # no DB write yet
        await vector_store.ensure_collection()
        points = [
            ChunkPoint(
                id=str(c.id),
                dense_vector=v,
                sparse_vector=embedder.compute_sparse_vector(c.text),
                payload={
                    "text": c.text,
                    "media_source_id": media_source_id,
                    "teacher_profile_id": profile_id,
                    "start_time": c.start_time,
                    "end_time": c.end_time,
                    "page": c.page,
                    "chunk_index": c.chunk_index,
                    "content_type": c.content_type,
                },
            )
            for c, v in zip(chunks, dense)
        ]
        await vector_store.upsert_chunks(points)  # writes vectors (separate store), commits
        for c in chunks:
            c.embedding_id = str(c.id)
        await db.commit()  # then mark embedded
