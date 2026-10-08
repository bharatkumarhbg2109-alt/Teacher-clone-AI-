"""LLM Provider factory with local Ollama as default."""
import logging
import os
from typing import Optional

from app.config import settings
from app.services.llm.base import LLMProvider
from app.services.llm.ollama import OllamaProvider

log = logging.getLogger("teachclone.llm.factory")

_cached_providers: dict[str, LLMProvider] = {}


def get_llm_provider(name: Optional[str] = None) -> LLMProvider:
    """Get the active LLM provider.

    Defaults to Ollama (100% offline, zero paid API keys).
    Paid providers (Anthropic, OpenAI) are only activated if explicitly configured
    AND their respective API keys are present in the environment/settings.
    """
    provider_name = (
        name
        or os.getenv("LLM_PROVIDER")
        or getattr(settings, "LLM_PROVIDER", "ollama")
        or "ollama"
    ).lower().strip()

    if provider_name == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY") or getattr(settings, "ANTHROPIC_API_KEY", "")
        if key:
            if "anthropic" not in _cached_providers:
                from app.services.llm.anthropic import AnthropicProvider

                _cached_providers["anthropic"] = AnthropicProvider(api_key=key)
            return _cached_providers["anthropic"]
        log.warning(
            "Anthropic requested but ANTHROPIC_API_KEY is not configured. Falling back to local OllamaProvider."
        )

    elif provider_name == "openai":
        key = os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", "")
        if key:
            if "openai" not in _cached_providers:
                from app.services.llm.openai import OpenAIProvider

                _cached_providers["openai"] = OpenAIProvider(api_key=key)
            return _cached_providers["openai"]
        log.warning(
            "OpenAI requested but OPENAI_API_KEY is not configured. Falling back to local OllamaProvider."
        )

    # Default to Ollama
    if "ollama" not in _cached_providers:
        _cached_providers["ollama"] = OllamaProvider()
    return _cached_providers["ollama"]


def reset_llm_provider_cache() -> None:
    """Clear provider cache (used in tests)."""
    _cached_providers.clear()
