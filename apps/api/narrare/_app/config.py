"""
Application configuration via pydantic-settings.

All configuration comes from environment variables or .env file.
Never hardcode secrets — always use these settings classes.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Berechnet den Pfad zum Projekt-Root (/workspace)
# Geht von apps/api/narrare/_app/config.py fünf Ebenen hoch
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Nutzt den absoluten Pfad zur .env Datei
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---------------------------------------------------------------------------
    # Application
    # ---------------------------------------------------------------------------
    environment: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    log_file: str | None = None
    secret_key: str = Field(
        default="dev-secret-key-change-in-production-min-32-chars",
        min_length=32,
    )

    # ---------------------------------------------------------------------------
    # Database
    # ---------------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://narrare:narrare@localhost:5432/narrare_dev"
    )
    test_database_url: str = Field(
        default="postgresql+asyncpg://narrare:narrare@localhost:5433/narrare_test"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # ---------------------------------------------------------------------------
    # Redis
    # ---------------------------------------------------------------------------
    redis_url: str = "redis://localhost:6379/0"

    # ---------------------------------------------------------------------------
    # Observability (OpenTelemetry)
    # ---------------------------------------------------------------------------
    otel_enabled: bool = False
    otel_endpoint: str = ""

    # ---------------------------------------------------------------------------
    # Auth
    # ---------------------------------------------------------------------------
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # ---------------------------------------------------------------------------
    # Encryption
    # ---------------------------------------------------------------------------
    encryption_key: str = Field(default="", alias="NARRARE_ENCRYPTION_KEY")

    # ---------------------------------------------------------------------------
    # Default models (override per-project in .narrare/config.yaml)
    # ---------------------------------------------------------------------------
    default_writing_model: str = "claude-sonnet-4-5-20251020"
    default_analysis_model: str = "claude-haiku-3-5-20241022"
    default_embedding_model: str = "text-embedding-3-small"

    # ---------------------------------------------------------------------------
    # Memory (mem0)
    # ---------------------------------------------------------------------------
    memory_llm_model: str = "gpt-4o-mini"
    memory_embedding_model: str = "text-embedding-3-small"

    # ---------------------------------------------------------------------------
    # Email
    # ---------------------------------------------------------------------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@narrare.local"

    # ---------------------------------------------------------------------------
    # Dev
    # ---------------------------------------------------------------------------
    dev_user_email: str = "dev@narrare.dev"
    dev_user_password: str = "narrare-dev"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @property
    def is_test(self) -> bool:
        return self.environment == "test"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def active_database_url(self) -> str:
        """Return test DB URL in test environment."""
        if self.is_test:
            return self.test_database_url
        return self.database_url


@lru_cache
def get_settings() -> Settings:
    """
    Return cached application settings.

    Use as FastAPI dependency: Depends(get_settings)
    """
    return Settings()
