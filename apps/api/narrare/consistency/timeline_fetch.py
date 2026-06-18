"""Timeline event data extraction for consistency checking — FIND-009.

Extracts timeline event data from the planning module's TimelineEvent ORM
model into the simple dict format used by ConsistencyDeps.timeline_events.

Extracted from checker_service.py for RULE-04 compliance (300-line limit).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

import structlog

from narrare_core.context.contracts import OmissionReason, ProvenanceField, RenderedKBContext

if TYPE_CHECKING:
    import uuid
    from collections.abc import Iterable

    from narrare.kb.repository import KBRepository
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare_core.agents.fact_extractor_types import TimelineEventEnvelope

logger = structlog.get_logger(__name__)


class _TimelineEventForRender(Protocol):
    """Structural shape needed by the timeline legacy formatter."""

    event_name: str
    timestamp_raw: str
    character_refs: list[dict[str, object]] | None
    location_ref: dict[str, object] | None


_TIMELINE_OMISSIONS: tuple[tuple[ProvenanceField, OmissionReason], ...] = (
    ("provenance", "consumer_cannot_act"),
    ("evidence", "consumer_cannot_act"),
    ("review_state", "consumer_cannot_act"),
    ("freshness", "consumer_cannot_act"),
    ("kb_lifecycle", "consumer_cannot_act"),
)


def _format_timeline_events(
    events: Iterable[_TimelineEventForRender],
) -> tuple[list[dict[str, str]], RenderedKBContext]:
    """Format timeline events for legacy deps and ADR-050 accounting.

    Args:
        events: Iterable of timeline event objects from the repository.

    Returns:
        Tuple of legacy event dictionaries and a RenderedKBContext audit
        envelope. The legacy dictionaries are unchanged for existing
        consumers; the envelope records metadata omitted by that legacy
        wire shape.
    """
    formatted: list[dict[str, str]] = []
    text_lines: list[str] = []
    for event in events:
        char_names = ", ".join(
            str(ref.get("name", "")) for ref in (event.character_refs or []) if ref.get("name")
        )
        loc_name = ""
        if event.location_ref:
            loc_name = str(event.location_ref.get("name", ""))

        formatted_event = {
            "event_name": event.event_name,
            "timestamp": event.timestamp_raw,
            "character": char_names,
            "location": loc_name,
        }
        formatted.append(formatted_event)
        text_lines.append(
            f"{formatted_event['event_name']} @ {formatted_event['timestamp']}"
            f" | {formatted_event['character']} | {formatted_event['location']}"
        )

    rendered = RenderedKBContext(
        text="\n".join(text_lines),
        preserved_fields=frozenset(),
        omitted_fields=_TIMELINE_OMISSIONS if formatted else (),
        entry_count=len(formatted),
        render_path="narrare.consistency.timeline_fetch._format_timeline_events",
    )
    return formatted, rendered


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

    # SQLAlchemy Mapped attributes satisfy the runtime shape, but static
    # analysis sees descriptors; narrow to the render protocol at the boundary.
    renderable_events = cast("Iterable[_TimelineEventForRender]", events)
    formatted, _rendered = _format_timeline_events(renderable_events)
    return formatted


async def fetch_timeline_event_envelopes(
    timeline_repo: TimelineEventRepository,
    kb_repo: KBRepository,
    novel_id: uuid.UUID,
) -> list[TimelineEventEnvelope]:
    """Fetch enriched timeline envelopes for ADR-044 staged consistency.

    This is the structured companion to ``fetch_timeline_events()``. It keeps
    the legacy compact list unchanged while exposing the FIND-009 metadata that
    the staged pipeline needs: normalized timestamps, temporal order, chapter
    provenance, causality, source, confidence, confirmation, and KB status.

    KB liveness note: current KB entries expose ``draft``, ``reviewed``,
    ``canon``, and ``deprecated`` statuses. They do not expose rename targets or
    deleted tombstones. Existing non-deprecated entries are therefore represented
    as ``active``; missing references are represented as ``unknown`` rather than
    falsely labeled ``deleted``.

    Args:
        timeline_repo: Repository for timeline event persistence.
        kb_repo: KB repository for entity status lookups.
        novel_id: The novel whose timeline events to fetch.

    Returns:
        Enriched timeline envelopes. Empty when the timeline fetch fails, with a
        warning log entry so the degradation is visible.
    """
    from narrare.consistency.timeline_envelope import enrich_timeline_envelopes

    try:
        events = await timeline_repo.list_by_novel(novel_id, is_confirmed=True)
    except Exception:
        logger.warning(
            "timeline_envelopes_fetch_failed",
            novel_id=str(novel_id),
            exc_info=True,
        )
        return []

    return await enrich_timeline_envelopes(events, kb_repo, novel_id)
