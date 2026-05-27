"""
Embedding provider abstraction — Protocol, implementations, and registry.

This module is an approved RULE-01 exception: it imports the OpenAI client
directly because the batch embedding API requires direct client access for
performance (the pydantic-ai agent abstraction does not expose batch embedding).

See: pyproject.toml [tool.narrare.architecture.exceptions]
See: ADR-020

# narrare: allow-direct-llm  reason="Batch embedding API needs direct client for performance"
"""

from __future__ import annotations

import os
import time
from typing import Protocol, runtime_checkable

import openai
import structlog

from narrare_core.shared.errors import EmbeddingError

logger = structlog.get_logger(__name__)

_BATCH_SIZE = 100  # OpenAI recommended batch size

# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for text embedding providers.

    All embedding providers must implement :meth:`embed_texts` and expose
    ``default_model`` and ``default_dimension`` properties.

    This is a ``@runtime_checkable`` protocol — use ``isinstance(obj, EmbeddingProvider)``
    for runtime type checks.
    """

    @property
    def default_model(self) -> str:
        """The default model identifier for this provider (e.g. ``"text-embedding-3-small"``)."""
        ...

    @property
    def default_dimension(self) -> int:
        """The default embedding vector dimension (e.g. ``1536``)."""
        ...

    async def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings for a list of text strings.

        Args:
            texts: List of text strings to embed. Empty strings are skipped
                and return zero vectors of the correct dimension.
            model: Optional model override. Uses :attr:`default_model` when ``None``.

        Returns:
            List of embedding vectors, one per input text. Empty texts return
            zero vectors of :attr:`default_dimension`.

        Raises:
            EmbeddingError: If the embedding API call fails.
        """
        ...


# ---------------------------------------------------------------------------
# OpenAI implementation
# ---------------------------------------------------------------------------


class OpenAIEmbeddingProvider:
    """Embedding provider using OpenAI's API.

    Wraps ``openai.AsyncOpenAI`` for batch text embedding. Supports empty
    string handling, batched requests (size 100), and ``OpenAIError`` wrapping.

    Configurable via the ``DEFAULT_EMBEDDING_MODEL`` environment variable,
    and accepts an optional pre-configured ``AsyncOpenAI`` client for testing
    or custom configuration.

    Attributes:
        default_model: Default model identifier (``"text-embedding-3-small"``).
        default_dimension: Default vector dimension (``1536``).
    """

    default_model = "text-embedding-3-small"
    default_dimension = 1536

    def __init__(self, *, client: openai.AsyncOpenAI | None = None) -> None:
        """Initialise the OpenAI embedding provider.

        Args:
            client: Optional pre-configured ``AsyncOpenAI`` client.
                When omitted, a new client is created on first use.
        """
        self._client = client

    async def embed_texts(
        self,
        texts: list[str],
        *,
        model: str | None = None,
    ) -> list[list[float]]:
        """Generate embeddings using the OpenAI Embeddings API.

        Empty strings are handled without API calls — they return zero vectors
        of :attr:`default_dimension`. Non-empty texts are processed in batches
        of up to :data:`_BATCH_SIZE` (100).

        Args:
            texts: List of text strings to embed. Empty strings are skipped.
            model: Optional model override. Falls back to ``DEFAULT_EMBEDDING_MODEL``
                env var, then :attr:`default_model`.

        Returns:
            List of embedding vectors, one per input text.

        Raises:
            EmbeddingError: If the OpenAI API call fails.
        """
        if not texts:
            return []

        model_name = model or os.environ.get("DEFAULT_EMBEDDING_MODEL", self.default_model)

        # Separate empty strings (return zero vectors) from real texts
        indices_to_embed: list[int] = []
        texts_to_embed: list[str] = []
        for i, text in enumerate(texts):
            if text.strip():
                indices_to_embed.append(i)
                texts_to_embed.append(text)

        if not texts_to_embed:
            # All empty — return zero vectors of the default dimension
            return [[0.0] * self.default_dimension for _ in texts]

        client = self._client or openai.AsyncOpenAI()

        all_embeddings: list[list[float]] = []
        start = time.monotonic()

        try:
            # Process in batches
            for batch_start in range(0, len(texts_to_embed), _BATCH_SIZE):
                batch = texts_to_embed[batch_start : batch_start + _BATCH_SIZE]
                response = await client.embeddings.create(
                    input=batch,
                    model=model_name,
                )
                for item in sorted(response.data, key=lambda x: x.index):
                    all_embeddings.append(item.embedding)

            elapsed = time.monotonic() - start

            logger.info(
                "embeddings_generated",
                count=len(texts_to_embed),
                model=model_name,
                provider="openai",
                duration_ms=round(elapsed * 1000),
            )

        except openai.OpenAIError as e:
            raise EmbeddingError(f"Embedding generation failed: {e}") from e

        # Re-assemble: place real embeddings at their original indices,
        # fill missing (empty text) positions with zero vectors
        dim = len(all_embeddings[0]) if all_embeddings else self.default_dimension
        result: list[list[float]] = [[0.0] * dim for _ in texts]
        for result_idx, orig_idx in enumerate(indices_to_embed):
            result[orig_idx] = all_embeddings[result_idx]

        return result


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_embedding_providers: dict[str, EmbeddingProvider] = {}
_default_key: str | None = None


def register(name: str, provider: EmbeddingProvider, *, default: bool = False) -> None:
    """Register an embedding provider.

    Args:
        name: Provider name (e.g. ``"openai"``, ``"local"``, ``"ollama"``).
        provider: Embedding provider instance.
        default: If ``True``, set as the default provider for module-level
            :func:`embed_texts` calls.

    Raises:
        ValueError: If *name* is empty.
    """
    if not name:
        raise ValueError("Provider name must not be empty")
    _embedding_providers[name] = provider
    if default:
        global _default_key
        _default_key = name


def get(name: str) -> EmbeddingProvider:
    """Retrieve a registered embedding provider by name.

    Args:
        name: Provider name (case-sensitive).

    Returns:
        The registered :class:`EmbeddingProvider` instance.

    Raises:
        KeyError: If *name* is not registered.
    """
    if name not in _embedding_providers:
        available_names = ", ".join(sorted(_embedding_providers.keys()))
        raise KeyError(f"Unknown embedding provider '{name}'. Available: {available_names}.")
    return _embedding_providers[name]


def available() -> list[str]:
    """Return sorted list of registered provider names."""
    return sorted(_embedding_providers.keys())


def get_default() -> str:
    """Return the name of the default embedding provider.

    Returns:
        Provider name registered as default.

    Raises:
        RuntimeError: If no provider has been registered with ``default=True``.
    """
    if _default_key is None:
        raise RuntimeError(
            "No default embedding provider registered. "
            "Call register(name, provider, default=True) first."
        )
    return _default_key


# ---------------------------------------------------------------------------
# Auto-registration
# ---------------------------------------------------------------------------

# Register the OpenAI provider as the default on module import.
# Same pattern as _providers/openai.py — see ADR-020.
register("openai", OpenAIEmbeddingProvider(), default=True)


# ---------------------------------------------------------------------------
# Module-level convenience
# ---------------------------------------------------------------------------


async def embed_texts(
    texts: list[str],
    *,
    model: str | None = None,
    provider: str | None = None,
) -> list[list[float]]:
    """Generate embeddings using the specified or default provider.

    This is a convenience wrapper that resolves the provider by name and
    delegates to its :meth:`EmbeddingProvider.embed_texts` method.

    Args:
        texts: List of text strings to embed.
        model: Optional model override. Passed through to the provider.
        provider: Provider name. Uses the default when ``None``.

    Returns:
        List of embedding vectors, one per input text.

    Raises:
        EmbeddingError: If the embedding API call fails.
        KeyError: If the named *provider* is not registered.
        RuntimeError: If no default provider is configured.
    """
    prov_name = provider or get_default()
    prov = get(prov_name)
    return await prov.embed_texts(texts, model=model)
