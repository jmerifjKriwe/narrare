"""Timeline event enrichment — TimelineEvent to TimelineEventEnvelope (ADR-044).

Produces ``TimelineEventEnvelope[]`` from ``TimelineEvent`` ORM records,
cross-referencing KB entity status for character_refs and location_ref.
Directly addresses FIND-009: preserves all provenance metadata that was
previously lost during compact text formatting.

Extracted from ``timeline_fetch.py`` for RULE-04 compliance — the original
function produces simple dicts; this module produces structured envelopes
for the staged pipeline.

See:
    :mod:`narrare.consistency.timeline_fetch` — Legacy dict-based fetch.
    ADR-044 — Staged Multi-Agent Consistency Pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

import structlog

from narrare_core.agents.fact_extractor_types import TimelineEventEnvelope

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from narrare.planning.models import TimelineEvent

logger = structlog.get_logger(__name__)


class _KBStatusRepositoryProtocol(Protocol):
    """Structural repository type for KB status lookups."""

    async def list_entries(
        self,
        novel_id: uuid.UUID,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        review_status: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[Sequence[object], int]: ...


# Mapping from KB model status values to envelope status values.
# The KB model currently uses: draft, reviewed, canon, deprecated.
# It does not expose rename targets or deleted tombstones to timeline refs, so
# this bridge only reports statuses it can know accurately: active/deprecated.
# Missing refs are marked as unknown, never guessed as deleted.
_KB_STATUS_MAP: dict[str, str] = {
    "draft": "active",
    "reviewed": "active",
    "canon": "active",
    "deprecated": "deprecated",
}


async def enrich_timeline_envelopes(
    events: list[TimelineEvent],
    kb_repo: _KBStatusRepositoryProtocol,
    novel_id: uuid.UUID,
) -> list[TimelineEventEnvelope]:
    """Convert TimelineEvent records into enriched TimelineEventEnvelope list.

    Cross-references KB entity status for each character_ref and location_ref
    so downstream agents (FactExtractorAgent, ConsistencyAgent) can reason
    about entity provenance and confidence.

    KB liveness/status behavior: existing non-deprecated entries are ``active``;
    deprecated entries remain ``deprecated``; missing or lookup-failed refs are
    ``unknown`` because current KB data cannot prove renamed/deleted state.

    Args:
        events: TimelineEvent ORM records from the planning module.
        kb_repo: KB repository for entity status lookups.
        novel_id: The novel ID for scoping KB lookups.

    Returns:
        List of TimelineEventEnvelope with full provenance metadata.
    """
    # Build a name→status lookup from KB entities for this novel.
    entity_status_map = await _build_entity_status_map(kb_repo, novel_id)

    envelopes: list[TimelineEventEnvelope] = []
    for event in events:
        # Enrich character refs with KB status
        enriched_chars = _enrich_character_refs(event, entity_status_map)

        # Enrich location ref with KB status
        enriched_location = _enrich_location_ref(event, entity_status_map)

        # Build kb_entity_status from all referenced entities
        kb_entity_status = _build_kb_entity_status(event, entity_status_map)

        # Parse causes/consequences from comma-separated strings
        causes = _split_list_field(event.causes)
        consequences = _split_list_field(event.consequences)

        envelopes.append(
            TimelineEventEnvelope(
                event_id=str(event.id),
                event_name=event.event_name,
                timestamp_raw=event.timestamp_raw,
                timestamp_normalized=event.timestamp_normalized or None,
                temporal_order=event.temporal_order,
                source_chapter_id=str(event.chapter_id) if event.chapter_id else None,
                character_refs=enriched_chars,
                location_ref=enriched_location,
                causes=causes,
                consequences=consequences,
                source=event.source,
                confidence=event.confidence if event.confidence is not None else 1.0,
                is_confirmed=event.is_confirmed,
                kb_entity_status=kb_entity_status,
            )
        )

    logger.debug(
        "timeline_envelopes_enriched",
        novel_id=str(novel_id),
        event_count=len(envelopes),
        entity_count=len(entity_status_map),
    )
    return envelopes


async def _build_entity_status_map(
    kb_repo: _KBStatusRepositoryProtocol,
    novel_id: uuid.UUID,
) -> dict[str, str]:
    """Build a mapping of entity name → KB status for cross-referencing.

    Gracefully returns empty dict on any failure (pipeline continues without
    KB status enrichment).

    Args:
        kb_repo: KB repository for listing entities.
        novel_id: Scope the lookup to this novel.

    Returns:
        Dict mapping lowercase entity name to envelope status string.
    """
    try:
        entries, _total = await kb_repo.list_entries(
            novel_id,
            page_size=500,
        )
    except Exception:
        logger.warning(
            "kb_status_lookup_failed",
            novel_id=str(novel_id),
            exc_info=True,
        )
        return {}

    status_map: dict[str, str] = {}
    for entry in entries:
        name = str(getattr(entry, "name", "") or "").strip()
        if not name:
            continue
        kb_status = str(getattr(entry, "status", "draft") or "draft")
        status_map[name.lower()] = _KB_STATUS_MAP.get(kb_status, "active")
    return status_map


def _enrich_character_refs(
    event: TimelineEvent,
    entity_status_map: dict[str, str],
) -> list[dict[str, str]]:
    """Enrich character_refs with KB entity status.

    Args:
        event: TimelineEvent with character_refs (list of dicts with id/name).
        entity_status_map: Name → status mapping from KB.

    Returns:
        List of dicts with id, name, and status keys.
    """
    result: list[dict[str, str]] = []
    for ref in event.character_refs or []:
        name = str(ref.get("name", ""))
        status = entity_status_map.get(name.lower(), "unknown")
        result.append(
            {
                "id": str(ref.get("id", "")),
                "name": name,
                "status": status,
            }
        )
    return result


def _enrich_location_ref(
    event: TimelineEvent,
    entity_status_map: dict[str, str],
) -> dict[str, str] | None:
    """Enrich location_ref with KB entity status.

    Args:
        event: TimelineEvent with optional location_ref dict.
        entity_status_map: Name → status mapping from KB.

    Returns:
        Dict with id, name, and status keys, or None.
    """
    if not event.location_ref:
        return None
    name = str(event.location_ref.get("name", ""))
    status = entity_status_map.get(name.lower(), "unknown")
    return {
        "id": str(event.location_ref.get("id", "")),
        "name": name,
        "status": status,
    }


def _build_kb_entity_status(
    event: TimelineEvent,
    entity_status_map: dict[str, str],
) -> dict[str, str]:
    """Build kb_entity_status mapping for the envelope.

    Combines character and location entity statuses into a single mapping
    keyed by entity name.

    Args:
        event: TimelineEvent with entity references.
        entity_status_map: Name → status mapping from KB.

    Returns:
        Dict mapping entity names to their KB status.
    """
    status: dict[str, str] = {}
    for ref in event.character_refs or []:
        name = str(ref.get("name", ""))
        if name and name.lower() in entity_status_map:
            status[name] = entity_status_map[name.lower()]
    if event.location_ref:
        name = str(event.location_ref.get("name", ""))
        if name and name.lower() in entity_status_map:
            status[name] = entity_status_map[name.lower()]
    return status


def _split_list_field(value: str) -> list[str]:
    """Split a comma-separated string into a list of stripped values.

    Args:
        value: Comma-separated string (e.g. causes, consequences).

    Returns:
        List of non-empty stripped strings.
    """
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]
