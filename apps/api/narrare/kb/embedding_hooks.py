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

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.embeddings.contracts import EmbeddingRepositoryProtocol
    from narrare.kb.models import KBEntry

logger = structlog.get_logger(__name__)


class EmbeddingHookManager:
    """Manages embedding hooks for KB entry lifecycle events.

    Computes content hashes and dispatches embedding tasks.
    Uses hash comparison on update to skip redundant embeddings.

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
        """Queue embedding generation after entry creation.

        Computes content hash and dispatches embedding task.
        Non-blocking: logs warning on failure.
        """
        try:
            content_hash = compute_content_hash(entry.body or "")
            await self._dispatch_task(entry.id, content_hash, trigger="create")
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
        """Queue embedding generation after entry update if content changed.

        Computes new content hash and compares with stored hash (when
        embedding repo is available). Skips dispatch if hashes match.

        Non-blocking: logs warning on failure.
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
        except Exception:
            logger.warning(
                "embedding_queue_failed",
                entry_id=str(entry.id),
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
