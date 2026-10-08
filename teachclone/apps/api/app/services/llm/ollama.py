"""Ollama local LLM provider (default, 100% offline)."""
import json
import logging
import os
from typing import Any, AsyncGenerator

import httpx

from app.config import settings
from app.services.llm.base import LLMProvider, extract_json_payload

log = logging.getLogger("teachclone.llm.ollama")


class OllamaProvider(LLMProvider):
    provider_name: str = "ollama"

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ):
        self.host = (
            host
            or os.getenv("OLLAMA_HOST")
            or os.getenv("OLLAMA_BASE_URL")
            or getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        ).rstrip("/")
        self.model_name = (
            model
            or os.getenv("OLLAMA_MODEL")
            or getattr(settings, "OLLAMA_MODEL", None)
            or "llama3.1:8b"
        )
        self.timeout = timeout or getattr(settings, "OLLAMA_TIMEOUT", 120)

    def _prepare_messages(self, messages: list[dict], system: str | None = None) -> list[dict]:
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
        options = {
            "temperature": kwargs.get("temperature", getattr(settings, "OLLAMA_TEMPERATURE", 0.1)),
            "num_ctx": kwargs.get("num_ctx", getattr(settings, "OLLAMA_NUM_CTX", 8192)),
        }
        num_predict = max_tokens or kwargs.get("num_predict", getattr(settings, "OLLAMA_NUM_PREDICT", 2000))
        if num_predict:
            options["num_predict"] = num_predict

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": self._prepare_messages(messages, system),
            "stream": False,
            "options": options,
        }
        if "format" in kwargs:
            payload["format"] = kwargs["format"]

        url = f"{self.host}/api/chat"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url, json=payload)
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                raise RuntimeError(
                    f"Cannot reach Ollama at {self.host} — is `ollama serve` running?"
                ) from exc

            if resp.status_code == 404:
                raise RuntimeError(
                    f"Ollama model '{self.model_name}' not found. Run: ollama pull {self.model_name}"
                )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "")

    async def stream_chat(
        self,
        messages: list[dict],
        system: str | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        options = {
            "temperature": kwargs.get("temperature", getattr(settings, "OLLAMA_TEMPERATURE", 0.1)),
            "num_ctx": kwargs.get("num_ctx", getattr(settings, "OLLAMA_NUM_CTX", 8192)),
        }
        num_predict = max_tokens or kwargs.get("num_predict", getattr(settings, "OLLAMA_NUM_PREDICT", 2000))
        if num_predict:
            options["num_predict"] = num_predict

        payload = {
            "model": self.model_name,
            "messages": self._prepare_messages(messages, system),
            "stream": True,
            "options": options,
        }
        url = f"{self.host}/api/chat"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code == 404:
                        raise RuntimeError(
                            f"Ollama model '{self.model_name}' not found. Run: ollama pull {self.model_name}"
                        )
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        chunk = json.loads(line)
                        content = chunk.get("message", {}).get("content", "")
                        if content:
                            yield content
            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                raise RuntimeError(
                    f"Cannot reach Ollama at {self.host} — is `ollama serve` running?"
                ) from exc

    async def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embed_model = os.getenv("OLLAMA_EMBED_MODEL") or "nomic-embed-text"
        url = f"{self.host}/api/embed"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url, json={"model": embed_model, "input": texts})
                if resp.status_code == 200:
                    embeddings = resp.json().get("embeddings")
                    if embeddings:
                        return embeddings
            except Exception as exc:
                log.warning("Ollama /api/embed failed (%s); trying fallback", exc)

            # Fallback to /api/embeddings per text
            embeddings_list: list[list[float]] = []
            for t in texts:
                try:
                    emb_resp = await client.post(
                        f"{self.host}/api/embeddings",
                        json={"model": self.model_name, "prompt": t},
                    )
                    if emb_resp.status_code == 200:
                        embeddings_list.append(emb_resp.json().get("embedding", []))
                        continue
                except Exception:
                    pass

                # Deterministic hash fallback
                import hashlib
                dim = getattr(settings, "EMBEDDING_DIM", 512)
                v = [0.0] * dim
                for word in t.lower().split():
                    idx = int(hashlib.md5(word.encode()).hexdigest(), 16) % dim
                    v[idx] += 1.0
                embeddings_list.append(v)
            return embeddings_list

    async def complete_json(
        self,
        prompt: str,
        schema: dict | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
        **kwargs: Any,
    ) -> dict:
        sys = system or "You output only valid JSON matching the requested schema. No prose, no markdown."
        if schema:
            sys += f"\n\nJSON SCHEMA:\n{json.dumps(schema)}"
        content = await self.chat(
            [{"role": "user", "content": prompt}],
            system=sys,
            max_tokens=max_tokens,
            format="json",
            **kwargs,
        )
        return extract_json_payload(content)

    async def vision_describe(
        self,
        images_b64: list[str],
        instruction: str,
        media_type: str = "image/jpeg",
        max_tokens: int = 2048,
    ) -> str:
        vision_model = os.getenv("OLLAMA_VISION_MODEL", "llava")
        messages = [
            {
                "role": "user",
                "content": instruction,
                "images": images_b64,
            }
        ]
        url = f"{self.host}/api/chat"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(url, json={"model": vision_model, "messages": messages, "stream": False})
                if resp.status_code == 200:
                    return resp.json().get("message", {}).get("content", "")
            except Exception as exc:
                log.warning("Ollama vision call failed: %s", exc)
        return ""
