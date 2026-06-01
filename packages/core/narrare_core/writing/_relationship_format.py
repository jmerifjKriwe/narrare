"""Format KB relationship data into human-readable text for writing prompts.

Pure function — no I/O, no DB, no side effects.  Takes structured
relationship data from the API layer and produces the ``→``-formatted
text injected into ``WritingContext.kb_relationships`` (FIND-009).

Output format::

    Aria → [ally of] → Marcus
    Aria → [member of] → Night Watch
    Marcus → [rival of] → Elena

Relationships are grouped by source entity and sorted alphabetically
for deterministic output.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Sequence


class RelationshipEdge(NamedTuple):
    """A single relationship edge with resolved names.

    Produced by the API layer (repository) and consumed by
    :func:`format_relationships`.
    """

    source_name: str
    rel_type: str
    label: str | None
    target_name: str
    direction: str  # "directed" | "mutual"


def format_relationships(
    edges: Sequence[tuple[str, str, str | None, str, str]] | None,
) -> str:
    """Format relationship edges into human-readable text for prompts.

    Accepts any sequence of 5-tuples ``(source_name, rel_type, label,
    target_name, direction)`` — this includes both
    :class:`RelationshipEdge` and the repository's
    :class:`RelationshipEdgeRow` without requiring mapping.

    Args:
        edges: Sequence of relationship edge tuples.  Each tuple has:
            ``(source_name, rel_type, label, target_name, direction)``.

    Returns:
        Formatted relationship text with one line per edge, grouped
        by source entity and sorted alphabetically.  Empty string when
        *edges* is ``None`` or empty.
    """
    if not edges:
        return ""

    # Sort for deterministic output: by source_name, then rel_type, then target_name
    sorted_edges = sorted(edges, key=lambda e: (e[0], e[1], e[3]))

    lines: list[str] = []
    for source_name, rel_type, label, target_name, _direction in sorted_edges:
        display_label = label or rel_type
        lines.append(f"{source_name} → [{display_label}] → {target_name}")

    return "\n".join(lines)
