"""Base LLM provider interface."""
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator
import json
import logging

log = logging.getLogger("teachclone.llm")


def extract_json_payload(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```", 2)
        if len(parts) > 1:
            text = parts[1]
        text = text[4:] if text.lower().startswith("json") else text
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


class LLMProvider(ABC):
    """Abstract base class for all LLM providers (Ollama, Anthropic, OpenAI)."""

    provider_name: str = "base"
    model_name: str = ""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Send chat messages and return the complete string response."""
        pass

    @abstractmethod
    async def stream_chat(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """Stream text tokens from the model."""
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Compute vector embeddings for a list of texts."""
        pass

    async def complete_json(
        self,
        prompt: str,
        schema: dict | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> dict:
        """Structured JSON generation with schema instruction and json parsing."""
        sys_prompt = system or "You output only valid JSON matching the requested schema. No prose, no markdown."
        if schema:
            prompt_content = f"{prompt}\n\nJSON SCHEMA:\n{json.dumps(schema)}"
        else:
            prompt_content = f"{prompt}\n\nReturn ONLY a valid JSON object."
        messages = [{"role": "user", "content": prompt_content}]
        response_text = await self.chat(messages, system=sys_prompt, max_tokens=max_tokens, **kwargs)
        return extract_json_payload(response_text)

    async def vision_describe(
        self,
        images_b64: list[str],
        instruction: str,
        media_type: str = "image/jpeg",
        max_tokens: int = 2048,
    ) -> str:
        """Describe or OCR keyframes / diagrams."""
        raise NotImplementedError(f"{self.provider_name} does not implement vision_describe")

    async def read_pdf(
        self,
        pdf_b64: str,
        instruction: str,
        max_tokens: int = 4096,
    ) -> str:
        """Natively read/analyze PDF."""
        raise NotImplementedError(f"{self.provider_name} does not implement read_pdf")
