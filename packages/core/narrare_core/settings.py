"""CoreSettings — centralised env-var-backed configuration for the Core package.

ADR-071 (Option B): ``CoreSettings(BaseSettings)`` is a standalone
pydantic-settings model that owns all operator-level environment variables the
Core package reads. Core modules read from :func:`get_core_settings` instead of
``os.environ.get`` directly, giving a single typed, validated source of truth.

The API ``Settings`` class remains separate (RULE-07: Core never imports from
``apps/``). The dependency arrow is one-way: ``apps/api`` may call
``get_core_settings``; Core never imports app-level config.

This file has the "Config" role per RULE-06 — settings/constants only, no
business logic, no I/O. See ``docs/architecture/decisions/ADR-071-core-settings.md``.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Compute the project-root ``.env`` path relative to this file.
# From packages/core/narrare_core/settings.py, go up 4 levels to reach the
# project root (mirrors apps/api/narrare/_app/settings_model.py, RULE-07: Core
# never imports BASE_DIR/ENV_FILE from apps/).
_BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
_ENV_FILE = _BASE_DIR / ".env"


class CoreSettings(BaseSettings):
    """Operator-level configuration for the Core package.

    All fields are read from environment variables (or the project-root
    ``.env`` file). Provider API keys are **fallback** values — per-user
    credentials from the database take precedence (ADR-001 factory Protocol
    unchanged).
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Allow construction by field name even though NARRARE_* fields use
        # ``validation_alias`` for env-var discovery (ADR-071 §8 test injection).
        populate_by_name=True,
        # Treat empty env-var values as unset → fall back to defaults. This
        # mirrors ``os.environ.get(VAR, default)`` semantics and prevents
        # crashes on the empty-string placeholders in ``.env.example``
        # (e.g. ``NARRARE_E2E_TEST=`` would otherwise raise a bool-parsing
        # ValidationError at startup).
        env_ignore_empty=True,
    )

    # --- Provider API keys (operator fallback; per-user key from DB wins) ---
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    google_api_key: str | None = None
    gemini_api_key: str | None = None
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    zai_api_key: str | None = None

    # --- Provider base URLs ---
    ollama_base_url: str = "http://localhost:11434"
    openai_base_url: str | None = None
    anthropic_base_url: str | None = None

    # --- NARRARE_* aliases (env var differs from default name uppercasing) ---
    # ``validation_alias`` (not ``alias``) keeps the field name as the constructor
    # parameter (pyright-clean); combined with ``populate_by_name=True`` above,
    # field-name construction works too. Env-var discovery uses the NARRARE_* name.
    encryption_key: str = Field(default="", validation_alias="NARRARE_ENCRYPTION_KEY")
    """Canonical Fernet encryption key source (ADR-071 §5)."""

    llm_transport_max_retries: int = Field(
        default=2, validation_alias="NARRARE_LLM_TRANSPORT_MAX_RETRIES"
    )
    """Governed transport-retry default (ADR-060). Typed mirror only —
    :func:`narrare_core.llm._transport_retry.get_transport_max_retries` remains
    the authoritative accessor with validation and the RULE-18b effect test."""

    # --- Dynamic tier routing pilot (ADR-089) ---
    llm_dynamic_tiering_enabled: bool = Field(
        default=False, validation_alias="NARRARE_LLM_DYNAMIC_TIERING"
    )
    """ADR-089 pilot: opt-in per-step dynamic tier selection (chat path only).

    Default ``False`` — static intent routing stays the shipped behavior;
    the ``SelectModel`` capability is not constructed when off.
    """

    llm_dynamic_tiering_max_prompt_chars: int = Field(
        default=2000, validation_alias="NARRARE_LLM_DYNAMIC_TIERING_MAX_PROMPT_CHARS"
    )
    """Escalate to the capable tier when the latest user prompt exceeds
    this many characters (strictly greater; ADR-089 Decision 3)."""

    llm_dynamic_tiering_min_turns: int = Field(
        default=6, validation_alias="NARRARE_LLM_DYNAMIC_TIERING_MIN_TURNS"
    )
    """Escalate to the capable tier from this user turn onward
    (``turn_count >= min_turns``; ADR-089 Decision 3)."""

    default_embedding_model: str = "text-embedding-3-small"
    """Default embedding model for the pgvector write/search paths (ADR-071 §3).

    Resolved at runtime by the embedding providers, ``EmbeddingService`` /
    ``NoteSearchService`` (read paths), and ``run_embed_source`` (write path).
    Env var: ``DEFAULT_EMBEDDING_MODEL`` (field-name uppercasing, no
    ``NARRARE_`` alias — mirrors the pre-ADR-071 env var).
    """

    default_embedding_dimension: int = 1536
    """Default embedding vector dimension recorded on the write path (P-DIM).

    Metadata stored alongside each vector (``embeddings.dimension`` column) —
    matches the pgvector column width ``vector(1536)`` (migration 0022).
    Env var: ``DEFAULT_EMBEDDING_DIMENSION`` (sibling of
    ``DEFAULT_EMBEDDING_MODEL``). Does NOT govern mem0's internal memory
    embeddings — those follow the memory cascade (ADR-071 §5 keeps
    ``memory_embedding_model`` in API Settings).
    """

    e2e_test: bool = Field(default=False, validation_alias="NARRARE_E2E_TEST")


@lru_cache
def get_core_settings() -> CoreSettings:
    """Return the cached :class:`CoreSettings` singleton.

    Mirrors the established ``get_settings()`` (API) and
    ``get_transport_max_retries()`` (ADR-060) accessor pattern. Tests that need
    to control env vars per-call must call ``get_core_settings.cache_clear()``
    after mutating ``os.environ``.
    """
    return CoreSettings()
