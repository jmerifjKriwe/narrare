"""The extraction and consistency prompts. Knowledge owns its prompt text, per the spec.

The chapter rides behind the kernel source marker, the way a retrieval passage
does: the fake provider reads the marker — and derives its answer from the
passage behind it — while a real provider reads the instruction above it. The
purpose marker names which machine-checked answer shape a prompt wants: the
fake branches on the marked line, so the answer shape is declared by the
prompt, not sniffed from its prose.

:class:`ParsedEntity` and :class:`ParsedFinding` live here with the vocabulary
they are checked against: a contract's ask and its answer shapes are one
thing, and both the handler (which parses) and the repository (which persists)
import them from here — never from each other.
"""

from collections.abc import Sequence  # noqa: TC003
from typing import NamedTuple

from app.kernel.contracts.models import ENTITY_TYPES
from app.kernel.llm import PURPOSE_PREFIX, SOURCE_PREFIX

# The most of a chapter body any prompt carries, in characters. A real model
# overflows on a long chapter; the fake never does, which is why the bound has
# its own tests. Characters, not bytes: a writer's é is one character.
BODY_LIMIT = 20_000


class ParsedEntity(NamedTuple):
    """One entity of a provider answer, already validated."""

    name: str
    type: str
    description: str | None


class ParsedFinding(NamedTuple):
    """One finding of a provider answer, already validated."""

    summary: str
    detail: str | None


def extraction_prompt(*, chapter_title: str, body: str) -> str:
    """Build a prompt requesting entity JSON from the chapter's full body.

    The purpose marker selects extraction, and the source marker introduces
    the body for providers that read marked passages.
    """
    types = "|".join(ENTITY_TYPES)
    return (
        f"{PURPOSE_PREFIX}extract-entities\n\n"
        "Extract the entities that appear in the chapter below: the characters, "
        "the places and the things that matter to the story. For each one judge "
        f"a type — {types} — and write a one-sentence description of its role. "
        'Answer with a JSON object containing an "items" array of objects '
        '{"name": string, "type": string, '
        '"description": string} and nothing else: no prose around it, no '
        'commentary. Answer with {"items": []} when the chapter proposes '
        "no entity.\n\n"
        f"Chapter: {chapter_title}\n"
        f"Text:\n{SOURCE_PREFIX}{body}\n"
    )


def consistency_prompt(
    *, entities: Sequence[tuple[str, str]], chapters: Sequence[tuple[str, str]]
) -> str:
    """The whole-novel check: the instruction, the accepted canon, every chapter.

    ``entities`` are (name, type) pairs of the novel's accepted entities — the
    story's canon, grounding what a name refers to. ``chapters`` are (title,
    body) pairs in reading order; each body rides behind the source marker the
    way a retrieval passage does, so the provider boundary sees every chapter
    and a test can steer the fake's derivation with the chapter texts alone.
    """
    grounding = "\n".join(f"{name} ({type_})" for name, type_ in entities)
    if not grounding:
        grounding = "None accepted yet."
    chapters_text = "\n\n".join(
        f"Chapter: {title}\nText:\n{SOURCE_PREFIX}{body}" for title, body in chapters
    )
    return (
        f"{PURPOSE_PREFIX}check-consistency\n\n"
        "Read the chapters below as one story and find where the text contradicts "
        "itself: an age that changes between chapters, a date or a timeline that "
        "cannot hold, a name that drifts, a fact stated one way and later another. "
        "For each contradiction write a short summary and a detail that quotes the "
        'readings that disagree. Answer with a JSON object containing an "items" '
        'array of objects {"summary": '
        'string, "detail": string} and nothing else: no prose around it, no '
        'commentary. Answer with {"items": []} when the chapters agree.\n\n'
        f"The story's accepted entities, as grounding:\n{grounding}\n\n"
        f"{chapters_text}\n"
    )
