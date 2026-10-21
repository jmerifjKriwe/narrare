"""The embedding boundary: what an entry offers.

The width is not part of the contract: the column stores any width, because
which model a user picks is not knowable in advance. What the contract demands
instead is consistency — one vector per text, in order — and the corpus guard
(kernel/retrieval) keeps one knowledge base to one model.
"""

from collections.abc import Sequence  # noqa: TC003
from typing import Protocol


class EmbeddingProvider(Protocol):
    """What every entry offers, real or fake."""

    def describe(self) -> str:
        """One line for the startup log, naming what is configured."""
        ...

    def configuration_problems(self) -> list[str]:
        """What this entry needs but does not have; empty when it is ready."""
        ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector per text, in the same order, all of one width."""
        ...
