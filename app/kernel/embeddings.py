"""The embedding boundary: one method, entries picked by configuration.

Same shape as the text boundary in ``app/kernel/llm.py``. The fake is a catalog
entry, not a test branch, and it is honest about what it is: signed feature
hashing over the lowercased words. It matches words, not meaning — enough to
prove the real path (chunk, store as pgvector, order by cosine) without a paid
model.
"""

import hashlib
import math
import re
from collections.abc import Sequence  # noqa: TC003
from os import environ
from typing import Protocol

SCHEMA_DIMENSIONS = 384
"""The vector width the applied migrations create. ``NARRE_EMBEDDING_DIMENSIONS``
may promise another width for a future deployment, but a running database keeps
its width until a migration changes it — ``validate_configuration`` refuses to
let the two drift apart silently."""


class EmbeddingSettings:
    """Configuration, not a literal: the database column fixes the dimension, so
    changing this needs a migration as well as an environment change."""

    dimensions = int(environ.get("NARRE_EMBEDDING_DIMENSIONS", str(SCHEMA_DIMENSIONS)))


class EmbeddingProvider(Protocol):
    dimensions: int

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector per text, in the same order."""
        ...


def _embed(text: str) -> list[float]:
    vector = [0.0] * EmbeddingSettings.dimensions
    for token in re.findall(r"\w+", text.lower()):
        digest = hashlib.blake2b(token.encode(), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % EmbeddingSettings.dimensions
        vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


class FakeEmbeddingProvider:
    dimensions = EmbeddingSettings.dimensions

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [_embed(text) for text in texts]


EMBEDDING_PROVIDERS = {"fake": FakeEmbeddingProvider}


def get_embedding_provider() -> EmbeddingProvider:
    """FastAPI dependency: the configured embedding provider."""
    name = environ.get("NARRE_EMBEDDING_PROVIDER", "fake")
    if name not in EMBEDDING_PROVIDERS:
        raise RuntimeError(
            f"unknown embedding provider {name!r}; known: {', '.join(sorted(EMBEDDING_PROVIDERS))}"
        )
    return EMBEDDING_PROVIDERS[name]()
