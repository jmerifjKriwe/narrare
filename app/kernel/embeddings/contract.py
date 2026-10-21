"""The embedding boundary: what an entry offers, and the width it must match.

The vector width is part of the contract with the database: the ``chunks``
column was created at ``SCHEMA_DIMENSIONS``, so a provider that returns anything
else cannot be stored. Changing the width is a migration, and
``validate_configuration`` refuses to let the two drift apart silently.
"""

from collections.abc import Sequence  # noqa: TC003
from os import environ
from typing import Protocol

SCHEMA_DIMENSIONS = 384
"""The width the applied migrations create."""


class EmbeddingSettings:
    """Configuration, not a literal: the database column fixes the dimension, so
    changing this needs a migration as well as an environment change."""

    dimensions = int(environ.get("NARRE_EMBEDDING_DIMENSIONS", str(SCHEMA_DIMENSIONS)))


class EmbeddingProvider(Protocol):
    """What every entry offers, real or fake."""

    dimensions: int

    def describe(self) -> str:
        """One line for the startup log, naming what is configured."""
        ...

    def configuration_problems(self) -> list[str]:
        """What this entry needs but does not have; empty when it is ready."""
        ...

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """One vector per text, in the same order."""
        ...
