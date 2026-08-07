"""mem0 AsyncMemory client factory with embedding cascade and graceful degradation.

Creates and configures a ``mem0.AsyncMemory`` instance using the
project's LLM provider for the memory model and a 4-tier embedding
cascade for the vector store. Falls back to ``NullMemoryClient`` when
mem0 is not installed, embeddings are disabled, or creation fails.

This module is the ONLY place mem0 is imported (RULE-08).

Embedding cascade (resolved by ``EmbeddingCascadeResolver``):
    Tier 1: OpenAI text-embedding-3-small (if user has OpenAI key)
    Tier 2: Provider-native embeddings (future hook)
    Tier 3: Local sentence-transformers all-MiniLM-L6-v2
    Tier 4: Disabled — NullMemoryClient
"""

from __future__ import annotations

from typing import Any, cast

import structlog

from narrare_core.memory._null_client import NullMemoryClient
from narrare_core.memory.embedding_cascade import EmbeddingCascadeResolver
from narrare_core.settings import get_core_settings

logger = structlog.get_logger(__name__)

_PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "anthropic": "claude-haiku-4-20250414",
    "openai": "gpt-4.1-nano",
    "ollama": "llama3.2:3b",
    "zai": "glm-4-flash",
}
"""Default memory models per LLM provider.

These are deliberately small/cheap models — mem0 uses them for
internal operations like memory extraction, not for user-facing generation.
"""

_FALLBACK_MODEL: str = "gpt-4.1-nano"
"""Model used when the provider is unknown."""

# narrare: allow-prompt-path reason="mem0 config string, not Narrare prompt path (ADR-064)"
_WRITING_PREFERENCE_PROMPTS: dict[str, str] = {
    "en": (
        "Extract writing preferences from the user's interactions with AI suggestions. "
        "Focus on: sentence length preferences, tone/mood preferences, vocabulary level, "
        "narrative perspective choices, pacing preferences, dialogue style, descriptive density, "
        "genre-specific conventions the user follows or avoids, and any patterns in what they "
        "accept vs reject vs modify. Store these as factual preferences."
    ),
    "de": (
        "Extrahiere Schreibpräferenzen aus den Interaktionen des Nutzers mit KI-Vorschlägen. "
        "Konzentriere dich auf: Satzlängenpräferenzen, Ton-/Stimmungspräferenzen, "
        "Wortschatzniveau, Erzählperspektiven-Wahl, Tempo-Präferenzen, Dialogstil, "
        "Beschreibungsdichte, genrespezifische Konventionen, denen der Nutzer folgt "
        "oder die er vermeidet, sowie Muster darin, was er akzeptiert, ablehnt oder "
        "modifiziert. Speichere diese als faktische Präferenzen."
    ),
    "fr": (
        "Extrait les préférences d'écriture des interactions de l'utilisateur "
        "avec les suggestions IA. Concentre-toi sur : les préférences de longueur "
        "de phrase, les préférences de ton/humeur, le niveau de vocabulaire, "
        "les choix de perspective narrative, les préférences de rythme, le style "
        "de dialogue, la densité descriptive, les conventions spécifiques au genre "
        "que l'utilisateur suit ou évite, et les tendances dans ce qu'il accepte, "
        "rejette ou modifie. Stocke ces informations comme des préférences factuelles."
    ),
}
"""Language-specific extraction prompts for mem0's memory extraction.

Each prompt tells the mem0 extraction LLM to focus on writing-relevant
preferences in the appropriate language for better extraction quality.
"""

WRITING_PREFERENCE_EXTRACTION_PROMPT = _WRITING_PREFERENCE_PROMPTS["en"]
"""Default (English) extraction prompt.

Kept as a module-level constant for backward compatibility with callers
that import it directly. Prefer ``get_extraction_prompt()`` for new code.
"""


def get_extraction_prompt(language: str = "en") -> str:
    """Return the writing preference extraction prompt in the given language.

    Falls back to English for unsupported languages.
    """
    return _WRITING_PREFERENCE_PROMPTS.get(language, _WRITING_PREFERENCE_PROMPTS["en"])


def _default_memory_model(provider: str) -> str:
    """Return the default memory model for a given LLM provider.

    Falls back to ``_FALLBACK_MODEL`` when the provider is not in
    the known mapping.
    """
    return _PROVIDER_DEFAULT_MODELS.get(provider, _FALLBACK_MODEL)


def _build_mem0_config(
    *,
    provider: str,
    api_key: str,
    base_url: str | None = None,
    memory_model: str | None = None,
    db_url: str = "",
    user_providers: list[str] | None = None,
    user_api_keys: dict[str, str] | None = None,
    user_base_urls: dict[str, str | None] | None = None,
    embedding_provider: str = "auto",
    custom_instructions: str | None = None,
    language: str = "en",
    # Legacy params (kept for backward compatibility, used as fallback)
    embedding_model: str | None = None,
    embedding_api_key: str | None = None,
    embedding_base_url: str | None = None,
) -> dict[str, Any] | None:
    """Build mem0 config dict synchronously. Returns None if embeddings disabled.

    Extracted from ``create_memory_client()`` for reuse in synchronous
    DI contexts (e.g. ``create_memory_client_sync()``). Contains only
    config-building logic — no mem0 imports, no client instantiation.
    """
    # Resolve embedding config via cascade
    providers = user_providers or [provider]
    keys = dict(user_api_keys or {})
    if provider not in keys:
        keys[provider] = api_key
    urls = dict(user_base_urls or {})

    resolver = EmbeddingCascadeResolver()
    embedding_config = resolver.resolve(
        user_providers=providers,
        user_api_keys=keys,
        user_base_urls=urls,
        explicit_provider=embedding_provider,
    )

    # Tier 4: Disabled — return None
    if embedding_config.provider == "disabled":
        return None

    model = memory_model or _default_memory_model(provider)
    # narrare: allow-prompt-path reason="mem0 config string, not Narrare prompt path (ADR-064)"
    extraction_prompt = custom_instructions or get_extraction_prompt(language)

    llm_config: dict[str, Any] = {
        "model": model,
        "api_key": api_key,
    }
    if base_url:
        llm_config["base_url"] = base_url

    # Build embedder config from resolved cascade result
    # Legacy params override cascade result if provided
    if embedding_model or embedding_api_key or embedding_base_url:
        embedder_config: dict[str, Any] = {
            "provider": "openai",
            "config": {
                "model": embedding_model or embedding_config.model,
                "api_key": embedding_api_key or embedding_config.api_key or api_key,
            },
        }
        if embedding_base_url:
            embedder_config["config"]["base_url"] = embedding_base_url
    elif embedding_config.provider == "local":
        # Tier 3: Local sentence-transformers via HuggingFace provider
        embedder_config = {
            "provider": "huggingface",
            "config": {
                "model": embedding_config.model,
            },
        }
    else:
        # Tier 1: OpenAI embeddings
        embedder_config = {
            "provider": "openai",
            "config": {
                "model": embedding_config.model,
                "api_key": embedding_config.api_key,
            },
        }
        if embedding_config.base_url:
            embedder_config["config"]["base_url"] = embedding_config.base_url

    vector_store_config: dict[str, Any] = {}
    if db_url:
        vector_store_config = {
            "provider": "pgvector",
            "config": {
                "dbname": db_url,
            },
        }

    config: dict[str, Any] = {
        "llm": llm_config,
        "embedder": embedder_config,
        # narrare: allow-prompt-path reason="mem0 config string, not Narrare prompt path (ADR-064)"
        "custom_instructions": extraction_prompt,
    }
    if vector_store_config:
        config["vector_store"] = vector_store_config

    return config


async def create_memory_client(
    *,
    provider: str,
    api_key: str,
    base_url: str | None = None,
    memory_model: str | None = None,
    db_url: str = "",
    user_providers: list[str] | None = None,
    user_api_keys: dict[str, str] | None = None,
    user_base_urls: dict[str, str | None] | None = None,
    embedding_provider: str = "auto",
    custom_instructions: str | None = None,
    language: str = "en",
    # Legacy params (kept for backward compatibility, used as fallback)
    embedding_model: str | None = None,
    embedding_api_key: str | None = None,
    embedding_base_url: str | None = None,
) -> Any:
    """Create a ``mem0.AsyncMemory`` instance, falling back to ``NullMemoryClient``.

    Uses the ``EmbeddingCascadeResolver`` to determine the best available
    embedding source. When ``embedding_provider="disabled"``, returns
    ``NullMemoryClient`` immediately.

    Returns ``Any`` because mem0 may not be installed — callers should
    not rely on a specific type from the mem0 package.

    Parameters
    ----------
    provider:
        LLM provider name (e.g. ``"openai"``, ``"anthropic"``).
    api_key:
        API key for the LLM provider.
    base_url:
        Optional custom base URL for the LLM provider.
    memory_model:
        Override the default memory model. When ``None``, the default
        for the provider is looked up from ``_PROVIDER_DEFAULT_MODELS``.
    db_url:
        PostgreSQL connection string for pgvector vector store.
    user_providers:
        List of provider names the user has configured (for cascade).
    user_api_keys:
        Mapping of provider name → API key (for cascade).
    user_base_urls:
        Mapping of provider name → base URL (for cascade).
    embedding_provider:
        Embedding provider override: ``"auto"`` (default), ``"openai"``,
        ``"local"``, or ``"disabled"``.
    custom_instructions:
        Custom extraction prompt for mem0. When ``None``, uses
        ``get_extraction_prompt(language)``.
    language:
        Language code for the extraction prompt (e.g. ``"en"``, ``"de"``,
        ``"fr"``). Defaults to ``"en"``. Ignored when ``custom_instructions``
        is provided.
    embedding_model:
        Legacy: explicit embedding model name. Overrides cascade result.
    embedding_api_key:
        Legacy: explicit embedding API key. Overrides cascade result.
    embedding_base_url:
        Legacy: explicit embedding base URL. Overrides cascade result.

    Returns
    -------
    Any
        A ``mem0.AsyncMemory`` instance, or ``NullMemoryClient`` on failure.
    """
    # E2E test mode: return NullMemoryClient before configuring OpenAI.
    # mem0 manages its own embedder (configured below) which does NOT go
    # through narrare_core.llm.embedding_providers — so the TestEmbeddingProvider
    # override does not cover it. mem0's config validator/EmbedderFactory reject
    # a "mock" provider (only the internal upstash_vector special-case returns
    # MockEmbeddings), so the clean E2E stub is NullMemoryClient (the existing
    # Tier 4 graceful-degradation mechanism). Same switch TestModel uses.
    if get_core_settings().e2e_test:
        logger.info("mem0_e2e_test_mode", reason="NARRARE_E2E_TEST set — NullMemoryClient")
        return NullMemoryClient()

    config = _build_mem0_config(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        memory_model=memory_model,
        db_url=db_url,
        user_providers=user_providers,
        user_api_keys=user_api_keys,
        user_base_urls=user_base_urls,
        embedding_provider=embedding_provider,
        custom_instructions=custom_instructions,
        language=language,
        embedding_model=embedding_model,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
    )

    if config is None:
        logger.info("mem0_embeddings_disabled", reason="embedding_provider=disabled")
        return NullMemoryClient()

    try:
        from mem0 import (  # pyright: ignore[reportMissingTypeStubs,reportMissingImports]
            AsyncMemory,  # type: ignore[import-untyped,reportMissingTypeStubs]  # reason: mem0 has no type stubs (RULE-08: mem0 adapter location)
        )
    except ImportError:
        logger.warning(
            "mem0_not_installed",
            message="mem0 package not found — using NullMemoryClient",
        )
        return NullMemoryClient()

    try:
        client = cast("Any", AsyncMemory).from_config(config_dict=config)
        logger.info(
            "mem0_client_created",
            provider=provider,
            embedding_provider=config.get("embedder", {}).get("provider"),
        )
        return client
    except Exception:
        logger.exception(
            "mem0_client_creation_failed",
            provider=provider,
        )
        return NullMemoryClient()


def create_memory_client_sync(
    *,
    provider: str,
    api_key: str,
    base_url: str | None = None,
    memory_model: str | None = None,
    db_url: str = "",
    embedding_provider: str = "auto",
    language: str = "en",
    embedding_model: str | None = None,
    embedding_api_key: str | None = None,
    embedding_base_url: str | None = None,
) -> Any:
    """Synchronous factory for mem0 AsyncMemory (for sync DI init).

    Same config logic as ``create_memory_client()`` but synchronous.
    Uses ``_build_mem0_config()`` internally and returns
    ``NullMemoryClient`` on failure. Intended for module-level DI
    wiring where async is not available.

    Returns ``Any`` because mem0 may not be installed — callers should
    not rely on a specific type from the mem0 package.
    """
    # E2E test mode: see create_memory_client() for rationale.
    if get_core_settings().e2e_test:
        logger.info("mem0_e2e_test_mode_sync", reason="NARRARE_E2E_TEST set — NullMemoryClient")
        return NullMemoryClient()

    config = _build_mem0_config(
        provider=provider,
        api_key=api_key,
        base_url=base_url,
        memory_model=memory_model,
        db_url=db_url,
        embedding_provider=embedding_provider,
        language=language,
        embedding_model=embedding_model,
        embedding_api_key=embedding_api_key,
        embedding_base_url=embedding_base_url,
    )

    if config is None:
        logger.info("mem0_embeddings_disabled_sync", reason="embedding_provider=disabled")
        return NullMemoryClient()

    try:
        from mem0 import (  # pyright: ignore[reportMissingTypeStubs,reportMissingImports]
            AsyncMemory,  # type: ignore[import-untyped,reportMissingTypeStubs]  # reason: mem0 has no type stubs (RULE-08: mem0 adapter location)
        )
    except ImportError:
        logger.warning("mem0_not_installed_sync")
        return NullMemoryClient()

    try:
        client = cast("Any", AsyncMemory).from_config(config_dict=config)
        logger.info("mem0_client_created_sync", provider=provider)
        return client
    except Exception:
        logger.exception("mem0_client_creation_failed_sync", provider=provider)
        return NullMemoryClient()
