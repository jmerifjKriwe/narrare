"""The LLM boundary: one interface, entries picked by configuration.

The fake is a normal catalog entry, not a test branch: routing, prompt
composition, streaming and persistence run the same code whichever name is
configured. ``NARRE_LLM_PROVIDER`` selects the entry; it defaults to ``fake``
because no paid provider is wired yet.

pydantic-ai is deliberately absent. One streaming completion over a fixed prompt
needs a single async method; an agent layer would add tools, retries and
structured output that nothing in v2 asks for. Revisit this module if tool use or
agent orchestration appears — not before.
"""

import asyncio
from collections.abc import AsyncIterator  # noqa: TC003
from os import environ
from typing import Protocol


class TextProvider(Protocol):
    """What every entry offers, real or fake."""

    def stream(self, prompt: str) -> AsyncIterator[str]:
        """Yield the completion in pieces, in order."""
        ...


# A prompt that wants its answer to quote a supplied passage marks it with this
# prefix, one passage per line. The fake reads it; a real provider reads the
# sentence above it. The marker is a kernel constant because the prompt builder
# and the fake must agree on it and live in different trees.
SOURCE_PREFIX = "SOURCE: "


def _first_source(prompt: str) -> str | None:
    for line in prompt.splitlines():
        if line.startswith(SOURCE_PREFIX):
            return line.removeprefix(SOURCE_PREFIX)
    return None


def _pieces(text: str) -> tuple[str, ...]:
    """Split into small pieces so the stream stays visible on the wire."""
    words = text.split()
    return tuple(
        " ".join(words[index : index + 4]) + (" " if index + 4 < len(words) else "")
        for index in range(0, len(words), 4)
    )


class FakeProvider:
    """Deterministic prose, streamed in pieces, so the wire is visible end to end.

    Two shapes, because the pipeline has two: a prompt without sources gets a fixed
    continuation; a prompt with sources gets the first one quoted back. The second
    shape is what lets a test see that retrieval reached the model boundary.
    """

    CHUNKS = (
        "Der Nebel hob sich ",
        "vom See und legte sich ",
        "über die Straße.",
    )

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        source = _first_source(prompt)
        for chunk in _pieces(source) if source else self.CHUNKS:
            # Yield to the loop between pieces: the server flushes each event
            # instead of collapsing the whole completion into one write.
            await asyncio.sleep(0)
            yield chunk


PROVIDERS = {"fake": FakeProvider}


def get_provider() -> TextProvider:
    """FastAPI dependency: the configured provider."""
    name = environ.get("NARRE_LLM_PROVIDER", "fake")
    if name not in PROVIDERS:
        raise RuntimeError(f"unknown LLM provider {name!r}; known: {', '.join(sorted(PROVIDERS))}")
    return PROVIDERS[name]()
