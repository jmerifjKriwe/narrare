"""Embedding cascade resolver — 4-tier embedding source resolution.

Tier 1: OpenAI text-embedding-3-small (if user has OpenAI key)
Tier 2: Provider-native embeddings (future hook, not implemented now)
Tier 3: Local sentence-transformers all-MiniLM-L6-v2 (no API key needed)
Tier 4: Disabled — NullMemoryClient (no embeddings)

Resolution order follows user's configured providers.
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EmbeddingConfig:
    """Resolved embedding configuration."""

    provider: str  # "openai" | "local" | "disabled"
    model: str  # model identifier
    api_key: str | None = None
    base_url: str | None = None


class EmbeddingCascadeResolver:
    """Resolves the best available embedding source for a user."""

    def resolve(
        self,
        *,
        user_providers: list[str],
        user_api_keys: dict[str, str],
        user_base_urls: dict[str, str | None],
        explicit_provider: str | None = None,
    ) -> EmbeddingConfig:
        """Resolve embedding config following the cascade.

        Args:
            user_providers: List of provider names the user has configured.
            user_api_keys: Mapping of provider name → API key.
            user_base_urls: Mapping of provider name → base URL (or None).
            explicit_provider: User override ("auto" | "openai" | "local" | "disabled").

        Returns:
            Resolved EmbeddingConfig.
        """
        if explicit_provider and explicit_provider != "auto":
            return self._resolve_explicit(explicit_provider, user_api_keys, user_base_urls)

        # Tier 1: OpenAI embeddings
        if "openai" in user_providers:
            key = user_api_keys.get("openai")
            if key:
                logger.debug("embedding_cascade_tier1", provider="openai")
                return EmbeddingConfig(
                    provider="openai",
                    model="text-embedding-3-small",
                    api_key=key,
                    base_url=user_base_urls.get("openai"),
                )

        # Tier 2: Provider-native (future hook)
        # Not implemented — skip to Tier 3

        # Tier 3: Local sentence-transformers
        logger.debug("embedding_cascade_tier3", provider="local")
        return EmbeddingConfig(
            provider="local",
            model="all-MiniLM-L6-v2",
        )

    def _resolve_explicit(
        self,
        provider: str,
        api_keys: dict[str, str],
        base_urls: dict[str, str | None],
    ) -> EmbeddingConfig:
        """Resolve an explicitly requested embedding provider."""
        if provider == "disabled":
            return EmbeddingConfig(provider="disabled", model="")
        elif provider == "openai":
            key = api_keys.get("openai")
            if not key:
                logger.warning("embedding_openai_no_key", provider=provider)
                return EmbeddingConfig(provider="disabled", model="")
            return EmbeddingConfig(
                provider="openai",
                model="text-embedding-3-small",
                api_key=key,
                base_url=base_urls.get("openai"),
            )
        elif provider == "local":
            return EmbeddingConfig(provider="local", model="all-MiniLM-L6-v2")
        else:
            logger.warning("embedding_unknown_provider", provider=provider)
            return EmbeddingConfig(provider="disabled", model="")
