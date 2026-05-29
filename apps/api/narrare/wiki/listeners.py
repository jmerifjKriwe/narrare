"""Event listeners connecting domain events to wiki summary regeneration.

Handles KB entity changes, chapter finalization, prompt updates, and
wiki sync requests.  Debounces rapid-fire events and gracefully logs
all failures without propagating exceptions (RULE-11).
"""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any

import structlog

from narrare.wiki.tasks import (
    run_wiki_generate_chapter,
    run_wiki_generate_entity,
    run_wiki_mark_all_stale,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from narrare_core.events.types import DomainEvent

logger = structlog.get_logger(__name__)

_DEBOUNCE_WINDOW_S = 1.0
_DEBOUNCE_TTL_S = 60.0


def _uuid_from_payload(payload: dict[str, Any], key: str) -> uuid.UUID | None:
    """Extract and validate a UUID from an event payload. Returns None on failure."""
    raw = payload.get(key, "")
    try:
        return uuid.UUID(raw) if raw else None
    except ValueError, TypeError:
        return None


class WikiEventListener:
    """Routes domain events to wiki background tasks.

    Debounces rapid-fire events and logs all failures without raising (RULE-11).

    Args:
        wiki_service_factory: Zero-arg callable returning an ``APIWikiService``.
    """

    def __init__(self, wiki_service_factory: Callable[[], Any]) -> None:
        self._factory = wiki_service_factory
        self._recent_events: dict[str, float] = {}

    def _is_debounced(self, event_type: str, entity_id: str) -> bool:
        """Return True if this event was processed within the debounce window."""
        key = f"{event_type}:{entity_id}"
        now = time.monotonic()
        last_seen = self._recent_events.get(key)
        if last_seen is not None and (now - last_seen) < _DEBOUNCE_WINDOW_S:
            return True
        self._recent_events[key] = now
        # Evict stale entries to prevent unbounded growth.
        cutoff = now - _DEBOUNCE_TTL_S
        self._recent_events = {k: ts for k, ts in self._recent_events.items() if ts >= cutoff}
        return False

    async def on_kb_entry_updated(self, event: DomainEvent) -> None:
        """Handle ``kb.entry.updated`` — regenerate entity wiki + mark related stale."""
        entity_id = _uuid_from_payload(event.payload, "entity_id")
        novel_id = _uuid_from_payload(event.payload, "novel_id")
        if entity_id is None or novel_id is None:
            logger.warning("wiki_listener_invalid_payload", event_type=str(event.event_type))
            return

        log = logger.bind(event_type=str(event.event_type), entity_id=str(entity_id))

        if self._is_debounced(str(event.event_type), str(entity_id)):
            log.debug("wiki_listener_debounced")
            return

        try:
            await run_wiki_generate_entity(entity_id, novel_id, wiki_service_factory=self._factory)
        except Exception:
            log.exception("wiki_listener_entity_failed")

        # Cross-entity staleness: mark summaries that reference this entity.
        try:
            svc = self._factory()
            count = await svc.mark_related_stale(entity_id)
            if count > 0:
                log.info("wiki_related_marked_stale", related_count=count)
        except Exception:
            log.exception("wiki_listener_related_stale_failed")

    async def on_chapter_finalized(self, event: DomainEvent) -> None:
        """Handle ``chapter.finalized`` — generate chapter wiki summary."""
        chapter_id = _uuid_from_payload(event.payload, "chapter_id")
        novel_id = _uuid_from_payload(event.payload, "novel_id")
        if chapter_id is None or novel_id is None:
            logger.warning("wiki_listener_invalid_payload", event_type=str(event.event_type))
            return
        try:
            await run_wiki_generate_chapter(
                chapter_id, novel_id, wiki_service_factory=self._factory
            )
        except Exception:
            logger.exception("wiki_listener_chapter_failed", chapter_id=str(chapter_id))

    async def on_wiki_prompt_changed(self, event: DomainEvent) -> None:
        """Handle ``wiki.prompt.changed`` — mark all summaries stale."""
        novel_id = _uuid_from_payload(event.payload, "novel_id")
        prompt_version = event.payload.get("prompt_version", "")
        if novel_id is None:
            logger.warning("wiki_listener_invalid_payload", event_type=str(event.event_type))
            return
        try:
            count = await run_wiki_mark_all_stale(
                novel_id, prompt_version, wiki_service_factory=self._factory
            )
            logger.info("wiki_listener_prompt_changed", novel_id=str(novel_id), stale_count=count)
        except Exception:
            logger.exception("wiki_listener_prompt_change_failed", novel_id=str(novel_id))

    async def on_wiki_sync_requested(self, event: DomainEvent) -> None:
        """Handle ``wiki.sync.requested`` — generate entity wiki summary."""
        entity_id = _uuid_from_payload(event.payload, "entity_id")
        novel_id = _uuid_from_payload(event.payload, "novel_id")
        if entity_id is None or novel_id is None:
            logger.warning("wiki_listener_invalid_payload", event_type=str(event.event_type))
            return
        try:
            await run_wiki_generate_entity(entity_id, novel_id, wiki_service_factory=self._factory)
        except Exception:
            logger.exception("wiki_listener_sync_failed", entity_id=str(entity_id))
