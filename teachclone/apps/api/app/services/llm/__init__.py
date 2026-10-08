"""LLM provider package: provider-pluggable interface with local Ollama as default."""
from typing import AsyncGenerator

from app.services.llm.base import LLMProvider, extract_json_payload
from app.services.llm.factory import get_llm_provider, reset_llm_provider_cache
from app.services.llm.ollama import OllamaProvider


from app.services.llm.anthropic import AnthropicProvider
from app.services.llm.openai import OpenAIProvider


# Convenience helpers for backward-compatibility with code that called app.services.llm directly:
async def stream_teaching(
    system: str,
    messages: list[dict],
    max_tokens: int | None = None,
) -> AsyncGenerator[str, None]:
    """Stream teaching chat tokens from the configured LLM provider."""
    provider = get_llm_provider()
    async for token in provider.stream_chat(messages, system=system, max_tokens=max_tokens):
        yield token


async def complete_text(
    system: str,
    messages: list[dict],
    max_tokens: int | None = None,
) -> str:
    """Non-streaming chat completion from the configured LLM provider."""
    provider = get_llm_provider()
    return await provider.chat(messages, system=system, max_tokens=max_tokens)


async def complete_json(
    prompt: str,
    schema: dict | None = None,
    max_tokens: int = 4096,
    system: str | None = None,
) -> dict:
    """Structured JSON generation from the configured LLM provider."""
    provider = get_llm_provider()
    return await provider.complete_json(prompt, schema=schema, max_tokens=max_tokens, system=system)


async def vision_describe(
    images_b64: list[str],
    instruction: str,
    media_type: str = "image/jpeg",
    max_tokens: int = 2048,
) -> str:
    """Describe / OCR images."""
    provider = get_llm_provider()
    return await provider.vision_describe(images_b64, instruction, media_type=media_type, max_tokens=max_tokens)


async def read_pdf(pdf_b64: str, instruction: str, max_tokens: int = 4096) -> str:
    """Read and extract content from PDF."""
    provider = get_llm_provider()
    return await provider.read_pdf(pdf_b64, instruction, max_tokens=max_tokens)


__all__ = [
    "LLMProvider",
    "OllamaProvider",
    "AnthropicProvider",
    "OpenAIProvider",
    "get_llm_provider",
    "reset_llm_provider_cache",
    "extract_json_payload",
    "stream_teaching",
    "complete_text",
    "complete_json",
    "vision_describe",
    "read_pdf",
]
