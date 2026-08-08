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

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.embeddings.contracts import EmbeddingRepositoryProtocol
    from narrare.kb.models import KBEntry

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

    Non-blocking: failures are logged but never prevent saves
    from completing (RULE-11).

    Args:
        embedding_repo: Optional repository for hash lookups.
            When provided, update hooks compare content hashes
            to avoid unnecessary task dispatches.
    """

    def __init__(
        self,
        embedding_repo: EmbeddingRepositoryProtocol | None = None,
    ) -> None:
        self._repo = embedding_repo

    async def on_entry_created(self, entry: KBEntry) -> None:
        """Queue embedding generation after creation.

        Forwards the entry body to the embedding task dispatcher.

        Non-blocking: logs warning on failure (RULE-11).
        """
        try:
            content = entry.body or ""
            await self._dispatch_task(entry.id, content, trigger="create")
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
        """Queue embedding generation after update if content changed.

        Computes new content hash and compares with stored hash (when
        embedding repo is available). Skips dispatch if hashes match.

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
        except Exception:
            logger.warning(
                "embedding_queue_failed",
                entry_id=str(entry.id),
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
