"""The budgeted continuation prompt. Writing owns its prompt text, per the spec.

The context a continuation carries is assembled from the four named slices the
kernel allocator sized (`app.kernel.context`): the active scene's tail, the
entities the tail names, the preceding scenes' tails and the novel's style hints
— each hard-cut to its slice, scaffolding included, so a slice never overflows.
A slice whose floor is zero is omitted at assembly; nothing rides free.

The prose unit is the scene (W4 §5): the predecessors are the active chapter's
earlier scenes, then earlier chapters' scenes, nearest first, with chapter titles
as separators — the chapter-predecessors logic refined onto scenes, not replaced.

The packers fill, the template arranges (the B docking): the three optional
sections arrive pre-packed within their slices as opaque strings, and the
template owns order, glue and instruction. The bundled arrangement is
`CONTINUATION_TEMPLATE`; an override of `writing.continuation` — per novel or
global — replaces it through the registry's effective chain, and its frame is
measured the same way, so a re-voiced prompt holds the budgets or is refused
by name (`PromptRenderError`, reason `budget`): sections are never cut to fit.

The writer's optional instruction (W4 D5) rides the same system: a carried
prompt arrives as one pre-packed block — separator, heading, the prompt
verbatim — placed by the template after the closing instruction. It is frame,
not a section: it shares the immediate-text slice with the scaffold and the
tail, the tail shrinks by its measured length, and a block the slice cannot
hold beside the scaffold refuses `budget` like any frame too big — the
instruction is never truncated to fit. An override that does not place the
`instruction` variable renders without it, its unrendered length never charged.

No environment variable remains here: the allocator is the one context
authority, and the resolved profile's limits decide the budgets the caller
passes in.
"""

import asyncio
from collections.abc import Awaitable, Callable, Sequence  # noqa: TC003
from dataclasses import dataclass
from typing import Final
from uuid import UUID  # noqa: TC003

from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002

from app.kernel.context import BudgetImpossibleError, ContextBudgets
from app.kernel.contracts.models import Entity  # noqa: TC001
from app.kernel.prompts import (
    AssembledContext,
    LiveContextMissingError,
    LiveTestContext,
    PromptRenderError,
    get_registry,
    no_includes,
    render,
    render_source,
)

CONTINUATION_KEY: Final = "writing.continuation"


@dataclass(frozen=True)
class PredecessorScene:
    """One earlier scene in the continuation's context, nearest first (W4 §5).

    ``chapter_id``/``chapter_title`` name the chapter the scene belongs to: the
    block renders the title as a ``###`` separator when the stream crosses into
    a new chapter, and the id (not the title) decides the boundary, so two
    unnamed chapters still separate. ``body`` is the scene's prose, hard-cut to
    the slice's remaining room at assembly.
    """

    chapter_id: UUID
    chapter_title: str
    body: str


_ENTITIES_HEADING = "Referenced entities:"
_PREDECESSORS_HEADING = "Previous chapters:"
_STYLE_HEADING = "Style notes:"
_INSTRUCTION_HEADING = "Writer's instruction:"
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
    "{{ instruction }}"
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
        "instruction": "\n\nWriter's instruction:\nLass Mira am Ufer zögern.",
    }


def _instruction_block(prompt: str | None) -> str:
    """The writer instruction as one pre-packed block, or nothing (W4 D5).

    None — and the empty string the schema already refuses — is no
    instruction: the variable renders empty and the arrangement is today's,
    byte for byte. A carried prompt rides verbatim under its heading with the
    leading separator; the block is last, so it carries no trailing one. The
    prompt is never trimmed here — the chat question's precedent bounds the
    raw string at the schema, and what passes renders as written.
    """
    if not prompt:
        return ""
    return f"\n\n{_INSTRUCTION_HEADING}\n{prompt}"


def _packed_variables(
    budgets: ContextBudgets,
    novel_title: str,
    chapter_title: str,
    entities: Sequence[Entity],
    predecessors: Sequence[PredecessorScene],
    genre: str | None,
    blurb: str | None,
    active_chapter_id: UUID | None = None,
    prompt: str | None = None,
) -> dict[str, str]:
    """The template's variables: the three sections packed within their slices.

    The assembly rules are today's, wrapped around the packers: a section
    whose slice cannot hold its heading plus separator — or that has no
    entries, or no style facts — arrives empty and renders nothing; a packed
    one carries its own blank-line separator, so the template needs none.
    The writer instruction (W4 D5) is no section: its block rides whole as
    frame, charged to the immediate slice by the fit, never packed or cut.
    """
    variables = {
        "novel_title": novel_title,
        "chapter_title": chapter_title,
        "entities_section": "",
        "predecessors_section": "",
        "style_section": "",
        "instruction": _instruction_block(prompt),
    }
    if budgets.referenced_entities >= len(_ENTITIES_HEADING) + _SECTION_OVERHEAD and entities:
        entities_block = _entities_block(entities, budgets.referenced_entities)
        if entities_block:
            variables["entities_section"] = entities_block + "\n\n"
    if budgets.recent_chapters >= len(_PREDECESSORS_HEADING) + _SECTION_OVERHEAD and predecessors:
        predecessors_block = _predecessors_block(
            predecessors, active_chapter_id, budgets.recent_chapters
        )
        if predecessors_block:
            variables["predecessors_section"] = predecessors_block + "\n\n"
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

    def _rendered_sections(text: str) -> int:
        # Count only the sections the template actually rendered, using their
        # original (unwrapped) text, so an override that drops a section does
        # not donate that section's length to the tail's room. No sentinel
        # overhead is measured.
        total = 0
        for key, value in variables.items():
            if key.endswith("_section") and value and value in text:
                total += len(value)
        return total

    def frame(text: str) -> int:
        """The glue one render added: everything beyond the sections and the tail."""
        return len(text) - _rendered_sections(text) - len(variables["tail"])

    measured = frame(rendered)
    # The fixed scaffolding (header, Text-so-far, instruction) is uncuttable:
    # if it alone exceeds the immediate slice, the window cannot hold even an
    # empty continuation, so refuse instead of overflowing.
    if measured > budgets.immediate_text:
        raise BudgetImpossibleError(
            "the continuation scaffold does not fit the immediate-text budget "
            f"({measured} characters vs {budgets.immediate_text})"
        )
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


def scaffold_length(novel_title: str, chapter_title: str, prompt: str | None = None) -> int:
    """The bundled template's fixed frame for an empty tail and no sections.

    The allocator's immediate slice also carries the header, the ``Text so
    far:`` scaffolding and the instruction; this is what that fixed frame
    measures, so a scan that ranks entities by their position in the tail
    excludes the characters that never reach the model. A carried writer
    instruction (W4 D5) is frame too: its block rides in the measurement, so
    the scan window shrinks by exactly the room the instruction takes.
    """
    variables = {
        "novel_title": novel_title,
        "chapter_title": chapter_title,
        "tail": "",
        "entities_section": "",
        "predecessors_section": "",
        "style_section": "",
        "instruction": _instruction_block(prompt),
    }
    return len(render_source(CONTINUATION_TEMPLATE, variables, include=no_includes))


def continuation_prompt(
    *,
    budgets: ContextBudgets,
    novel_title: str,
    chapter_title: str,
    body: str,
    entities: Sequence[Entity] = (),
    predecessors: Sequence[PredecessorScene] = (),
    genre: str | None = None,
    blurb: str | None = None,
    active_chapter_id: UUID | None = None,
    prompt: str | None = None,
) -> str:
    """The bundled continuation prompt, rendered offline inside the four budgets.

    Offline-only: this sync entry point raises RuntimeError under a running
    event loop (it uses asyncio.run); it is the golden subject for the bundled
    template and is not the service method of the same name.

    Scaffolding counts: the ``Novel:``/``Chapter:`` header, the ``Text so
    far:`` tail and the instruction share the immediate-text slice; each
    optional section's heading shares its own slice. An entity entry is
    ``### {name} ({type})`` plus its body; when it exceeds the slice's
    remaining room it degrades to the ``{name} ({type})`` line, and when even
    the line does not fit the entity is skipped, silently. A predecessor scene
    contributes a tail hard-cut to what remains of its slice, under its
    chapter's ``###`` separator when the stream crosses into a new chapter
    (``active_chapter_id`` names the chapter the tail belongs to, so its own
    earlier scenes carry no separator). Sections whose slice is zero — or too
    small for the heading and its separator — are absent whole, as is a section
    with no entries at all; the style section is also omitted when the novel
    carries neither genre nor blurb. The arrangement is the bundled template's
    own: the sections are packed, the frame measured against the template, the
    tail cut to fit — the same flow the chain render runs. A carried writer
    instruction (W4 D5) rides as frame after the closing instruction: the tail
    shrinks by its block, and a block the slice cannot hold refuses
    `BudgetImpossibleError` — never a truncated instruction.
    """

    async def bundled(variables: dict[str, str]) -> str:
        return render_source(CONTINUATION_TEMPLATE, variables, include=no_includes)

    return asyncio.run(
        _fit_tail(
            bundled,
            budgets,
            body,
            _packed_variables(
                budgets,
                novel_title,
                chapter_title,
                entities,
                predecessors,
                genre,
                blurb,
                active_chapter_id,
                prompt,
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
    predecessors: Sequence[PredecessorScene],
    genre: str | None,
    blurb: str | None,
    active_chapter_id: UUID | None = None,
    prompt: str | None = None,
    source: str | None = None,
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

    An explicit ``source`` renders instead of the chain's pick (W8's live
    test): the editor draft under test is budgeted and refused exactly as a
    saved override would be, while its includes still walk the chain.

    The writer instruction (W4 D5) rides the same fit: its block is frame the
    source may place anywhere — an override that does not name the
    ``instruction`` variable renders without it, and only what rendered is
    charged. A block the slice cannot hold refuses like any frame too big.
    """

    async def chain(variables: dict[str, str]) -> str:
        return await render(
            session, user_id, CONTINUATION_KEY, variables, novel_id=novel_id, source=source
        )

    return await _fit_tail(
        chain,
        budgets,
        body,
        _packed_variables(
            budgets,
            novel_title,
            chapter_title,
            entities,
            predecessors,
            genre,
            blurb,
            active_chapter_id,
            prompt,
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
    if not entries:
        return ""
    return heading + "".join(f"\n{entry}" for entry in entries)


def _predecessors_block(
    predecessors: Sequence[PredecessorScene], active_chapter_id: UUID | None, budget: int
) -> str:
    """Nearest first, each scene's tail hard-cut to what the slice still has left.

    The unit is the scene (W4 §5): the active chapter's earlier scenes, then
    earlier chapters' scenes, each chapter's nearest first. A chapter title
    rides as a ``###`` separator when the stream crosses into a new chapter —
    the active chapter's own earlier scenes share the header's chapter and
    carry none. An empty (or whitespace-only) scene carries no prose and is
    skipped, separator and all; a scene that does not fit stops the packing,
    since farther ones must not skip past the nearest that failed.
    """
    heading = _PREDECESSORS_HEADING
    entries: list[str] = []
    used = len(heading) + _SECTION_OVERHEAD
    current_chapter = active_chapter_id
    for scene in predecessors:
        if not scene.body.strip():
            continue
        join = 1 if entries else 0
        separator = ""
        if scene.chapter_id != current_chapter:
            separator = f"### {scene.chapter_title}\n"
            current_chapter = scene.chapter_id
        tail_room = budget - used - join - len(separator)
        if tail_room <= 0:
            # The nearest scene did not fit; farther ones must not skip past
            # it, so stop packing here.
            break
        entry = separator + scene.body[-tail_room:]
        entries.append(entry)
        used += join + len(entry)
    if not entries:
        return ""
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


async def _assemble_live(context: LiveTestContext) -> AssembledContext:
    """The live test's continuation: the writer's latest scene, the real budgets.

    The same assembly the continuation endpoint runs — the service gathers
    the scene, its chapter and novel, the entities the tail names and the
    predecessors — over the writer's most recently touched scene, with the
    resolved tier's numbers as the budgets and the draft (or the effective
    chain) as the source. The import is deferred: this module registers at
    import time and the service imports it.
    """
    from app.capabilities.writing.service import WritingService

    service = WritingService(context.session, context.user_id)
    scene = await service.latest_scene(context.novel_id)
    if scene is None:
        raise LiveContextMissingError("no scene to continue yet — write a scene first")
    prompt = await service.continuation_prompt(
        scene.id,
        source=context.source,
        context_window=context.resolved.context_window,
        max_output_tokens=context.resolved.max_output_tokens,
        model=context.resolved.model,
    )
    chapter = await service.get_chapter(scene.chapter_id)
    novel = await service.novels.get(chapter.novel_id)
    facts = {"chapter": chapter.title}
    if novel is not None:
        facts = {"novel": novel.title, **facts}
    if scene.title:
        facts["scene"] = scene.title
    return AssembledContext(prompt=prompt, facts=facts)


get_registry().register(
    CONTINUATION_KEY,
    template=CONTINUATION_TEMPLATE,
    sample_variables=sample_variables,
    novel_scopable=True,
    assemble=_assemble_live,
)
