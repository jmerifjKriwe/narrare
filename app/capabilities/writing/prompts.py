"""The budgeted continuation prompt. Writing owns its prompt text, per the spec.

The context a continuation carries is assembled from the four named slices the
kernel allocator sized (`app.kernel.context`): the chapter tail, the entities
the tail names, the previous chapters' tails and the novel's style hints — each
hard-cut to its slice, scaffolding included, so a slice never overflows. A
slice whose floor is zero is omitted at assembly; nothing rides free.

The packers fill, the template arranges (the B docking): the three optional
sections arrive pre-packed within their slices as opaque strings, and the
template owns order, glue and instruction. The bundled arrangement is
`CONTINUATION_TEMPLATE`; an override of `writing.continuation` — per novel or
global — replaces it through the registry's effective chain, and its frame is
measured the same way, so a re-voiced prompt holds the budgets or is refused
by name (`PromptRenderError`, reason `budget`): sections are never cut to fit.

No environment variable remains here: the allocator is the one context
authority, and the resolved profile's limits decide the budgets the caller
passes in.
"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence  # noqa: TC003
from typing import Final
from uuid import UUID  # noqa: TC003

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.context import ContextBudgets  # noqa: TC001
from app.kernel.contracts.models import Chapter, Entity  # noqa: TC001
from app.kernel.prompts import PromptRenderError, get_registry, render, render_source

CONTINUATION_KEY: Final = "writing.continuation"

_ENTITIES_HEADING = "Referenced entities:"
_PREDECESSORS_HEADING = "Previous chapters:"
_STYLE_HEADING = "Style notes:"
# Heading + the heading's newline + the blank section separator. A slice below
# this cannot hold its section whole, so the section is omitted — a slice never
# overflows and no heading is ever truncated.
_SECTION_OVERHEAD = 3

CONTINUATION_TEMPLATE = (
    "Novel: {{ novel_title }}\n"
    "Chapter: {{ chapter_title }}\n"
    "\n"
    "Text so far:\n"
    "{{ tail }}\n"
    "\n"
    "{{ entities_section }}{{ predecessors_section }}{{ style_section }}"
    "Continue the chapter in the same voice. Keep the language of the existing "
    "text. Return only the new text, without a heading or commentary."
)


def sample_variables() -> dict[str, object]:
    """The sample the editor's legend and the save-time validation render.

    The sections are shown as the packers produce them — heading, entries and
    the blank separator — so an override's author sees what an override may
    reorder: whole sections, never their innards.
    """
    return {
        "novel_title": "Der Nebel",
        "chapter_title": "Ankunft",
        "tail": "Der Nebel kam von See.",
        "entities_section": "Referenced entities:\n### Mira (character)\nDie Wanderin.\n\n",
        "predecessors_section": "Previous chapters:\n### Ursprung\nMira kam.\n\n",
        "style_section": "Style notes:\nGenre: Mystery\nBlurb: Ein Nebeljahr.\n\n",
    }


def _packed_variables(
    budgets: ContextBudgets,
    novel_title: str,
    chapter_title: str,
    entities: Sequence[Entity],
    predecessors: Sequence[Chapter],
    genre: str | None,
    blurb: str | None,
) -> dict[str, str]:
    """The template's variables: the three sections packed within their slices.

    The assembly rules are today's, wrapped around the packers: a section
    whose slice cannot hold its heading plus separator — or that has no
    entries, or no style facts — arrives empty and renders nothing; a packed
    one carries its own blank-line separator, so the template needs none.
    """
    variables = {
        "novel_title": novel_title,
        "chapter_title": chapter_title,
        "entities_section": "",
        "predecessors_section": "",
        "style_section": "",
    }
    if budgets.referenced_entities >= len(_ENTITIES_HEADING) + _SECTION_OVERHEAD and entities:
        variables["entities_section"] = (
            _entities_block(entities, budgets.referenced_entities) + "\n\n"
        )
    if budgets.recent_chapters >= len(_PREDECESSORS_HEADING) + _SECTION_OVERHEAD and predecessors:
        variables["predecessors_section"] = (
            _predecessors_block(predecessors, budgets.recent_chapters) + "\n\n"
        )
    if budgets.style_hints >= len(_STYLE_HEADING) + _SECTION_OVERHEAD and (
        genre is not None or blurb is not None
    ):
        variables["style_section"] = _style_block(genre, blurb, budgets.style_hints)
    return variables


async def _fit_tail(
    render_one: Callable[[dict[str, str]], Awaitable[str]],
    budgets: ContextBudgets,
    body: str,
    variables: dict[str, str],
) -> str:
    """Render with the tail cut to what the template's frame leaves of the slice.

    Pass 1 probes with the full candidate tail (`body[-immediate_text:]`); the
    frame — the render beyond the sections and the tail, the design's
    "rendered total minus tail minus sections" — is measured off the probe,
    and pass 2 renders with the tail re-cut to the room left. A template
    whose glue grows as the tail shrinks (`{% else %}` branches) gets one
    more pass, the tail re-cut to the frame as last measured; a render that
    still overflows the slice is refused `budget`, never truncated — the
    sections, already within their own slices, are never cut to fit. A frame
    that merely does not fit degrades the tail (to empty, at the floor) the
    way the bundled scaffolding degrades in a degenerate window today.
    """
    candidate = body[-budgets.immediate_text :] if budgets.immediate_text > 0 else ""
    variables["tail"] = candidate
    rendered = await render_one(variables)

    sections = sum(len(value) for key, value in variables.items() if key.endswith("_section"))

    def frame(text: str) -> int:
        """The glue one render added: everything beyond the sections and the tail."""
        return len(text) - sections - len(variables["tail"])

    measured = frame(rendered)
    room = budgets.immediate_text - measured
    tail = body[-room:] if room > 0 else ""
    if tail != candidate:
        variables["tail"] = tail
        rendered = await render_one(variables)
        grown = frame(rendered) - measured
        if grown > 0:
            room = budgets.immediate_text - measured - grown
            variables["tail"] = body[-room:] if room > 0 else ""
            rendered = await render_one(variables)
            if frame(rendered) + len(variables["tail"]) > budgets.immediate_text:
                raise PromptRenderError(
                    "budget",
                    f"the template's frame grew to {frame(rendered)} characters and leaves "
                    f"no room for the chapter tail ({len(variables['tail'])} characters) "
                    f"inside the immediate-text budget ({budgets.immediate_text}); "
                    "the sections are never cut to fit",
                )
    return rendered


def _bundled_only(key: str) -> str:
    """The offline render's include chain: the bundled template includes nothing."""
    raise KeyError(key)


def continuation_prompt(
    *,
    budgets: ContextBudgets,
    novel_title: str,
    chapter_title: str,
    body: str,
    entities: Sequence[Entity] = (),
    predecessors: Sequence[Chapter] = (),
    genre: str | None = None,
    blurb: str | None = None,
) -> str:
    """The bundled continuation prompt, rendered offline inside the four budgets.

    Scaffolding counts: the ``Novel:``/``Chapter:`` header, the ``Text so
    far:`` tail and the instruction share the immediate-text slice; each
    optional section's heading shares its own slice. An entity entry is
    ``### {name} ({type})`` plus its body; when it exceeds the slice's
    remaining room it degrades to the ``{name} ({type})`` line, and when even
    the line does not fit the entity is skipped, silently. A predecessor
    contributes its title and a tail hard-cut to what remains of its slice.
    Sections whose slice is zero — or too small for the heading and its
    separator — are absent whole, as is a section with no entries at all; the
    style section is also omitted when the novel carries neither genre nor
    blurb. The arrangement is the bundled template's own: the sections are
    packed, the frame measured against the template, the tail cut to fit —
    the same flow the chain render runs.
    """

    async def bundled(variables: dict[str, str]) -> str:
        return render_source(CONTINUATION_TEMPLATE, variables, include=_bundled_only)

    return asyncio.run(
        _fit_tail(
            bundled,
            budgets,
            body,
            _packed_variables(
                budgets, novel_title, chapter_title, entities, predecessors, genre, blurb
            ),
        )
    )


async def render_continuation(
    session: AsyncSession,
    user_id: UUID,
    novel_id: UUID | None,
    *,
    budgets: ContextBudgets,
    novel_title: str,
    chapter_title: str,
    body: str,
    entities: Sequence[Entity],
    predecessors: Sequence[Chapter],
    genre: str | None,
    blurb: str | None,
) -> str:
    """The continuation prompt through the effective chain, the budgets held.

    The sections are packed exactly as the offline arrangement packs them;
    the source — the novel's override, else the user's global one, else the
    bundled template — owns the arrangement. The frame is measured and charged
    to the immediate-text slice (`_fit_tail`): the tail shrinks by the frame's
    measured length, and glue that grows as the tail shrinks — a frame the
    slice can never hold — is refused with ``PromptRenderError`` and reason
    ``budget``, the caller's error frame, never a truncated prompt. Read-only:
    the override chain is read, nothing written.
    """

    async def chain(variables: dict[str, str]) -> str:
        return await render(session, user_id, CONTINUATION_KEY, variables, novel_id=novel_id)

    return await _fit_tail(
        chain,
        budgets,
        body,
        _packed_variables(
            budgets, novel_title, chapter_title, entities, predecessors, genre, blurb
        ),
    )


def _entities_block(entities: Sequence[Entity], budget: int) -> str:
    """Pack the entities into their slice; the skip is silent, the slice full."""
    heading = _ENTITIES_HEADING
    entries: list[str] = []
    used = len(heading) + _SECTION_OVERHEAD
    for entity in entities:
        line = f"{entity.name} ({entity.type})"
        for entry in (f"### {line}\n{entity.content}", line):
            join = 1 if entries else 0
            if used + join + len(entry) <= budget:
                entries.append(entry)
                used += join + len(entry)
                break
    return heading + "".join(f"\n{entry}" for entry in entries)


def _predecessors_block(predecessors: Sequence[Chapter], budget: int) -> str:
    """Nearest first, each tail hard-cut to what the slice still has left."""
    heading = _PREDECESSORS_HEADING
    entries: list[str] = []
    used = len(heading) + _SECTION_OVERHEAD
    for chapter in predecessors:
        join = 1 if entries else 0
        title_line = f"### {chapter.title}\n"
        tail_room = budget - used - join - len(title_line)
        if tail_room <= 0:
            continue
        entry = title_line + chapter.body[-tail_room:]
        entries.append(entry)
        used += join + len(entry)
    return heading + "".join(f"\n{entry}" for entry in entries)


def _style_block(genre: str | None, blurb: str | None, budget: int) -> str:
    """`Genre:`/`Blurb:` lines, truncated to the slice, separator included.

    The cut reserves the trailing blank line: without it the next block (the
    instruction) would glue onto the truncated prose.
    """
    lines = "\n".join(
        line
        for line in (
            None if genre is None else f"Genre: {genre}",
            None if blurb is None else f"Blurb: {blurb}",
        )
        if line is not None
    )
    section = f"{_STYLE_HEADING}\n{lines}\n\n"
    if len(section) <= budget:
        return section
    return section[: budget - 2] + "\n\n"


get_registry().register(
    CONTINUATION_KEY,
    template=CONTINUATION_TEMPLATE,
    sample_variables=sample_variables,
    novel_scopable=True,
)
