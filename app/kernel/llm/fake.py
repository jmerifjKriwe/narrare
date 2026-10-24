"""The fake provider: deterministic prose, so the wire is testable end to end.

It is a catalog entry with the same interface as a real one, not a test branch:
routing, prompt composition, streaming and persistence run the same code
whichever name ``NARRE_LLM_PROVIDER`` selects.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator  # noqa: TC003

from app.kernel.llm.contract import SOURCE_PREFIX

JSON_REQUEST = "JSON array"
"""The phrase an instruction uses to ask for a JSON-array answer. The fake
reads it the way a real provider reads the instruction; the prompt builders
and this fake share it as a literal, the same way they share the marker."""

PROPOSED_ENTITIES = 3
ENTITY_KINDS = ("character", "place", "thing")
# Kept in step with the extraction contract's vocabulary (knowledge's prompt
# asks for exactly these kinds); the handler's parse refuses anything else, so
# drift here fails loudly at the first extraction instead of silently.

CAPITALIZED = re.compile(r"\b[ÄÖÜA-Z][äöüßa-z]+\b")


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


def _entities_answer(passage: str) -> str:
    """Deterministic extraction: the passage's capitalized words as entities.

    Names are derived from the prompt, so a test steers the fake with the
    chapter text alone; kinds cycle the extraction vocabulary in order of
    appearance.
    """
    names = list(dict.fromkeys(CAPITALIZED.findall(passage)))[:PROPOSED_ENTITIES]
    return json.dumps(
        [
            {
                "name": name,
                "kind": ENTITY_KINDS[index % len(ENTITY_KINDS)],
                "description": f"{name} appears in the chapter.",
            }
            for index, name in enumerate(names)
        ],
        ensure_ascii=False,
    )


def _json_answer(prompt: str) -> str | None:
    """The JSON-array answer when the instruction asks for one; None otherwise."""
    head, _separator, passage = prompt.partition(SOURCE_PREFIX)
    if JSON_REQUEST not in head:
        return None
    return _entities_answer(passage.strip())


class FakeProvider:
    """Deterministic prose, streamed in pieces, so the wire is visible end to end.

    Three shapes, because the pipeline has three: a prompt without sources gets
    a fixed continuation; a prompt with sources gets the first one quoted back
    (what lets a test see that retrieval reached the model boundary); and a
    prompt whose instruction asks for a JSON array gets one derived from the
    marked passage — the extraction path, whose names come from the chapter.
    """

    CHUNKS = (
        "Der Nebel hob sich ",
        "vom See und legte sich ",
        "über die Straße.",
    )

    def describe(self) -> str:
        return "fake"

    def configuration_problems(self) -> list[str]:
        return []

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        answer = _json_answer(prompt)
        if answer is not None:
            # One piece is still a stream: the consumer sees the same protocol.
            await asyncio.sleep(0)
            yield answer
            return
        source = _first_source(prompt)
        for chunk in _pieces(source) if source else self.CHUNKS:
            # Yield to the loop between pieces: the server flushes each event
            # instead of collapsing the whole completion into one write.
            await asyncio.sleep(0)
            yield chunk
