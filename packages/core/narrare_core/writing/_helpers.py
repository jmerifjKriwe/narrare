"""Helper functions for the writing context assembler.

Extracted from ``context_assembler.py`` for RULE-04 compliance.
Contains frontmatter reference extraction and entity text formatting.

These are pure data transformations — no I/O, no DB, no LLM calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare_core.context.contracts import OmissionReason, ProvenanceField, RenderedKBContext
from narrare_core.shared.frontmatter import parse_frontmatter

if TYPE_CHECKING:
    from narrare_core.writing.context_models import KBEntity


_REFERENCE_KEYS: frozenset[str] = frozenset(
    {
        "pov_character",
        "characters",
        "location",
        "locations",
        "faction",
        "factions",
        "system",
        "systems",
        "timeline",
        "timelines",
    }
)


def extract_frontmatter_references(frontmatter: str) -> set[str]:
    """Extract entity IDs referenced in chapter frontmatter.

    Looks for keys: ``pov_character``, ``characters``, ``location``,
    ``locations``, ``faction``, ``factions``, ``system``, ``systems``,
    ``timeline``, ``timelines``.  Returns a set of entity ID strings.
    Returns an empty set for empty or unparsable input.
    """
    if not frontmatter.strip():
        return set()

    parsed = parse_frontmatter(frontmatter)
    if not parsed.has_frontmatter:
        return set()

    ids: set[str] = set()
    for key in _REFERENCE_KEYS:
        value = parsed.metadata.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            for item in value:  # pyright: ignore[reportUnknownVariableType]
                if item is not None:
                    ids.add(str(item))  # pyright: ignore[reportUnknownArgumentType]
        else:
            ids.add(str(value))  # pyright: ignore[reportUnknownArgumentType]
    return ids


_COMPACT_ENTITY_OMISSIONS: tuple[tuple[ProvenanceField, OmissionReason], ...] = (
    ("priority", "tier_does_not_require"),
    ("provenance", "tier_does_not_require"),
    ("review_state", "tier_does_not_require"),
    ("freshness", "tier_does_not_require"),
    ("kb_lifecycle", "tier_does_not_require"),
)


def format_entities(entities: list[KBEntity]) -> RenderedKBContext:
    """Format entities as a readable text block with provenance accounting.

    The prompt-bound text remains the historical compact format:
    ``### Type: Name\nContent``. ADR-050 P1-A accounting is carried in
    the returned :class:`RenderedKBContext` so metadata loss is explicit.
    """
    render_path = "narrare_core.writing._helpers.format_entities"
    if not entities:
        return RenderedKBContext(
            text="",
            preserved_fields=frozenset(),
            omitted_fields=(),
            entry_count=0,
            render_path=render_path,
        )
    parts: list[str] = []
    for entity in entities:
        header = f"### {entity.entity_type.title()}: {entity.name}"
        parts.append(f"{header}\n{entity.content}")
    return RenderedKBContext(
        text="\n\n".join(parts),
        preserved_fields=frozenset(),
        omitted_fields=_COMPACT_ENTITY_OMISSIONS,
        entry_count=len(entities),
        render_path=render_path,
    )
