"""Utility functions for timeline event conversion.

Extracted from ``timeline_consistency_service.py`` for RULE-04 compliance
(the service was approaching the 300-line limit).

These helpers convert :class:`TimelineEvent` ORM objects into the plain-dict
format expected by ``core/analysis/temporal.py`` deterministic checks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare.planning.models import TimelineEvent


def events_to_dicts(events: list[TimelineEvent]) -> list[dict[str, object]]:
    """Convert TimelineEvent ORM objects to dicts for deterministic checks.

    The core analysis functions expect plain dicts with specific keys:
    id, event_name, temporal_order, causes, consequences,
    timestamp_raw, chapter_reference, character_refs,
    location_ref, event_type.

    ``location_ref`` comes from JSONB (dict or None).
    ``event_type`` is a plain string field from the model.

    Args:
        events: List of TimelineEvent ORM objects.

    Returns:
        List of dicts with the keys expected by ``run_deterministic_checks``.
    """
    result: list[dict[str, object]] = []
    for event in events:
        result.append(
            {
                "id": str(event.id),
                "event_name": event.event_name,
                "temporal_order": event.temporal_order,
                "causes": event.causes,
                "consequences": event.consequences,
                "timestamp_raw": event.timestamp_raw,
                "timestamp_normalized": event.timestamp_normalized,
                "chapter_reference": str(event.chapter_id) if event.chapter_id else "",
                "character_refs": event.character_refs or [],
                "location_ref": event.location_ref or None,
                "event_type": event.event_type,
            },
        )
    return result
