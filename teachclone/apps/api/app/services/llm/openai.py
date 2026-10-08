"""OpenAI LLM provider (optional paid provider)."""
import json
import logging
import os
from typing import Any, AsyncGenerator

from app.config import settings
from app.services.llm.base import LLMProvider, extract_json_payload

log = logging.getLogger("teachclone.llm.openai")


class OpenAIProvider(LLMProvider):
    provider_name: str = "openai"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        embedding_model: str | None = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or getattr(settings, "OPENAI_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. OpenAIProvider cannot be used without an API key."
            )
        self.model_name = (
            model
            or os.getenv("OPENAI_MODEL")
            or "gpt-4o"
        )
        self.embedding_model = (
            embedding_model
            or os.getenv("OPENAI_EMBEDDING_MODEL")
            or getattr(settings, "OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
        )
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    def _format_messages(self, messages: list[dict], system: str | None = None) -> list[dict]:
        formatted = []
        if system:
            formatted.append({"role": "system", "content": system})
        for m in messages:
            formatted.append({"role": m.get("role", "user"), "content": m.get("content", "")})
        return formatted

    async def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        client = self._get_client()
        params: dict[str, Any] = {
            "model": self.model_name,
            "messages": self._format_messages(messages, system),
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]

        resp = await client.chat.completions.create(**params)
        return resp.choices[0].message.content or ""

    async def stream_chat(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        params: dict[str, Any] = {
            "model": self.model_name,
            "messages": self._format_messages(messages, system),
            "stream": True,
        }
        if max_tokens:
            params["max_tokens"] = max_tokens
        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]

        stream = await client.chat.completions.create(**params)
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        client = self._get_client()
        resp = await client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        return [item.embedding for item in resp.data]

    async def complete_json(
        self,
        prompt: str,
        schema: dict | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> dict:
        client = self._get_client()
        sys = system or "You output only valid JSON matching the requested schema. No prose, no markdown."
        messages = [
            {"role": "system", "content": sys},
            {"role": "user", "content": prompt},
        ]
        params: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "response_format": {"type": "json_object"},
        }
        if max_tokens:
            params["max_tokens"] = max_tokens

        resp = await client.chat.completions.create(**params)
        content = resp.choices[0].message.content or "{}"
        return extract_json_payload(content)

    async def vision_describe(
        self,
        images_b64: list[str],
        instruction: str,
        media_type: str = "image/jpeg",
        max_tokens: int = 2048,
    ) -> str:
        client = self._get_client()
        content: list[dict] = []
        for b64 in images_b64:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{media_type};base64,{b64}"},
            })
        content.append({"type": "text", "text": instruction})
        resp = await client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": content}],
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""
