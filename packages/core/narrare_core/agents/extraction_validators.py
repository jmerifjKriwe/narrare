"""Helpers for ExtractionAgent output validation — ADR-035.

Pure, side-effect-free predicates used by
``ExtractionAgent._validate_output``. Split from ``extraction_agent.py``
for RULE-04 compliance (agent files have a 200-line hard limit).

See:
    :class:`narrare_core.agents.extraction_agent.ExtractionAgent`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.agents.extraction_types import ExtractionItem


def has_text(value: str | None) -> bool:
    """True when value is a non-empty, non-whitespace string."""
    return value is not None and value.strip() != ""


def dedup_key(item: ExtractionItem) -> tuple[str, ...]:
    """Identity of an extraction item for duplicate detection.

    Relationship items are identified by (predicate, endpoints, name):
    under the predicate contract ``name`` alone would falsely collide for
    same-type edges between different endpoint pairs.
    """
    if item.item_type == "relationship":
        target = item.target_entity_name or item.related_entity_name or ""
        return (
            item.item_type,
            (item.relationship_type or "").strip(),
            (item.source_entity_name or "").strip(),
            target.strip(),
            item.name.strip(),
        )
    return (item.item_type, item.name.strip())
