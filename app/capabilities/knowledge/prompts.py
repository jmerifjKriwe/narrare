"""The extraction prompt. Knowledge owns its prompt text, per the spec.

The chapter rides behind the kernel source marker, the way a retrieval passage
does: the fake provider reads the marker — and derives its answer from the
passage behind it — while a real provider reads the instruction above it. The
instruction asks for a "JSON array"; that phrase is the part of the contract
that tells the fake which answer shape the prompt wants.

:class:`ParsedEntity` lives here with the vocabulary it is checked against:
the extraction contract's ask and its answer shapes are one thing, and both
the handler (which parses) and the repository (which persists) import them
from here — never from each other.
"""

from typing import NamedTuple

from app.kernel.llm import SOURCE_PREFIX

ENTITY_KINDS = ("character", "place", "thing")


class ParsedEntity(NamedTuple):
    """One entity of a provider answer, already validated."""

    name: str
    kind: str
    description: str | None


def extraction_prompt(*, chapter_title: str, body: str) -> str:
    kinds = "|".join(ENTITY_KINDS)
    return (
        "Extract the entities that appear in the chapter below: the characters, "
        "the places and the things that matter to the story. For each one judge "
        f"a kind — {kinds} — and write a one-sentence description of its role. "
        'Answer with a JSON array of objects {"name": string, "kind": string, '
        '"description": string} and nothing else: no prose around it, no '
        "commentary. An empty array is a valid answer when the chapter proposes "
        "no entity.\n\n"
        f"Chapter: {chapter_title}\n"
        f"Text:\n{SOURCE_PREFIX}{body}\n"
    )
