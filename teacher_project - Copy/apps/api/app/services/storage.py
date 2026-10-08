"""Object storage.

- backend "s3": S3-compatible (MinIO / R2 / S3), presigned uploads + multipart.
- backend "local": files on disk, "presigned" URLs point at the API's /storage
  endpoints. Used for the native, no-infra run.
"""
import os
import re
import shutil
import uuid
from urllib.parse import quote

from app.config import settings


# ---------------------------------------------------------------------------
#  File upload validation
# ---------------------------------------------------------------------------

# Magic byte signatures: {mime_type: [(offset, signature), ...]}
MAGIC_BYTES: dict[str, list[tuple[int, bytes]]] = {
    "video/mp4": [(4, b"ftyp")],
    "video/webm": [(0, b"\x1a\x45\xdf\xa3")],
    "audio/mpeg": [(0, b"\xff\xfb"), (0, b"\xff\xf3"), (0, b"\xff\xf2"), (0, b"ID3")],
    "audio/wav": [(0, b"RIFF")],
    "audio/ogg": [(0, b"OggS")],
    "application/pdf": [(0, b"%PDF")],
    "image/jpeg": [(0, b"\xff\xd8\xff")],
    "image/png": [(0, b"\x89PNG\r\n\x1a\n")],
    "image/gif": [(0, b"GIF87a"), (0, b"GIF89a")],
}

ALLOWED_MIME_TYPES: set[str] = set(MAGIC_BYTES.keys()) | {
    # Types we accept but can't verify via magic bytes alone
    "audio/x-wav", "audio/wave",
    "video/x-matroska", "video/avi",
    "image/webp", "image/bmp", "image/tiff",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "text/plain", "text/markdown",
}

MAX_FILE_SIZES: dict[str, int] = {
    "video": 2 * 1024 * 1024 * 1024,       # 2 GB
    "audio": 500 * 1024 * 1024,             # 500 MB
    "application/pdf": 100 * 1024 * 1024,   # 100 MB
    "image": 20 * 1024 * 1024,              # 20 MB
    "text": 50 * 1024 * 1024,               # 50 MB
}



def get_max_file_size(content_type: str) -> int:
    """Return the maximum allowed file size in bytes for a given MIME type.

    Walks MAX_FILE_SIZES keys; returns the first prefix match.
    Falls back to 100 MB for unknown types.
    """
    ct = (content_type or "").split(";")[0].strip().lower()
    for category, max_size in MAX_FILE_SIZES.items():
        if ct.startswith(category):
            return max_size
    return 100 * 1024 * 1024  # 100 MB default for unknown types


def validate_file_upload(
    filename: str,
    content_type: str,
    file_size: int,
    file_header: bytes | None = None,
) -> None:
    """Validate file upload metadata. Raises HTTPException on any violation.

    - Checks declared MIME type is in allowed list
    - Checks actual file magic bytes match declared type (if header provided)
    - Checks file size is within bounds
    - Checks filename has no path traversal or dangerous characters
    """
    from fastapi import HTTPException

    # 1. Filename safety
    basename = os.path.basename(filename)
    if basename != filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")
    if not re.match(r"^[\w\-. ]+$", basename):
        raise HTTPException(400, "Filename contains invalid characters")

    # 2. MIME type in allowlist
    ct = (content_type or "").split(";")[0].strip().lower()  # strip charset etc
    if ct and ct not in ALLOWED_MIME_TYPES:
        raise HTTPException(400, f"File type '{ct}' is not allowed")

    # 3. File size check
    if file_size > 0:
        for category, max_size in MAX_FILE_SIZES.items():
            if ct.startswith(category) and file_size > max_size:
                max_mb = max_size // (1024 * 1024)
                raise HTTPException(400, f"File too large. Maximum size is {max_mb} MB")

    # 4. Magic byte verification (if header is available)
    if file_header and ct in MAGIC_BYTES:
        signatures = MAGIC_BYTES[ct]
        matched = any(
            file_header[offset : offset + len(sig)] == sig
            for offset, sig in signatures
        )
        if not matched:
            raise HTTPException(400, "File content does not match declared type")

LOCAL = settings.STORAGE_BACKEND == "local"


class StorageService:
    def __init__(self) -> None:
        self._client = None
        self.bucket = settings.S3_BUCKET_NAME
        if LOCAL:
            os.makedirs(settings.LOCAL_STORAGE_DIR, exist_ok=True)

    # --- s3 client (lazy) ---------------------------------------------------
    @property
    def client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY_ID,
                aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
                config=Config(signature_version="s3v4"),
                region_name=settings.S3_REGION,
            )
        return self._client

    def _local_path(self, key: str) -> str:
        return os.path.join(settings.LOCAL_STORAGE_DIR, key)

    def generate_key(self, user_id: str, profile_id: str, filename: str) -> str:
        ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
        return f"media/{user_id}/{profile_id}/{uuid.uuid4()}.{ext}"

    # --- Single-shot upload -------------------------------------------------
    def presign_put(self, key: str, content_type: str, expires: int = 3600) -> str:
        """Legacy PUT URL — kept for local storage backend."""
        if LOCAL:
            return f"{settings.API_URL}/storage/put?key={quote(key)}"
        return self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=expires,
            HttpMethod="PUT",
        )

    def presign_post(
        self,
        key: str,
        content_type: str,
        max_size_bytes: int,
        expires: int = 3600,
    ) -> dict:
        """Generate a presigned POST with S3-enforced Conditions.

        S3 will reject the upload at the storage layer if:
        - Content-Length exceeds ``max_size_bytes``
        - Content-Type header doesn't match ``content_type``

        Returns ``{"url": ..., "fields": {...}}`` — the client POSTs
        a multipart form with these fields + the file blob.

        For the local backend, falls back to a presigned PUT URL (no
        S3 conditions available) wrapped in the same shape.
        """
        if LOCAL:
            return {
                "url": f"{settings.API_URL}/storage/put?key={quote(key)}",
                "fields": {"Content-Type": content_type},
            }
        response = self.client.generate_presigned_post(
            Bucket=self.bucket,
            Key=key,
            Conditions=[
                ["content-length-range", 0, max_size_bytes],
                ["eq", "$Content-Type", content_type],
            ],
            Fields={
                "Content-Type": content_type,
            },
            ExpiresIn=expires,
        )
        return response

    def presign_get(self, key: str, expires: int = 86400) -> str:
        if LOCAL:
            return f"{settings.API_URL}/storage/get?key={quote(key)}"
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires,
        )

    # --- Multipart (s3 only) ------------------------------------------------
    def create_multipart(self, key: str, content_type: str) -> str:
        return self.client.create_multipart_upload(
            Bucket=self.bucket, Key=key, ContentType=content_type
        )["UploadId"]

    def presign_part(self, key: str, upload_id: str, part_number: int, expires: int = 3600) -> str:
        return self.client.generate_presigned_url(
            "upload_part",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "UploadId": upload_id,
                "PartNumber": part_number,
            },
            ExpiresIn=expires,
            HttpMethod="PUT",
        )

    def complete_multipart(self, key: str, upload_id: str, parts: list[dict]) -> None:
        self.client.complete_multipart_upload(
            Bucket=self.bucket, Key=key, UploadId=upload_id,
            MultipartUpload={"Parts": parts},
        )

    def abort_multipart(self, key: str, upload_id: str) -> None:
        try:
            self.client.abort_multipart_upload(Bucket=self.bucket, Key=key, UploadId=upload_id)
        except Exception:
            pass

    # --- Direct helpers -----------------------------------------------------
    def object_exists(self, key: str) -> bool:
        if LOCAL:
            return os.path.exists(self._local_path(key))
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def object_size(self, key: str) -> int:
        if LOCAL:
            p = self._local_path(key)
            return os.path.getsize(p) if os.path.exists(p) else 0
        try:
            return int(self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"])
        except Exception:
            return 0

    def delete_object(self, key: str) -> bool:
        if LOCAL:
            try:
                os.remove(self._local_path(key))
                return True
            except Exception:
                return False
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def download_to_path(self, key: str, local_path: str) -> None:
        if LOCAL:
            shutil.copyfile(self._local_path(key), local_path)
            return
        self.client.download_file(self.bucket, key, local_path)

    def upload_bytes(self, key: str, data: bytes, content_type: str) -> str:
        if LOCAL:
            path = self._local_path(key)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            return self.presign_get(key)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        return f"{settings.S3_PUBLIC_URL}/{key}"

    def get_bytes(self, key: str) -> bytes:
        if LOCAL:
            with open(self._local_path(key), "rb") as f:
                return f.read()
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    # Used by the /storage local endpoints.
    def write_local(self, key: str, data: bytes) -> None:
        path = self._local_path(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)


storage_service = StorageService()
