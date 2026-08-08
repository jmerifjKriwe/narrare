"""Embedding lifecycle hooks for KB entries.

Handles content hash computation and embedding task dispatch on
KB entry create/update.  Non-blocking: failures are logged but
never prevent saves from completing (RULE-11).

Extracted from ``service.py`` to stay under RULE-04 file-size limits.
The ``_dispatch_task`` method launches the in-process embedding
coroutine via ``asyncio.create_task`` (ADR-080) and holds a strong
reference against garbage collection of the in-flight coroutine.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import structlog

from narrare.embeddings.tasks import run_embed_source_inprocess
from narrare_core.embeddings.hash import compute_content_hash
from narrare_core.events.types import DomainEvent, EventType

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.embeddings.contracts import EmbeddingRepositoryProtocol
    from narrare.kb.models import KBEntry
    from narrare_core.events.bus import EventBus

logger = structlog.get_logger(__name__)

#: Strong references to in-flight embedding coroutines, preventing the
#: garbage collector from cancelling a ``asyncio.create_task`` coroutine
#: that nothing else holds a reference to (ADR-080). Entries are removed
#: automatically via ``add_done_callback`` when the task completes.
_INFLIGHT_TASKS: set[asyncio.Task[None]] = set()


def _on_done(task: asyncio.Task[None]) -> None:
    """Done-callback for in-flight embedding tasks.

    Removes the task from the GC-guard set and retrieves any exception so
    asyncio does not emit an un-retrieved-exception warning (IMP-1). A
    surfaced failure is logged via structlog at error level (RULE-11): the
    inner runner already logs, but this guarantees a structured error signal
    even on the retry-exhaustion / premature-failure paths.
    """
    _INFLIGHT_TASKS.discard(task)
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("background_task_failed", error=str(exc), exc_info=exc)


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
        """Launch the ``embed_source`` in-process coroutine (ADR-080).

        Schedules ``run_embed_source_inprocess`` via ``asyncio.create_task``
        with JSON-serialisable arguments (the UUID is passed as a string,
        keeping the dispatch seam swappable). The coroutine builds its own DB
        session and recomputes the content hash internally for idempotency,
        so only the raw content is forwarded.

        A strong reference is held in the module-level ``_INFLIGHT_TASKS`` set
        to prevent the garbage collector from cancelling the in-flight
        coroutine; the reference is discarded automatically on completion
        (via ``_on_done``), which also retrieves any task exception so it is
        logged rather than surfacing as un-retrieved-exception noise (IMP-1).

        Fire-and-forget: the task is not awaited here.
        """
        source_type = "kb_entry"
        task = asyncio.create_task(run_embed_source_inprocess(source_type, str(source_id), content))
        _INFLIGHT_TASKS.add(task)
        task.add_done_callback(_on_done)
        logger.info(
            "embedding_task_dispatched",
            entry_id=str(source_id),
            source_type=source_type,
            trigger=trigger,
        )
