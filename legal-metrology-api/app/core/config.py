"""
Centralized application configuration.
Loaded once as a cached singleton via `get_settings()`.
"""
from functools import lru_cache
from typing import List

from pydantic import AnyUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Application ---
    APP_NAME: str = "Legal Metrology Verification System"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: str
    DATABASE_URL_SYNC: str  # used by Alembic (sync driver)

    # --- JWT / Security ---
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # --- Certificate anti-tamper signing (separate secret from JWT) ---
    CERTIFICATE_HMAC_SECRET: str

    # --- Optional SMTP OTP delivery ---
    SMTP_SERVER: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None

    # --- Redis / Celery ---
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # --- CORS ---
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def _split_cors(cls, v):
        if isinstance(v, str) and not v.startswith("["):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # --- File Storage ---
    STORAGE_BACKEND: str = "local"  # "local" | "s3"
    LOCAL_STORAGE_PATH: str = "./storage"
    AWS_S3_BUCKET: str | None = None
    AWS_REGION: str = "ap-south-1"
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None

    # --- Uploads ---
    MAX_UPLOAD_SIZE_MB: int = 5
    ALLOWED_UPLOAD_MIME_TYPES: List[str] = Field(
        default_factory=lambda: ["image/jpeg", "image/png", "application/pdf"]
    )

    # --- Rate Limiting ---
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_PUBLIC_VERIFY: str = "20/minute"

    # --- Certificate lifecycle defaults (days), overridable per-instrument-category in DB ---
    DEFAULT_CERTIFICATE_VALIDITY_DAYS: int = 365
    EXPIRY_ALERT_OFFSETS_DAYS: List[int] = Field(default_factory=lambda: [30, 15, 7])


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
