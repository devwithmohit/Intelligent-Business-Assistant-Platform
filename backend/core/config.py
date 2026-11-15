from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_DEFAULT_DATABASE_URL = f"sqlite:///{(_BACKEND_DIR.parent / 'data' / 'dev.db').as_posix()}"
_DEFAULT_WORKFLOW_DIR = _BACKEND_DIR.parent / "data" / "workflows"
_DEFAULT_WORKFLOW_STATE_DIR = _BACKEND_DIR.parent / "data" / "workflow_states"
_DEFAULT_CHROMA_DIR = _BACKEND_DIR.parent / "data" / "vector_db" / "chroma"

_DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

INSECURE_SECRET_KEYS: set[str] = {
    "change-me-super-secret",
    "changeme",
    "secret",
    "secret-key",
    "default-secret-key",
    "generate-a-secure-random-key-here",
    "your-secret-key-here",
    "password",
    "admin",
}


def validate_security_settings(settings_obj: Settings) -> None:
    """
    Validate that critical secrets are securely configured.
    Fails fast and loudly with ValueError if insecure or default secrets
    are used in any non-development environment (e.g. production, staging).
    """
    env = (getattr(settings_obj, "ENV", None) or "").lower().strip()
    is_dev = env in ("development", "dev", "test", "testing", "local")
    secret = (getattr(settings_obj, "SECRET_KEY", None) or "").strip()

    if not is_dev:
        if not secret:
            raise ValueError(
                f"CRITICAL SECURITY CONFIGURATION ERROR: SECRET_KEY is not set in non-development environment '{env}'! "
                "Refusing to start."
            )
        if (
            secret in INSECURE_SECRET_KEYS
            or "change-me" in secret.lower()
            or len(secret) < 32
        ):
            raise ValueError(
                f"CRITICAL SECURITY CONFIGURATION ERROR: Insecure or default SECRET_KEY detected in "
                f"non-development environment '{env}'! "
                "A secure, cryptographically random key of at least 32 characters must be configured."
            )
    else:
        if secret in INSECURE_SECRET_KEYS or "change-me" in secret.lower():
            logger.warning(
                "SECURITY WARNING: Using default/insecure SECRET_KEY in '%s' environment. "
                "Do NOT use this key in production!",
                env or "development",
            )


class Settings(BaseSettings):
    """Application settings loaded from environment variables and backend/.env."""

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "Intelligent Business Assistant"
    ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    DATABASE_URL: str = _DEFAULT_DATABASE_URL

    SECRET_KEY: str = Field(default="change-me-super-secret")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    REDIS_URL: str | None = None
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60

    OPENROUTER_KEY: str | None = None
    OPENROUTER_URL: str = "https://api.openrouter.ai"
    DEEPSEEK_API_KEY: str | None = None
    DEEPSEEK_URL: str = "https://api.deepseek.ai"

    WORKFLOW_DIR: str = str(_DEFAULT_WORKFLOW_DIR)
    WORKFLOW_STATE_DIR: str = str(_DEFAULT_WORKFLOW_STATE_DIR)
    ALLOWED_ORIGINS: Any = Field(
        default_factory=lambda: list(_DEFAULT_ALLOWED_ORIGINS)
    )

    CHROMA_DIR: str = str(_DEFAULT_CHROMA_DIR)
    CHROMA_API_KEY: str | None = None
    EMBEDDING_MODEL: str = "deeps-embed-1"

    MODEL_PREFERENCES: Any = Field(
        default_factory=lambda: ["openrouter", "deepseek"]
    )
    LLM_DEFAULT_PROVIDER: str = "openrouter"

    ADMIN_EMAIL: str | None = None
    ADMIN_PASSWORD: str | None = None
    TEST_EMAIL: str | None = None
    TEST_PASSWORD: str | None = None

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, value: Any) -> list[str]:
        if value in (None, "", []):
            return list(_DEFAULT_ALLOWED_ORIGINS)
        if isinstance(value, list):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            return cleaned or list(_DEFAULT_ALLOWED_ORIGINS)
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return list(_DEFAULT_ALLOWED_ORIGINS)
            if stripped.startswith("[") and stripped.endswith("]"):
                parsed = [
                    item.strip().strip('"').strip("'")
                    for item in stripped[1:-1].split(",")
                ]
                cleaned = [item for item in parsed if item]
                return cleaned or list(_DEFAULT_ALLOWED_ORIGINS)
            cleaned = [item.strip() for item in stripped.split(",") if item.strip()]
            return cleaned or list(_DEFAULT_ALLOWED_ORIGINS)
        raise TypeError("ALLOWED_ORIGINS must be a list or comma-separated string")

    @field_validator("MODEL_PREFERENCES", mode="before")
    @classmethod
    def _parse_model_preferences(cls, value: Any) -> list[str]:
        if value in (None, "", []):
            return ["openrouter", "deepseek"]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        raise TypeError("MODEL_PREFERENCES must be a list or comma-separated string")

    @model_validator(mode="after")
    def _validate_secrets(self) -> Settings:
        validate_security_settings(self)
        return self


settings = Settings()
