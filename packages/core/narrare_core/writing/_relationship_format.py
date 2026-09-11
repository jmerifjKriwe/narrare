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

Output is capped at :data:`DEFAULT_MAX_RELATIONSHIP_EDGES` rendered lines
(overridable per call via ``max_edges``).  Above the cap, a deterministic
first-N slice is rendered plus an omission marker line; ``entry_count``
always reports the TOTAL pre-cap edge count (metadata = KB truth).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, NamedTuple

from narrare_core.context.contracts import OmissionReason, ProvenanceField, RenderedKBContext

if TYPE_CHECKING:
    from collections.abc import Sequence


#: Hard cap on rendered relationship edges — Ruling 1 (PO architecture
#: short-check, 2026-09): count-based cap at the core formatter so every
#: caller (writing routes, draft, chat, analysis) inherits it uniformly.
#: 100 lines of ``A → [rel] → B`` ≈ 1.0-1.5k tokens, the ceiling the
#: prompt budgets allow for unbudgeted KB relationship context.
#: RULE-18: ``Final`` marks this as a pinned domain ceiling, not
#: configuration (precedent: ``TOKEN_OUTPUT_ABSOLUTE_MAX`` in
#: ``llm/token_profiles.py``); no settings key this slice — callers
#: override via ``format_relationships(max_edges=...)``.
DEFAULT_MAX_RELATIONSHIP_EDGES: Final[int] = 100


_RELATIONSHIP_OMISSIONS: tuple[tuple[ProvenanceField, OmissionReason], ...] = (
    ("provenance", "tier_does_not_require"),
    ("evidence", "tier_does_not_require"),
    ("review_state", "tier_does_not_require"),
    ("freshness", "tier_does_not_require"),
    ("kb_lifecycle", "tier_does_not_require"),
)


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
    max_edges: int | None = None,
) -> RenderedKBContext:
    """Format relationship edges into human-readable text for prompts.

    Accepts any sequence of 5-tuples ``(source_name, rel_type, label,
    target_name, direction)`` — this includes both
    :class:`RelationshipEdge` and the repository's
    :class:`RelationshipEdgeRow` without requiring mapping.

    Args:
        edges: Sequence of relationship edge tuples.  Each tuple has:
            ``(source_name, rel_type, label, target_name, direction)``.
        max_edges: Maximum number of edges rendered into ``.text``
            (deterministic first-N AFTER sorting; the sort guarantee is
            preserved, so which N survive is order-independent).
            ``None`` falls back to :data:`DEFAULT_MAX_RELATIONSHIP_EDGES`.

    Returns:
        Rendered relationship context. ``.text`` is the legacy formatted
        text with one line per edge, grouped by source entity and sorted
        alphabetically.  When the total edge count exceeds the effective
        cap, only the first ``max_edges`` sorted lines are rendered and a
        final ``[… N more relationships omitted]`` marker line is appended
        (LLM-visible, deterministic); at or below the cap there is no
        marker.  ``entry_count`` always reports the TOTAL pre-cap edge
        count — metadata stays KB truth regardless of truncation.
    """
    render_path = "narrare_core.writing._relationship_format.format_relationships"
    if not edges:
        return RenderedKBContext(
            text="",
            preserved_fields=frozenset(),
            omitted_fields=(),
            entry_count=0,
            render_path=render_path,
        )

    cap = DEFAULT_MAX_RELATIONSHIP_EDGES if max_edges is None else max_edges

    # Sort for deterministic output: by source_name, then rel_type, then target_name
    sorted_edges = sorted(edges, key=lambda e: (e[0], e[1], e[3]))

    total = len(sorted_edges)
    rendered_edges = sorted_edges[:cap]

    lines: list[str] = []
    for source_name, rel_type, label, target_name, _direction in rendered_edges:
        display_label = label or rel_type
        lines.append(f"{source_name} → [{display_label}] → {target_name}")

    omitted = total - len(rendered_edges)
    if omitted > 0:
        lines.append(f"[… {omitted} more relationships omitted]")

    return RenderedKBContext(
        text="\n".join(lines),
        preserved_fields=frozenset(),
        omitted_fields=_RELATIONSHIP_OMISSIONS,
        entry_count=total,
        render_path=render_path,
    )
