"""Application Settings model — pydantic-settings configuration.

Extracted from ``config.py`` for RULE-04 modularisation.
All configuration comes from environment variables or .env file.
Never hardcode secrets — always use these settings classes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Compute path to project root.
# From apps/api/narrare/_app/settings_model.py, go up 5 levels.
BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
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
    # Invocation Evidence (ADR-042)
    # ---------------------------------------------------------------------------
    use_persistent_evidence: bool = Field(
        default=False,
        alias="NARRARE_USE_PERSISTENT_EVIDENCE",
    )
    """Select the production PostgreSQL evidence sink when ``True``.

    When enabled, the InvocationPipeline records each
    ``FeatureInvocationEvidence`` to the ``invocation_evidence`` table via
    ``PersistentEvidenceSink``. When disabled (default), the pipeline uses the
    ephemeral ``LoggingEvidenceSink`` and dev/test environments are unaffected.
    See ADR-042 § Wiring in Production.
    """

    # ---------------------------------------------------------------------------
    # Auth
    # ---------------------------------------------------------------------------
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30

    # NOTE (ADR-071): ``NARRARE_ENCRYPTION_KEY`` and ``DEFAULT_EMBEDDING_MODEL``
    # are owned by ``CoreSettings`` (packages/core/narrare_core/settings.py) —
    # the single source of truth for env-var-backed Core config. Read them via
    # ``get_core_settings()`` and do NOT re-add them here (duplicate source of
    # truth). The API lifespan no longer bridges the encryption key into
    # ``os.environ``; ``core/crypto.py`` reads CoreSettings directly.

    # ---------------------------------------------------------------------------
    # Default models (override per-project in .narrare/config.yaml)
    # ---------------------------------------------------------------------------
    default_writing_model: str = "claude-sonnet-4-5-20251020"
    default_analysis_model: str = "claude-haiku-3-5-20241022"

    # ---------------------------------------------------------------------------
    # Memory (mem0)
    # ---------------------------------------------------------------------------
    memory_llm_model: str = "gpt-4o-mini"
    memory_embedding_model: str = "text-embedding-3-small"

    # ---------------------------------------------------------------------------
    # Token Limits (Operator-Config)
    # ---------------------------------------------------------------------------
    default_max_tokens: int = Field(
        default=4096,
        alias="NARRARE_DEFAULT_MAX_TOKENS",
    )
    """Default output token limit for LLM calls.
    Used as fallback when no token_limit_profile is set.
    """

    # ---------------------------------------------------------------------------
    # WebSocket
    # ---------------------------------------------------------------------------
    ws_idle_timeout_seconds: int = Field(
        default=1800,
        alias="NARRARE_WS_IDLE_TIMEOUT_SECONDS",
    )
    """WebSocket connection idle timeout in seconds (default: 30 min)."""

    # NOTE (ADR-060): operator-level LLM transport retry is NO LONGER a
    # token-limits / app-Settings concern. It is governed at the provider layer
    # (``packages/core/narrare_core/llm/_providers/``) via the operator env
    # ``NARRARE_LLM_TRANSPORT_MAX_RETRIES``. The former ``retry_max_attempts`` /
    # ``retry_base_delay`` app-Settings fields (envs ``NARRARE_RETRY_*``) were a
    # false control with no runtime consumer and have been removed. Do not
    # re-add per-user/project retry here — see ADR-060 (RULE-18b).

    # ---------------------------------------------------------------------------
    # Consistency Token Limits (Operator-Config)
    # ---------------------------------------------------------------------------
    consistency_max_chapter_tokens: int = Field(
        default=2000,
        alias="NARRARE_CONSISTENCY_MAX_CHAPTER_TOKENS",
    )
    """Maximum tokens per chapter preview in consistency checks."""

    consistency_max_kb_entries: int = Field(
        default=100,
        alias="NARRARE_CONSISTENCY_MAX_KB_ENTRIES",
    )
    """Maximum KB entries to include in consistency context."""

    # ---------------------------------------------------------------------------
    # Co-Author Selection Limits (Operator-Config)
    # ---------------------------------------------------------------------------
    default_max_selection_words: int = Field(
        default=2000,
        alias="NARRARE_DEFAULT_MAX_SELECTION_WORDS",
    )
    """Default maximum word count for co-author selection text."""

    # ---------------------------------------------------------------------------
    # Prompt History Retention (Operator-Config) — CR-AUFG-07-19
    # ---------------------------------------------------------------------------
    prompt_history_retention_limit: int = Field(
        default=100,
        ge=1,
        alias="NARRARE_PROMPT_HISTORY_RETENTION_LIMIT",
    )
    """Maximum prompt override revisions kept per (prompt_id, scope)."""

    # ---------------------------------------------------------------------------
    # Cost Estimation (optional override)
    # ---------------------------------------------------------------------------
    cost_rates_json: str = Field(
        default="",
        alias="NARRARE_COST_RATES_JSON",
    )
    """JSON string with per-provider cost rates.
    Format: '{"openai": [10.0, 30.0], "anthropic": [8.0, 24.0]}'
    Input rate, Output rate per 1M tokens.
    Empty string = use code defaults.
    """

    # ---------------------------------------------------------------------------
    # Email
    # ---------------------------------------------------------------------------
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = "noreply@narrare.local"

    # ---------------------------------------------------------------------------
    # CSRF Origin Validation (AUFG-05-13)
    # ---------------------------------------------------------------------------
    csrf_trusted_origins: list[str] = Field(
        default=["http://localhost:3000"],
        alias="NARRARE_CSRF_TRUSTED_ORIGINS",
    )
    """Trusted origins for CSRF Origin/Referer validation (defense-in-depth).

    JSON-serialized list of origin strings.  Set via env var:
    ``NARRARE_CSRF_TRUSTED_ORIGINS='["https://narrare.example.com"]'``
    Defaults to ``["http://localhost:3000"]`` for local development.
    """

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
