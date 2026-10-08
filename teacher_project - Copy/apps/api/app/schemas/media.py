import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class YouTubeIngestRequest(BaseModel):
    teacher_profile_id: str = Field(min_length=1, max_length=100)
    youtube_url: str = Field(min_length=1, max_length=500)

    @field_validator("youtube_url")
    @classmethod
    def must_be_youtube(cls, v: str) -> str:
        pattern = r"^https?://(www\.)?(youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)[a-zA-Z0-9_\-]{11}"
        if not re.match(pattern, v):
            raise ValueError("Must be a valid YouTube video URL")
        return v


class UploadInitiateRequest(BaseModel):
    teacher_profile_id: str = Field(min_length=1, max_length=100)
    file_name: str = Field(min_length=1, max_length=255)
    file_size: int = Field(ge=1, le=2_147_483_648)  # max 2 GB
    content_type: str = Field(min_length=1, max_length=100)


class UploadInitiateResponse(BaseModel):
    media_source_id: str
    upload_url: str | None = None
    upload_fields: dict | None = None  # presigned POST fields (S3-enforced conditions)
    upload_key: str
    multipart_upload_id: str | None = None
    part_size: int | None = None
    part_count: int | None = None
    expires_at: str


class MultipartPartRequest(BaseModel):
    media_source_id: str = Field(min_length=1, max_length=100)
    upload_key: str = Field(min_length=1, max_length=500)
    multipart_upload_id: str = Field(min_length=1, max_length=200)
    part_numbers: list[int] = Field(min_length=1, max_length=10000)
    # Validate each part number
    @field_validator("part_numbers")
    @classmethod
    def valid_part_numbers(cls, v: list[int]) -> list[int]:
        for n in v:
            if n < 1 or n > 10000:
                raise ValueError(f"Part number {n} out of range (1-10000)")
        return v


class MultipartPartUrl(BaseModel):
    part_number: int
    url: str


class UploadCompleteRequest(BaseModel):
    media_source_id: str = Field(min_length=1, max_length=100)
    storage_key: str = Field(min_length=1, max_length=500)
    # For multipart uploads:
    multipart_upload_id: str | None = Field(default=None, max_length=200)
    parts: list[dict] | None = None  # [{"PartNumber": n, "ETag": "..."}]


class MediaSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teacher_profile_id: UUID
    source_type: str
    original_url: str | None = None
    file_name: str | None = None
    file_size_bytes: int | None = None
    duration_seconds: int | None = None
    page_count: int | None = None
    status: str
    error_message: str | None = None
    transcript_chunks: int | None = None
    created_at: datetime


class ProcessingProgressResponse(BaseModel):
    status: str
    transcript_chunks: int | None = None
    stage: str | None = None
    progress: int | None = None
