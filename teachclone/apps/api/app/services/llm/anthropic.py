"""Anthropic Claude LLM provider (optional paid provider)."""
import json
import logging
import os
from typing import Any, AsyncGenerator

from app.config import settings
from app.services.llm.base import LLMProvider, extract_json_payload

log = logging.getLogger("teachclone.llm.anthropic")


class AnthropicProvider(LLMProvider):
    provider_name: str = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY") or getattr(settings, "ANTHROPIC_API_KEY", "")
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not configured. AnthropicProvider cannot be used without an API key."
            )
        self.model_name = (
            model
            or os.getenv("ANTHROPIC_MODEL")
            or getattr(settings, "ANTHROPIC_MODEL", None)
            or "claude-3-5-sonnet-20241022"
        )
        self.max_tokens = max_tokens or getattr(settings, "ANTHROPIC_MAX_TOKENS", 4096)
        self._client = None

    def _get_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self.api_key)
        return self._client

    async def chat(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        client = self._get_client()
        resp = await client.messages.create(
            model=self.model_name,
            max_tokens=max_tokens or self.max_tokens,
            system=system or "",
            messages=messages,
            thinking={"type": "disabled"},
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    async def stream_chat(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        client = self._get_client()
        async with client.messages.stream(
            model=self.model_name,
            max_tokens=max_tokens or self.max_tokens,
            system=system or "",
            messages=messages,
            thinking={"type": "disabled"},
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # Anthropic does not provide native vector embedding API.
        # Fall back to local hash/dimension representation or raise
        log.warning("Anthropic does not offer vector embeddings; falling back to deterministic embedding.")
        import hashlib
        dim = getattr(settings, "EMBEDDING_DIM", 512)
        res = []
        for text in texts:
            v = [0.0] * dim
            for word in text.lower().split():
                idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % dim
                v[idx] += 1.0
            res.append(v)
        return res

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
        mt = max_tokens or self.max_tokens
        if schema:
            try:
                resp = await client.messages.create(
                    model=self.model_name,
                    max_tokens=mt,
                    system=sys,
                    messages=[{"role": "user", "content": prompt}],
                    output_config={"format": {"type": "json_schema", "schema": schema}},
                )
                text = next((b.text for b in resp.content if b.type == "text"), "{}")
                return extract_json_payload(text)
            except Exception:
                pass

        resp = await client.messages.create(
            model=self.model_name,
            max_tokens=mt,
            system=sys,
            messages=[
                {"role": "user", "content": prompt + "\n\nReturn ONLY a valid JSON object."}
            ],
        )
        text = next((b.text for b in resp.content if b.type == "text"), "{}")
        return extract_json_payload(text)

    async def vision_describe(
        self,
        images_b64: list[str],
        instruction: str,
        media_type: str = "image/jpeg",
        max_tokens: int = 2048,
    ) -> str:
        client = self._get_client()
        content: list[dict] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": b64},
            }
            for b64 in images_b64
        ]
        content.append({"type": "text", "text": instruction})
        resp = await client.messages.create(
            model=self.model_name,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": content}],
        )
        return "".join(b.text for b in resp.content if b.type == "text")

    async def read_pdf(
        self,
        pdf_b64: str,
        instruction: str,
        max_tokens: int = 4096,
    ) -> str:
        client = self._get_client()
        resp = await client.messages.create(
            model=self.model_name,
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
