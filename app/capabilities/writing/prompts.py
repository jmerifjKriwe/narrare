"""The budgeted continuation prompt. Writing owns its prompt text, per the spec.

The context a continuation carries is assembled from the four named slices the
kernel allocator sized (`app.kernel.context`): the chapter tail, the entities
the tail names, the previous chapters' tails and the novel's style hints — each
hard-cut to its slice, scaffolding included, so a slice never overflows. A
slice whose floor is zero is omitted at assembly; nothing rides free.

No environment variable remains here: the allocator is the one context
authority, and the resolved profile's limits decide the budgets the caller
passes in.
"""

from collections.abc import Sequence  # noqa: TC003

from app.kernel.context import ContextBudgets  # noqa: TC001
from app.kernel.contracts.models import Chapter, Entity  # noqa: TC001

_INSTRUCTION = (
    "Continue the chapter in the same voice. Keep the language of the existing "
    "text. Return only the new text, without a heading or commentary."
)

_ENTITIES_HEADING = "Referenced entities:"
_PREDECESSORS_HEADING = "Previous chapters:"
_STYLE_HEADING = "Style notes:"
# Heading + the heading's newline + the blank section separator. A slice below
# this cannot hold its section whole, so the section is omitted — a slice never
# overflows and no heading is ever truncated.
_SECTION_OVERHEAD = 3


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
    """Render the continuation prompt inside the four budgets.

    Scaffolding counts: the ``Novel:``/``Chapter:`` header, the ``Text so
    far:`` tail and the instruction share the immediate-text slice; each
    optional section's heading shares its own slice. An entity entry is
    ``### {name} ({type})`` plus its body; when it exceeds the slice's
    remaining room it degrades to the ``{name} ({type})`` line, and when even
    the line does not fit the entity is skipped, silently. A predecessor
    contributes its title and a tail hard-cut to what remains of its slice.
    Sections whose slice is zero — or too small for the heading and its
    separator — are absent whole; the style section is also omitted when the
    novel carries neither genre nor blurb.
    """
    header = f"Novel: {novel_title}\nChapter: {chapter_title}\n\n"
    room = (
        budgets.immediate_text
        - len(header)
        - len("Text so far:\n")
        - len("\n\n")
        - len(_INSTRUCTION)
    )
    tail = body[-room:] if room > 0 else ""
    blocks = [header, f"Text so far:\n{tail}\n\n"]
    if budgets.referenced_entities >= len(_ENTITIES_HEADING) + _SECTION_OVERHEAD:
        blocks.append(_entities_block(entities, budgets.referenced_entities) + "\n\n")
    if budgets.recent_chapters >= len(_PREDECESSORS_HEADING) + _SECTION_OVERHEAD:
        blocks.append(_predecessors_block(predecessors, budgets.recent_chapters) + "\n\n")
    if budgets.style_hints >= len(_STYLE_HEADING) + _SECTION_OVERHEAD and (
        genre is not None or blurb is not None
    ):
        blocks.append(_style_block(genre, blurb, budgets.style_hints))
    blocks.append(_INSTRUCTION)
    return "".join(blocks)


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
    """`Genre:`/`Blurb:` lines, truncated to the slice, separator included."""
    lines = "\n".join(
        line
        for line in (
            None if genre is None else f"Genre: {genre}",
            None if blurb is None else f"Blurb: {blurb}",
        )
        if line is not None
    )
    section = f"{_STYLE_HEADING}\n{lines}\n\n"
    return section[:budget]
