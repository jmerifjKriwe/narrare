"""Helper functions for the writing context assembler.

Extracted from ``context_assembler.py`` for RULE-04 compliance.
Contains frontmatter reference extraction and entity text formatting.

These are pure data transformations — no I/O, no DB, no LLM calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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
    }
)


def extract_frontmatter_references(frontmatter: str) -> set[str]:
    """Extract entity IDs referenced in chapter frontmatter.

    Looks for keys: ``pov_character``, ``characters``, ``location``,
    ``locations``, ``faction``, ``factions``.  Returns a set of entity
    ID strings.  Returns an empty set for empty or unparsable input.
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


def format_entities(entities: list[KBEntity]) -> str:
    """Format entities as a readable text block."""
    if not entities:
        return ""
    parts: list[str] = []
    for entity in entities:
        header = f"### {entity.entity_type.title()}: {entity.name}"
        parts.append(f"{header}\n{entity.content}")
    return "\n\n".join(parts)
