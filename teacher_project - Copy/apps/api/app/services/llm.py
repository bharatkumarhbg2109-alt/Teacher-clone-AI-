"""Anthropic Claude wrapper — teaching chat, structured JSON, and vision/PDF.

Model: claude-opus-4-8. Teaching chat streams with thinking disabled for a
snappy first token (the teaching system prompt tightly controls output). JSON
extraction uses structured outputs. Vision handles diagrams/slides/images and
scanned-PDF OCR.
"""
import json
from typing import AsyncGenerator

from anthropic import AsyncAnthropic

from app.config import settings

_client: AsyncAnthropic | None = None


def client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


async def stream_teaching(
    system: str,
    messages: list[dict],
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """Stream a teaching response as text deltas."""
    async with client().messages.stream(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=max_tokens or settings.ANTHROPIC_MAX_TOKENS,
        system=system,
        messages=messages,
        thinking={"type": "disabled"},
    ) as stream:
        async for text in stream.text_stream:
            yield text


async def complete_text(
    system: str,
    messages: list[dict],
    max_tokens: int | None = None,
) -> str:
    """Non-streaming teaching response (used by the sync /v1 API)."""
    resp = await client().messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=max_tokens or settings.ANTHROPIC_MAX_TOKENS,
        system=system,
        messages=messages,
        thinking={"type": "disabled"},
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        text = text[4:] if text.lower().startswith("json") else text
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


async def complete_json(
    prompt: str,
    schema: dict,
    max_tokens: int = 4096,
    system: str | None = None,
) -> dict:
    """Structured JSON output. Uses structured outputs when the SDK supports
    them, otherwise falls back to prompt-instructed JSON."""
    sys = system or "You output only valid JSON matching the requested schema. No prose, no markdown."
    try:
        resp = await client().messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=sys,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
    except TypeError:
        resp = await client().messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=sys,
            messages=[
                {"role": "user", "content": prompt + "\n\nReturn ONLY a valid JSON object."}
            ],
        )
    text = next((b.text for b in resp.content if b.type == "text"), "{}")
    return _extract_json(text)


async def vision_describe(
    images_b64: list[str],
    instruction: str,
    media_type: str = "image/jpeg",
    max_tokens: int = 2048,
) -> str:
    """Describe / OCR a batch of images (diagrams, slides, scanned pages)."""
    content: list[dict] = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": b64},
        }
        for b64 in images_b64
    ]
    content.append({"type": "text", "text": instruction})
    resp = await client().messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


async def read_pdf(pdf_b64: str, instruction: str, max_tokens: int = 4096) -> str:
    """Read a PDF natively (handles scanned pages, tables, diagrams)."""
    resp = await client().messages.create(
        model=settings.ANTHROPIC_MODEL,
        max_tokens=max_tokens,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": pdf_b64,
                        },
                    },
                    {"type": "text", "text": instruction},
                ],
            }
        ],
    )
    return "".join(b.text for b in resp.content if b.type == "text")
