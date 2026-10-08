"""
Vision processing module — sends images to Ollama llava:7b for visual reasoning.
Called from chat_router.py when an uploaded file is an image.
"""
import base64
import httpx
from pathlib import Path

OLLAMA_URL = "http://localhost:11434/api/chat"
VISION_MODEL = "llava:7b"

SUPPORTED_FORMATS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def is_image(file_path: str) -> bool:
    return Path(file_path).suffix.lower() in SUPPORTED_FORMATS


async def describe_image(
    image_path: str,
    user_prompt: str = "Describe this image in detail. Extract any text, diagrams, tables, or educational content visible.",
    context_docs: str = ""
) -> str:
    """
    Send image to LLaVA and return descriptive text to inject into RAG context.
    Returns descriptive string or fallback message if llava is unavailable (graceful fallback).
    """
    try:
        with open(image_path, "rb") as f:
            image_b64 = base64.b64encode(f.read()).decode("utf-8")

        system_prompt = (
            "You are an educational content analyzer. "
            "Extract all useful information from images including text, diagrams, equations, charts, and tables. "
            "Format extracted content for use as study material."
        )
        if context_docs:
            system_prompt += f"\n\nRelated course context:\n{context_docs[:1000]}"

        payload = {
            "model": VISION_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": user_prompt,
                    "images": [image_b64]
                }
            ],
            "stream": False,
            "options": {"temperature": 0.1}
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(OLLAMA_URL, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("message", {}).get("content", "")

    except httpx.ConnectError:
        return "[Vision unavailable: Ollama not running or llava:7b not pulled]"
    except httpx.HTTPStatusError as e:
        if "model not found" in str(e).lower():
            return "[Vision unavailable: run 'ollama pull llava:7b' to enable image analysis]"
        return f"[Vision error: {str(e)}]"
    except Exception as e:
        return f"[Vision processing failed: {str(e)}]"
