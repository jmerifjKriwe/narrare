"""The fake provider: deterministic prose, so the wire is testable end to end.

It is a catalog entry with the same interface as a real one, not a test branch:
routing, prompt composition, streaming and persistence run the same code
whichever name ``NARRE_LLM_PROVIDER`` selects.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator  # noqa: TC003

from app.kernel.llm.contract import PURPOSE_PREFIX, SOURCE_PREFIX

PURPOSE_EXTRACT = "extract-entities"
PURPOSE_CHECK = "check-consistency"
# Kept in step with the job kinds whose prompts carry the purpose marker
# (knowledge's extraction and consistency checks). A purpose the fake does
# not know gets the default prose, whose shape the handler's parse refuses
# loudly — a drifted kind fails at its first job instead of silently.

PROPOSED_ENTITIES = 3
ENTITY_KINDS = ("character", "place", "thing")
# Kept in step with the extraction contract's vocabulary (knowledge's prompt
# asks for exactly these kinds); the handler's parse refuses anything else, so
# drift here fails loudly at the first extraction instead of silently.

CAPITALIZED = re.compile(r"\b[ÄÖÜA-Z][äöüßa-z]+\b")

# A name paired with a number: the capitalized word, an optional lowercase
# connector word ("Mira ist 34"), then the number. The match is the reading
# as written, which a finding can quote.
WORD_NUMBER = re.compile(r"\b([ÄÖÜA-Z][äöüßa-z]+)(?:\s+[a-zäöüß]+)?\s+(\d+)\b")


def _purpose(prompt: str) -> str | None:
    """The purpose a marked prompt declares; None when no line carries it."""
    for line in prompt.splitlines():
        if line.startswith(PURPOSE_PREFIX):
            return line.removeprefix(PURPOSE_PREFIX).strip()
    return None


def _first_source(prompt: str) -> str | None:
    for line in prompt.splitlines():
        if line.startswith(SOURCE_PREFIX):
            return line.removeprefix(SOURCE_PREFIX)
    return None


def _passages(prompt: str) -> list[str]:
    """Every passage behind a source marker, in order.

    A passage runs from its marker to the next one, not to the next line: a
    chapter body spans lines, so the marker names where a passage starts. A
    multi-passage prompt carries its later headings inside a passage — the
    fake is a stand-in that reads the marked text, not a prompt parser.
    """
    _, *passages = prompt.split(SOURCE_PREFIX)
    return passages


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


def _findings_answer(text: str) -> str:
    """Deterministic consistency check: a name given two numbers contradicts itself.

    A real, small continuity check, not a fixture: the text's (name, number)
    pairs — a capitalized word with an optional connector and a number — are
    grouped by name, and a name carrying two distinct numbers is a
    contradiction: one finding that names the numbers and quotes both
    readings. A test steers the fake with the chapter texts alone.
    """
    # name -> number -> the first reading that carried the pair; dict order
    # keeps first appearance, so the answer is deterministic.
    readings: dict[str, dict[str, str]] = {}
    for match in WORD_NUMBER.finditer(text):
        name = match.group(1)
        number = match.group(2)
        readings.setdefault(name, {}).setdefault(number, match.group(0))
    findings: list[dict[str, str]] = []
    for name, by_number in readings.items():
        if len(by_number) < 2:
            continue
        numbers = list(by_number)
        findings.append(
            {
                "summary": f"{name}: {' vs. '.join(numbers)}",
                "detail": '"' + '" vs. "'.join(by_number.values()) + '"',
            }
        )
    return json.dumps(findings, ensure_ascii=False)


class FakeProvider:
    """Deterministic prose, streamed in pieces, so the wire is visible end to end.

    Three shapes, because the pipeline has three. A prompt without a purpose
    marker keeps the chat behavior: a fixed continuation, or the first marked
    source quoted back (what lets a test see that retrieval reached the model
    boundary). A prompt that declares its purpose gets the answer that purpose
    contracts, derived from the marked passages: extraction proposes entities
    from its passage, the consistency check derives contradictions from every
    one of them.
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
        """Yield deterministic JSON for recognized extraction or check purposes.

        Other prompts yield the first source line in pieces, or CHUNKS when
        that line is absent or empty. JSON answers arrive as a single piece.
        """
        purpose = _purpose(prompt)
        passages = _passages(prompt)
        if purpose == PURPOSE_EXTRACT:
            answer: str | None = _entities_answer("\n".join(passages).strip())
        elif purpose == PURPOSE_CHECK:
            answer = _findings_answer("\n".join(passages))
        else:
            answer = None
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
