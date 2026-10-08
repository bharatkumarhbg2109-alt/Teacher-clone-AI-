"""Application settings, loaded from the environment via Pydantic."""
import secrets as _secrets
import sys as _sys
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # --- App ---------------------------------------------------------------
    APP_NAME: str = "TeachClone API"
    VERSION: str = "0.1.0"
    ENV: str = "local"  # local | staging | production
    DEBUG: bool = False
    # DEV_MODE bypasses Clerk/Stripe and uses a local dev user, so the core
    # product runs with only an Anthropic key.
    DEV_MODE: bool = True
    DEV_USER_EMAIL: str = "dev@teachclone.local"
    DEV_USER_NAME: str = "Dev Student"
    APP_URL: str = "http://localhost:3000"
    API_URL: str = "http://localhost:8000"

    # --- Database ----------------------------------------------------------
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/teachclone"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # --- Redis / Celery ----------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Qdrant ------------------------------------------------------------
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "teachclone_chunks"

    # --- General secret (embed tokens, session signing, etc.) ---------------
    SECRET_KEY: str = ""

    # --- LLM Provider (ollama | anthropic | openai) ------------------------
    LLM_PROVIDER: str = "ollama"

    # --- Anthropic (LLM + vision + PDF) ------------------------------------
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    ANTHROPIC_MAX_TOKENS: int = 4096
    ANTHROPIC_EFFORT: str = "medium"  # low | medium | high | xhigh | max

    # --- Ollama (local LLM — 100% offline, zero paid API keys) -------------
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.1:8b"       # default model
    OLLAMA_FALLBACK_MODEL: str = "mistral"  # used if the primary model errors
    OLLAMA_TIMEOUT: int = 120               # seconds per request
    OLLAMA_TEMPERATURE: float = 0.1         # low = consistent extraction
    OLLAMA_NUM_PREDICT: int = 2000
    OLLAMA_NUM_CTX: int = 8192

    # --- Teacher DNA pipeline ----------------------------------------------
    # When true, teacher-style extraction uses the local 7-layer DNA pipeline
    # (Ollama + faster-whisper) instead of the legacy statistical method.
    USE_DNA_PIPELINE: bool = True
    DNA_WHISPER_MODEL: str = "base"         # base = fast and offline-friendly
    DNA_TRANSCRIPT_CHAR_LIMIT: int = 12000  # per-layer prompt truncation
    DNA_EMBED_TRANSCRIPTS: bool = True       # also embed DNA transcripts for RAG
    DNA_REPORTS_DIR: str = "./dna_reports"
    SYSTEM_PROMPTS_DIR: str = "./system_prompts"

    # --- Embeddings (provider: openai | local) -----------------------------
    EMBEDDING_PROVIDER: str = "openai"
    OPENAI_API_KEY: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"
    EMBEDDING_DIM: int = 3072
    LOCAL_EMBEDDING_MODEL: str = "BAAI/bge-large-en-v1.5"

    # --- TTS / audio output (provider: openai | elevenlabs | piper) --------
    TTS_PROVIDER: str = "openai"
    OPENAI_TTS_MODEL: str = "tts-1"
    DEFAULT_TTS_VOICE: str = "nova"
    ELEVENLABS_API_KEY: str = ""
    PIPER_VOICE: str = "en_US-amy-medium"

    # --- Whisper (speech-to-text) ------------------------------------------
    WHISPER_MODEL: str = "base"
    WHISPER_DEVICE: str = "cpu"
    WHISPER_COMPUTE_TYPE: str = "int8"

    # --- Clerk (optional in DEV_MODE) --------------------------------------
    CLERK_SECRET_KEY: str = ""
    CLERK_WEBHOOK_SECRET: str = ""
    CLERK_JWKS_URL: str = "https://api.clerk.com/v1/jwks"

    # --- Stripe (optional in DEV_MODE) -------------------------------------
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRO_PRICE_ID: str = ""
    STRIPE_CREATOR_PRICE_ID: str = ""
    STRIPE_INSTITUTION_PRICE_ID: str = ""

    # --- Object storage (S3 / R2 / MinIO) ----------------------------------
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_ACCESS_KEY_ID: str = "minioadmin"
    S3_SECRET_ACCESS_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "teachclone-media"
    S3_REGION: str = "auto"
    S3_PUBLIC_URL: str = "http://localhost:9000/teachclone-media"

    # --- Email -------------------------------------------------------------
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "noreply@teachclone.app"

    # --- Monitoring --------------------------------------------------------
    SENTRY_DSN: str = ""

    # --- Rate limiting (per-user, sliding window) ---------------------------
    # Limits are expressed as max requests per window_seconds.
    RATE_LIMIT_CHAT: int = 30           # chat messages per window
    RATE_LIMIT_DNA: int = 5             # DNA extraction jobs per window
    RATE_LIMIT_AUTH: int = 10           # auth attempts per window (IP-based)
    RATE_LIMIT_AUTH_WINDOW: int = 60    # auth window in seconds
    RATE_LIMIT_UPLOAD: int = 20         # upload requests per window
    RATE_LIMIT_VOICE: int = 60          # voice requests per window
    RATE_LIMIT_PUBLIC: int = 100        # public endpoint requests per window
    RATE_LIMIT_WINDOW: int = 60         # default window size in seconds
    RATE_LIMIT_BURST_MULTIPLIER: float = 1.5  # short burst allowance
    RATE_LIMIT_BACKOFF_BASE: int = 60   # base window for auth backoff (seconds)
    RATE_LIMIT_BACKOFF_MAX: int = 900   # max backoff window (15 min)

    # --- Free-plan quotas --------------------------------------------------
    FREE_VIDEOS_PER_MONTH: int = 3
    FREE_MESSAGES_PER_DAY: int = 50
    FREE_QUIZZES_PER_MONTH: int = 5
    FREE_EXPORTS_PER_MONTH: int = 2

    # --- Upload limits -----------------------------------------------------
    # "Any size" — high ceilings; large files use multipart uploads.
    MULTIPART_THRESHOLD_BYTES: int = 64 * 1024 * 1024  # 64 MB → multipart
    MULTIPART_PART_SIZE_BYTES: int = 32 * 1024 * 1024  # 32 MB parts

    # --- Local / no-infra mode (native run without Docker) -----------------
    # storage: s3 | local ; vectors: qdrant | local ; INLINE_TASKS runs the
    # ingestion pipeline in-process (no Redis/Celery worker needed).
    STORAGE_BACKEND: str = "s3"
    VECTOR_BACKEND: str = "qdrant"
    INLINE_TASKS: bool = False
    LOCAL_STORAGE_DIR: str = "./storage_data"

    @property
    def price_to_plan(self) -> dict[str, str]:
        return {
            self.STRIPE_PRO_PRICE_ID: "pro",
            self.STRIPE_CREATOR_PRICE_ID: "creator",
            self.STRIPE_INSTITUTION_PRICE_ID: "institution",
        }

    def model_post_init(self, __context: object) -> None:
        # --- C2: DEV_MODE guard -------------------------------------------------
        # DEV_MODE=true with a non-local ENV is a critical misconfiguration.
        if self.DEV_MODE and self.ENV not in ("local", ""):
            print("\n" + "!" * 60)
            print("CRITICAL SECURITY WARNING")
            print("DEV_MODE=true is set but ENV is not 'local'.")
            print("This bypasses ALL authentication. Refusing to start.")
            print("Set DEV_MODE=false in your production .env file.")
            print("!" * 60 + "\n")
            _sys.exit(1)

        # --- C1: SECRET_KEY guard -----------------------------------------------
        if not self.SECRET_KEY or len(self.SECRET_KEY) < 32:
            if self.DEV_MODE:
                auto_key = _secrets.token_hex(32)
                # Mutate the field so downstream code sees the generated key.
                object.__setattr__(self, "SECRET_KEY", auto_key)
                print(f"\n{'=' * 60}")
                print(f"[DEV] Auto-generated SECRET_KEY for local development.")
                print(f"[DEV] Add this to your .env file:")
                print(f"SECRET_KEY={auto_key}")
                print(f"{'=' * 60}\n")
            else:
                raise ValueError(
                    "SECRET_KEY must be set to a random string of 32+ characters. "
                    'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
                )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
