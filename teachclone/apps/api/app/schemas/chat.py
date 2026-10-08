import re

from pydantic import BaseModel, Field, field_validator


class ChatMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    # Ask the server to also synthesize audio for the reply.
    want_audio: bool = False

    @field_validator("content")
    @classmethod
    def no_script_tags(cls, v: str) -> str:
        pattern = re.compile(r"<script|javascript:|data:text/html|on\w+\s*=", re.IGNORECASE)
        if pattern.search(v):
            raise ValueError("Message contains disallowed content")
        return v


class CitationResponse(BaseModel):
    media_source_id: str
    start_time: float | None = None
    end_time: float | None = None
    page: int | None = None
    chunk_text: str
