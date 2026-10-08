"""Text-to-speech for audio output. Provider: openai | elevenlabs | piper.

Strips markdown/citations before synthesis and returns audio bytes along with
the correct file extension and MIME type. Results are cached to object storage
by the voice router so replays are instant.
"""
import re
import subprocess
import tempfile
from typing import NamedTuple

import httpx

from app.config import settings

import logging
import shutil

log = logging.getLogger("teachclone.tts")

_MD = re.compile(r"(\*\*|*|`|#+\s|\[\d+\]|\[.*?\]\(.*?\))")


class TtsResult(NamedTuple):
    audio: bytes
    ext: str      # "mp3" or "wav"
    mime: str     # "audio/mpeg" or "audio/wav"


def _strip_markdown(text: str) -> str:
    text = _MD.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


async def synthesize(text: str, voice: str | None = None) -> TtsResult | None:
    """Synthesize text to speech. Gracefully degrades to None if unconfigured."""
    voice = voice or settings.DEFAULT_TTS_VOICE
    clean = _strip_markdown(text)
    provider = (settings.TTS_PROVIDER or "").lower().strip()

    if provider == "elevenlabs":
        if not settings.ELEVENLABS_API_KEY:
            log.warning("ElevenLabs TTS requested but ELEVENLABS_API_KEY is not configured. TTS audio skipped.")
            return None
        return await _elevenlabs(clean, voice)

    if provider == "piper":
        if not shutil.which("piper"):
            log.warning("Piper TTS CLI not found on PATH. Install piper for offline local TTS. TTS audio skipped.")
            return None
        return _piper(clean, voice)

    if provider == "openai":
        if not settings.OPENAI_API_KEY:
            log.warning("OpenAI TTS requested but OPENAI_API_KEY is not configured. TTS audio skipped (recommend piper for local offline TTS).")
            return None
        return await _openai(clean, voice)

    log.warning("Unknown TTS provider '%s'. TTS audio skipped.", provider)
    return None


async def _openai(text: str, voice: str) -> TtsResult:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    resp = await client.audio.speech.create(
        model=settings.OPENAI_TTS_MODEL,
        voice=voice,
        input=text[:4096],
        response_format="mp3",
    )
    return TtsResult(resp.read(), "mp3", "audio/mpeg")


async def _elevenlabs(text: str, voice: str) -> TtsResult:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice}"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            headers={
                "xi-api-key": settings.ELEVENLABS_API_KEY,
                "accept": "audio/mpeg",
            },
            json={"text": text[:5000], "model_id": "eleven_multilingual_v2"},
        )
        resp.raise_for_status()
        return TtsResult(resp.content, "mp3", "audio/mpeg")


def _piper(text: str, voice: str) -> TtsResult:
    """Local, offline TTS via the piper CLI. Emits WAV bytes."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as out:
        out_path = out.name
    proc = subprocess.run(
        ["piper", "--model", voice or settings.PIPER_VOICE, "--output_file", out_path],
        input=text.encode(),
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"piper failed: {proc.stderr.decode()[:300]}")
    with open(out_path, "rb") as f:
        return TtsResult(f.read(), "wav", "audio/wav")
