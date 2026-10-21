"""The fake embedding entry: deterministic vectors, no network, no key.

It is honest about what it is: signed feature hashing over the lowercased words.
It matches words, not meaning — enough to prove the real path (chunk, store as
pgvector, order by cosine) without a paid model.
"""

import hashlib
import math
import re
from collections.abc import Sequence  # noqa: TC003

from app.kernel.embeddings.contract import EmbeddingSettings


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

    def describe(self) -> str:
        return "fake"

    def configuration_problems(self) -> list[str]:
        return []

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [_embed(text) for text in texts]
