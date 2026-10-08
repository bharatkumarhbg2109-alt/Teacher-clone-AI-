"""Tests for LLM provider abstraction, defaults, and configuration."""
import os
from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from app.services.llm import (
    AnthropicProvider,
    LLMProvider,
    OllamaProvider,
    OpenAIProvider,
    complete_text,
    get_llm_provider,
    reset_llm_provider_cache,
    stream_teaching,
)


@pytest.fixture(autouse=True)
def clean_provider_state():
    reset_llm_provider_cache()
    yield
    reset_llm_provider_cache()


def test_default_provider_is_ollama():
    """Verify that the default LLM provider is Ollama with local zero-cost settings."""
    with patch.dict(os.environ, {}, clear=True):
        # Ensure no paid keys in env
        os.environ.pop("ANTHROPIC_API_KEY", None)
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("LLM_PROVIDER", None)

        provider = get_llm_provider()
        assert isinstance(provider, OllamaProvider)
        assert provider.provider_name == "ollama"
        assert "11434" in provider.host
        assert "llama3.1" in provider.model_name


def test_no_hardcoded_claude_opus():
    """Verify that claude-opus-4-8 is not hardcoded anywhere in config or providers."""
    assert "claude-opus-4-8" not in getattr(settings, "ANTHROPIC_MODEL", "")
    assert "claude-opus-4-8" not in getattr(settings, "OLLAMA_MODEL", "")

    # Ollama provider model can be customized via env/param
    custom = OllamaProvider(model="mistral:7b")
    assert custom.model_name == "mistral:7b"


def test_paid_provider_used_only_when_key_present():
    """Verify that requesting a paid provider without an API key falls back to Ollama."""
    # Anthropic without key -> falls back to Ollama
    with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": ""}, clear=True):
        provider = get_llm_provider("anthropic")
        assert isinstance(provider, OllamaProvider)

    # OpenAI without key -> falls back to Ollama
    with patch.dict(os.environ, {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": ""}, clear=True):
        provider = get_llm_provider("openai")
        assert isinstance(provider, OllamaProvider)


def test_paid_provider_instantiated_when_key_is_provided():
    """Verify Anthropic/OpenAI providers are instantiated only when key is provided."""
    reset_llm_provider_cache()
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test-key-12345"}):
        provider = get_llm_provider("anthropic")
        assert isinstance(provider, AnthropicProvider)
        assert provider.provider_name == "anthropic"

    reset_llm_provider_cache()
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-openai-key-12345"}):
        provider = get_llm_provider("openai")
        assert isinstance(provider, OpenAIProvider)
        assert provider.provider_name == "openai"


@pytest.mark.asyncio
async def test_ollama_chat_and_stream_delegation():
    """Verify high-level helper functions delegate properly to the provider."""
    provider = get_llm_provider()

    async def mock_stream(*args, **kwargs):
        yield "Hello"
        yield " from"
        yield " Ollama"

    with patch.object(provider, "stream_chat", side_effect=mock_stream):
        tokens = []
        async for t in stream_teaching("system prompt", [{"role": "user", "content": "hi"}]):
            tokens.append(t)
        assert "".join(tokens) == "Hello from Ollama"

    with patch.object(provider, "chat", new_callable=AsyncMock, return_value="Complete answer"):
        result = await complete_text("system prompt", [{"role": "user", "content": "hi"}])
        assert result == "Complete answer"
