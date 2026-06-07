"""Timeline event data extraction for consistency checking — FIND-009.

Extracts timeline event data from the planning module's TimelineEvent ORM
model into the simple dict format used by ConsistencyDeps.timeline_events.

Extracted from checker_service.py for RULE-04 compliance (300-line limit).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    import uuid

    from narrare.planning.timeline_repository import TimelineEventRepository

logger = structlog.get_logger(__name__)


async def fetch_timeline_events(
    timeline_repo: TimelineEventRepository,
    novel_id: uuid.UUID,
) -> list[dict[str, str]]:
    """Fetch confirmed timeline events formatted for ConsistencyDeps.

    Extracts temporal event data from the planning module's
    ``TimelineEventRepository`` and formats each event into a simple
    dict with ``event_name``, ``timestamp``, ``character``, and ``location``.

    Graceful degradation: if the fetch fails (e.g., missing table during
    migration), returns an empty list so consistency checking continues
    without timeline context.

    Args:
        timeline_repo: Repository for timeline event persistence.
        novel_id: The novel whose timeline events to fetch.

    Returns:
        List of event dicts suitable for ``ConsistencyDeps.timeline_events``.
        Empty list if no events exist or fetch fails.
    """
    try:
        events = await timeline_repo.list_by_novel(
            novel_id,
            is_confirmed=True,
        )
    except Exception:
        logger.warning(
            "timeline_events_fetch_failed",
            novel_id=str(novel_id),
            exc_info=True,
        )
        return []

    formatted: list[dict[str, str]] = []
    for event in events:
        # Extract character names from refs: [{"id": "uuid", "name": "Aria"}, ...]
        char_names = ", ".join(
            str(ref.get("name", "")) for ref in (event.character_refs or []) if ref.get("name")
        )
        # Extract location name from ref: {"id": "uuid", "name": "Castle"}
        loc_name = ""
        if event.location_ref:
            loc_name = str(event.location_ref.get("name", ""))

        formatted.append(
            {
                "event_name": event.event_name,
                "timestamp": event.timestamp_raw,
                "character": char_names,
                "location": loc_name,
            }
        )
    return formatted
