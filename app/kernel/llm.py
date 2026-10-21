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


class FakeProvider:
    """Deterministic prose, three pieces, so streaming is visible end to end."""

    CHUNKS = (
        "Der Nebel hob sich ",
        "vom See und legte sich ",
        "über die Straße.",
    )

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        for chunk in self.CHUNKS:
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
