"""Embedding lifecycle hooks for KB entries.

Handles content hash computation and embedding task dispatch on
KB entry create/update.  Non-blocking: failures are logged but
never prevent saves from completing (RULE-11).

Extracted from ``service.py`` to stay under RULE-04 file-size limits.
When the TaskIQ broker is fully wired up, the ``_dispatch_task`` method
will call ``run_embed_source`` via the broker instead of just logging.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.embeddings.hash import compute_content_hash
from narrare_core.events.types import DomainEvent, EventType

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.embeddings.contracts import EmbeddingRepositoryProtocol
    from narrare.kb.models import KBEntry
    from narrare_core.events.bus import EventBus

logger = structlog.get_logger(__name__)


class EmbeddingHookManager:
    """Manages embedding hooks for KB entry lifecycle events.

    Computes content hashes and dispatches embedding tasks.
    Uses hash comparison on update to skip redundant embeddings.
    Publishes ``wiki.sync.requested`` events when content changes
    to trigger WikiSummary regeneration (WIKI-001).

    Non-blocking: failures are logged but never prevent saves
    from completing (RULE-11).

    Args:
        embedding_repo: Optional repository for hash lookups.
            When provided, update hooks compare content hashes
            to avoid unnecessary task dispatches.
        event_bus: Optional event bus for publishing wiki sync events.
            When provided, publishes ``wiki.sync.requested``
            on content change.
    """

    def __init__(
        self,
        embedding_repo: EmbeddingRepositoryProtocol | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._repo = embedding_repo
        self._event_bus = event_bus

    async def on_entry_created(self, entry: KBEntry) -> None:
        """Queue embedding generation and publish wiki sync event after creation.

        Computes content hash, dispatches embedding task, and publishes
        ``wiki.sync.requested`` for WikiSummary generation.

        Non-blocking: logs warning on failure (RULE-11).
        """
        try:
            content_hash = compute_content_hash(entry.body or "")
            await self._dispatch_task(entry.id, content_hash, trigger="create")
            await self._publish_wiki_sync_event(entry.id, entry.novel_id)
        except Exception:
            logger.warning(
                "embedding_queue_failed",
                entry_id=str(entry.id),
                exc_info=True,
            )

    async def on_entry_updated(
        self,
        entry: KBEntry,
        *,
        content_changed: bool,
    ) -> None:
        """Queue embedding generation and publish wiki sync after update if content changed.

        Computes new content hash and compares with stored hash (when
        embedding repo is available). Skips dispatch if hashes match.
        Publishes ``wiki.sync.requested`` only when content actually changed.

        Non-blocking: logs warning on failure (RULE-11).
        """
        try:
            if not content_changed:
                return

            content_hash = compute_content_hash(entry.body or "")

            # Check hash comparison if embedding repo is available
            if self._repo is not None:
                existing = await self._repo.get_by_source(
                    "kb_entry",
                    entry.id,
                )
                if existing is not None and existing.content_hash == content_hash:
                    logger.info(
                        "embedding_skipped_unchanged",
                        entry_id=str(entry.id),
                    )
                    return

            await self._dispatch_task(entry.id, content_hash, trigger="update")
            await self._publish_wiki_sync_event(entry.id, entry.novel_id)
        except Exception:
            logger.warning(
                "embedding_queue_failed",
                entry_id=str(entry.id),
                exc_info=True,
            )

    async def _publish_wiki_sync_event(
        self,
        entity_id: UUID,
        novel_id: UUID,
    ) -> None:
        """Publish a ``wiki.sync.requested`` event (non-blocking, RULE-11).

        Failure to publish is logged but never raised — the main
        save flow must not be blocked by event infrastructure issues.

        Args:
            entity_id: The KB entry that changed.
            novel_id: The novel the entity belongs to.
        """
        if self._event_bus is None:
            return

        try:
            event = DomainEvent(
                event_type=EventType.WIKI_SYNC_REQUESTED,
                aggregate_id=entity_id,
                payload={
                    "entity_id": str(entity_id),
                    "novel_id": str(novel_id),
                },
            )
            await self._event_bus.publish(event)
            logger.info(
                "wiki_sync_event_published",
                entity_id=str(entity_id),
                novel_id=str(novel_id),
            )
        except Exception:
            logger.warning(
                "wiki_sync_event_failed",
                entity_id=str(entity_id),
                novel_id=str(novel_id),
                exc_info=True,
            )

    async def _dispatch_task(
        self,
        source_id: UUID,
        content_hash: str,
        *,
        trigger: str,
    ) -> None:
        """Dispatch an embedding generation task.

        Currently logs the task. When TaskIQ is wired up, this will
        call ``run_embed_source`` via the broker.
        """
        logger.info(
            "embedding_task_queued",
            entry_id=str(source_id),
            source_type="kb_entry",
            content_hash=content_hash,
            trigger=trigger,
        )
