"""The provider boundary: what an entry offers, real or fake.

One method streams the completion. The other two let the kernel report what a
configured entry is and what it still needs, so a half-configured real provider
fails at startup instead of with the first prompt.
"""

from collections.abc import AsyncIterator  # noqa: TC003
from typing import Protocol

SOURCE_PREFIX = "SOURCE: "
"""A prompt that wants its answer to quote a supplied passage marks it with this
prefix, one passage per line. The fake reads it; a real provider reads the
sentence above it. The marker is a kernel constant because the prompt builder
and the providers must agree on it and live in different trees."""


class TextProvider(Protocol):
    """What every entry offers, real or fake."""

    def describe(self) -> str:
        """One line for the startup log, naming what is configured."""
        ...

    def configuration_problems(self) -> list[str]:
        """What this entry needs but does not have; empty when it is ready."""
        ...

    def stream(self, prompt: str) -> AsyncIterator[str]:
        """Yield the completion in pieces, in order."""
        ...
