"""mem0 AsyncMemory client factory with graceful degradation.

Creates and configures a ``mem0.AsyncMemory`` instance using the
project's LLM provider for the memory model and pgvector for the
vector store. Falls back to ``NullMemoryClient`` when mem0 is not
installed or creation fails.

This module is the ONLY place mem0 is imported (RULE-08).
"""

from __future__ import annotations

from typing import Any

import structlog

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
    embedding_model: str = "text-embedding-3-small",
    embedding_provider: str = "openai",
    embedding_api_key: str | None = None,
    embedding_base_url: str | None = None,
) -> Any:
    """Create a ``mem0.AsyncMemory`` instance, falling back to ``NullMemoryClient``.

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
    embedding_model:
        Embedding model identifier (default: ``"text-embedding-3-small"``).
    embedding_provider:
        Embedding provider name (default: ``"openai"``).
    embedding_api_key:
        API key for the embedding provider (falls back to ``api_key``).
    embedding_base_url:
        Optional custom base URL for the embedding provider.

    Returns
    -------
    Any
        A ``mem0.AsyncMemory`` instance, or ``NullMemoryClient`` on failure.
    """
    model = memory_model or _default_memory_model(provider)
    embed_key = embedding_api_key or api_key

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

        embedder_config: dict[str, Any] = {
            "provider": embedding_provider,
            "config": {
                "model": embedding_model,
                "api_key": embed_key,
            },
        }
        if embedding_base_url:
            embedder_config["config"]["base_url"] = embedding_base_url

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
        }
        if vector_store_config:
            config["vector_store"] = vector_store_config

        client = AsyncMemory.from_config(config_dict=config)  # type: ignore[reportUnknownVariableType,reportUnknownMemberType]
        logger.info(
            "mem0_client_created",
            provider=provider,
            model=model,
            embedding_model=embedding_model,
        )
        return client  # type: ignore[reportUnknownVariableType]
    except Exception:
        logger.exception(
            "mem0_client_creation_failed",
            provider=provider,
            model=model,
        )
        return NullMemoryClient()
