"""Embedding lifecycle hooks for KB entries.

Handles content hash computation and embedding task dispatch on
KB entry create/update.  Non-blocking: failures are logged but
never prevent saves from completing (RULE-11).

Extracted from ``service.py`` to stay under RULE-04 file-size limits.
The ``_dispatch_task`` method enqueues the registered ``embed_source``
task on the shared TaskIQ broker (INFRA-007).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.tasks.broker import broker
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

        Forwards the entry body to the embedding task dispatcher and
        publishes ``wiki.sync.requested`` for WikiSummary generation.

        Non-blocking: logs warning on failure (RULE-11).
        """
        try:
            content = entry.body or ""
            await self._dispatch_task(entry.id, content, trigger="create")
            # Skip wiki sync for Series-Canon entries (novel_id IS NULL).
            # Wiki sync is novel-scoped; Canon entries belong to a series, not
            # a novel. Series-scoped wiki sync is a future concern (Spec 2+).
            if entry.novel_id is None:
                return
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

            content = entry.body or ""
            content_hash = compute_content_hash(content)

            # Skip dispatch when content hash is unchanged (when a repo is
            # available for comparison). The embed_source task also performs
            # this idempotency check internally.
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

            await self._dispatch_task(entry.id, content, trigger="update")
            # Skip wiki sync for Series-Canon entries (novel_id IS NULL).
            # Wiki sync is novel-scoped; Canon entries belong to a series, not
            # a novel. Series-scoped wiki sync is a future concern (Spec 2+).
            if entry.novel_id is None:
                return
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
        content: str,
        *,
        trigger: str,
    ) -> None:
        """Enqueue the ``embed_source`` task via the TaskIQ broker.

        Looks up the registered ``embed_source`` task on the shared broker and
        enqueues it with JSON-serializable arguments (the UUID is passed as a
        string, as required across the TaskIQ process boundary). The task
        worker owns its own DB session and recomputes the content hash
        internally for idempotency, so only the raw content is forwarded.

        Non-blocking: a missing task registration is logged, not raised.
        """
        source_type = "kb_entry"
        task = broker.find_task("embed_source")
        if task is None:
            logger.warning(
                "embed_source_task_not_registered",
                source_type=source_type,
                source_id=str(source_id),
            )
            return
        await task.kiq(
            source_type=source_type,
            source_id=str(source_id),
            content=content,
        )
        logger.info(
            "embedding_task_queued",
            entry_id=str(source_id),
            source_type=source_type,
            trigger=trigger,
        )
