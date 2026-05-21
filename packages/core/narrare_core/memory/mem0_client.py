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

from typing import Any

import structlog

from narrare_core.memory.embedding_cascade import EmbeddingCascadeResolver

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

WRITING_PREFERENCE_EXTRACTION_PROMPT = (
    "Extract writing preferences from the user's interactions with AI suggestions. "
    "Focus on: sentence length preferences, tone/mood preferences, vocabulary level, "
    "narrative perspective choices, pacing preferences, dialogue style, descriptive density, "
    "genre-specific conventions the user follows or avoids, and any patterns in what they "
    "accept vs reject vs modify. Store these as factual preferences."
)
"""Custom instructions for mem0's memory extraction.

Tells the mem0 extraction LLM to focus on writing-relevant preferences
rather than generic fact extraction.
"""


def _default_memory_model(provider: str) -> str:
    """Return the default memory model for a given LLM provider.

    Falls back to ``_FALLBACK_MODEL`` when the provider is not in
    the known mapping.
    """
    return _PROVIDER_DEFAULT_MODELS.get(provider, _FALLBACK_MODEL)


class NullMemoryClient:
    """No-op memory client used when mem0 is unavailable.

    Every method logs a warning and returns empty results so callers
    never need to handle ``None`` or missing client state.
    """

    async def add(self, **kwargs: Any) -> dict[str, list[Any]]:
        """No-op add — logs warning and returns empty results."""
        logger.warning("mem0_unavailable", method="add")
        return {"results": [], "relations": []}

    async def search(self, **kwargs: Any) -> dict[str, list[Any]]:
        """No-op search — logs warning and returns empty results."""
        logger.warning("mem0_unavailable", method="search")
        return {"results": []}

    async def get_all(self, **kwargs: Any) -> dict[str, list[Any]]:
        """No-op get_all — logs warning and returns empty results."""
        logger.warning("mem0_unavailable", method="get_all")
        return {"results": []}

    async def delete(self, **kwargs: Any) -> dict[str, list[Any]]:
        """No-op delete — logs warning and returns empty results."""
        logger.warning("mem0_unavailable", method="delete")
        return {"results": []}

    async def delete_all(self, **kwargs: Any) -> dict[str, list[Any]]:
        """No-op delete_all — logs warning and returns empty results."""
        logger.warning("mem0_unavailable", method="delete_all")
        return {"results": []}


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
        ``WRITING_PREFERENCE_EXTRACTION_PROMPT``.
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

    # Tier 4: Disabled — return NullMemoryClient
    if embedding_config.provider == "disabled":
        logger.info("mem0_embeddings_disabled", reason="embedding_provider=disabled")
        return NullMemoryClient()

    model = memory_model or _default_memory_model(provider)
    extraction_prompt = custom_instructions or WRITING_PREFERENCE_EXTRACTION_PROMPT

    try:
        from mem0 import (  # type: ignore[import-untyped,reportMissingTypeStubs]
            AsyncMemory,  # type: ignore[reportUnknownVariableType]  # narrare: allow-mem0-import  reason="RULE-08: mem0 adapter location"
        )
    except ImportError:
        logger.warning(
            "mem0_not_installed",
            message="mem0 package not found — using NullMemoryClient",
        )
        return NullMemoryClient()

    try:
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
            "custom_instructions": extraction_prompt,
        }
        if vector_store_config:
            config["vector_store"] = vector_store_config

        client = AsyncMemory.from_config(config_dict=config)  # type: ignore[reportUnknownVariableType,reportUnknownMemberType]
        logger.info(
            "mem0_client_created",
            provider=provider,
            model=model,
            embedding_provider=embedding_config.provider,
            embedding_model=embedding_config.model,
        )
        return client  # type: ignore[reportUnknownVariableType]
    except Exception:
        logger.exception(
            "mem0_client_creation_failed",
            provider=provider,
            model=model,
        )
        return NullMemoryClient()
