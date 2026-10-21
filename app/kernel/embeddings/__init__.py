"""The embedding boundary: a catalog of entries, picked by configuration.

Same shape as the text boundary in ``app/kernel/llm/``. Adding an entry is one
line here, plus one fetch strategy module when the vendor speaks a new API
shape. ``NARRE_EMBEDDING_PROVIDER`` selects it and defaults to ``fake``, so a
fresh clone runs without a key.

The width is not a preference: the ``chunks`` column was created at
``SCHEMA_DIMENSIONS``, so an entry has to produce exactly that many numbers.
"""

from collections.abc import Callable  # noqa: TC003
from os import environ

from app.kernel.embeddings.contract import (
    SCHEMA_DIMENSIONS,
    EmbeddingProvider,
    EmbeddingSettings,
)
from app.kernel.embeddings.fake import FakeEmbeddingProvider
from app.kernel.embeddings.openai_compat import OpenAICompatibleEmbeddingProvider

EMBEDDING_PROVIDERS: dict[str, Callable[[], EmbeddingProvider]] = {
    "fake": FakeEmbeddingProvider,
    "openai-compatible": OpenAICompatibleEmbeddingProvider.from_environment,
}

__all__ = [
    "EMBEDDING_PROVIDERS",
    "SCHEMA_DIMENSIONS",
    "EmbeddingProvider",
    "EmbeddingSettings",
    "FakeEmbeddingProvider",
    "get_embedding_provider",
]


def get_embedding_provider() -> EmbeddingProvider:
    """FastAPI dependency: the configured embedding provider."""
    name = environ.get("NARRE_EMBEDDING_PROVIDER", "fake")
    if name not in EMBEDDING_PROVIDERS:
        raise RuntimeError(
            f"unknown embedding provider {name!r}; known: {', '.join(sorted(EMBEDDING_PROVIDERS))}"
        )
    return EMBEDDING_PROVIDERS[name]()
