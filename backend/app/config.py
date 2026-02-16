"""
Environment-based configuration. All secrets and URLs from env.
"""
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env from project root (parent of backend/) when run from backend/
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_ENV_FILES = [_PROJECT_ROOT / ".env", Path(".env")]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(p) for p in _ENV_FILES],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    app_name: str = "CV Resume Screening API"
    debug: bool = False
    allowed_origins: str = "*"  # Comma-separated in production, e.g. "https://app.example.com"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5433/screening"
    database_url_sync: Optional[str] = None  # For Alembic; set to postgresql://... if not set we derive from database_url

    # Redis & Celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: Optional[str] = None  # Defaults to redis_url

    # OpenAI (embeddings only)
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536

    # JWT
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24  # 24 hours
    jwt_refresh_expire_days: int = 30

    # Upload
    process_resumes_inline: bool = True  # If True, process CVs synchronously (no Celery). For dev when Celery/Redis not running.
    max_file_size_mb: int = 10
    max_files_per_batch: int = 100
    allowed_extensions: set[str] = frozenset({".pdf", ".docx"})
    upload_dir: str = "uploads"
    temp_dir: str = "temp"

    # Pagination
    default_page_size: int = 20
    max_page_size: int = 100

    def __init__(self, **kwargs):  # type: ignore
        super().__init__(**kwargs)
        if self.database_url_sync is None and self.database_url.startswith("postgresql+asyncpg://"):
            self.database_url_sync = self.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
        elif self.database_url_sync is None:
            self.database_url_sync = self.database_url
        if self.celery_broker_url is None:
            self.celery_broker_url = self.redis_url
        # Production: require non-default JWT secret (set DEBUG=true for local dev to allow default)
        if not self.debug and self.jwt_secret_key in ("change-me-in-production", ""):
            raise ValueError(
                "JWT_SECRET_KEY must be set to a secure value in production. "
                "Use e.g. openssl rand -hex 32"
            )

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
