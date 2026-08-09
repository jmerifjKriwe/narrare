"""CR-AUFG-07-19 — ``PromptHistoryApiService``.

Composes the core file-based ``PromptManagementService`` (authoritative
cascade source) with the DB-backed ``PromptHistoryRepository`` (append-only
revision record).  RULE-08: core stays infra-free, so the history
orchestration lives at the backend boundary.

Key invariants:

* **File-first.** ``save_override_recorded`` writes the active override FILE
  via the core service before any DB work.  The file is the source of truth.
* **Best-effort record.** If the DB revision row cannot be persisted the
  failure is logged (RULE-11) but does NOT roll back or block the file write.
* **Dedup.** A revision is recorded only when its content hash differs from
  the most recent recorded revision (idempotent re-saves do not spam history).
* **Derived ``is_active``.** Never stored — at read time the current active
  file is hashed and compared against each revision's stored hash.
* **Append-only restore.** Restoring writes the active file and records a NEW
  revision (``source="restore"``, ``restored_from_id`` → original); the
  original row is never mutated.
* **Retention.** After each insert the configured ``retention_limit``
  revisions per ``(prompt_id, scope)`` are kept.

The canonical stored content + hash is the FILE content as written (including
the ``override_of_version`` frontmatter the core injects), read back via
``core.get_prompt``.  This keeps ``is_active`` derivation and the restore
round-trip consistent with the authoritative file.

Pure mapping helpers live in ``history_mapping.py`` (RULE-04 split).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.prompts._history_compare_mixin import HistoryCompareRestoreMixin
from narrare.prompts._wiki_prompt_event import (
    WIKI_PROMPT_CATEGORY_PREFIX,
    publish_wiki_prompt_changed,
)
from narrare.prompts.history_mapping import content_hash, revision_to_response
from narrare.prompts.schemas_prompt_history import (
    PromptHistoryClearedResponse,
    PromptHistoryListResponse,
    PromptHistoryScope,
)

if TYPE_CHECKING:
    import uuid

    from narrare.events.publisher import EventPublisher
    from narrare.prompts.repository import PromptHistoryRepository
    from narrare.prompts.schemas import SaveOverrideRequest
    from narrare_core.prompts.management import PromptManagementService

logger = structlog.get_logger(__name__)


class PromptHistoryApiService(HistoryCompareRestoreMixin):
    """Prompt History service implementing ``PromptHistoryServiceProtocol``."""

    def __init__(
        self,
        core: PromptManagementService,
        repo: PromptHistoryRepository,
        *,
        retention_limit: int,
        event_publisher: EventPublisher | None = None,
    ) -> None:
        self._core = core
        self._repo = repo
        self._retention_limit = retention_limit
        self._event_publisher = event_publisher

    # -- helpers -----------------------------------------------------------

    async def _active_content(self, prompt_id: str) -> str | None:
        """Return the active override FILE content, or ``None`` if none set.

        Only the override file counts as "active" for history purposes; the
        bundled default (no override) means no revision is active.
        """
        detail = await self._core.get_prompt(prompt_id)
        if detail is None or not detail.is_overridden:
            return None
        return detail.content

    # -- public API --------------------------------------------------------

    async def save_override_recorded(
        self,
        prompt_id: str,
        request: SaveOverrideRequest,
        *,
        actor_id: uuid.UUID,
        scope: PromptHistoryScope = PromptHistoryScope.PROJECT,
    ) -> None:
        """Write the active override file, then record a revision row.

        Order: file-first (authoritative), then DB row.  Dedup skips the row
        when the content hash matches the most recent recorded revision.  DB
        failures are logged but do not block the file write.
        """
        # 1. File write (authoritative cascade source).
        await self._core.save_override(prompt_id, request.content)

        # 2. Read back the canonical written content (includes the injected
        #    override_of_version frontmatter) so hashing matches the file.
        active_content = await self._active_content(prompt_id)
        if active_content is None:
            # Defensive: save succeeded so an override should exist.  If the
            # core returned not-overridden, we cannot derive canonical content
            # — log and skip recording rather than persist a wrong hash.
            logger.warning(
                "prompt_history_no_active_after_save",
                prompt_id=prompt_id,
            )
            return

        digest = content_hash(active_content)

        # 3. Dedup against the most recent recorded revision.
        latest = await self._repo.get_latest_revision(prompt_id, scope.value)
        if latest is not None and latest.content_hash == digest:
            logger.info(
                "prompt_history_dedup_skip",
                prompt_id=prompt_id,
                scope=scope.value,
            )
            return

        # Q-016: a wiki-category prompt override changes the wiki generation
        # prompt globally. Publish ``wiki.prompt.changed`` so the listener
        # marks wiki summaries stale for regeneration. Non-blocking (the
        # helper swallows publish failures — RULE-11). Only fires when content
        # genuinely changed (past the dedup check above).
        if self._event_publisher is not None and prompt_id.startswith(WIKI_PROMPT_CATEGORY_PREFIX):
            await publish_wiki_prompt_changed(self._event_publisher, prompt_id, digest)

        # 4. Best-effort DB record + retention.  Failure is non-fatal.
        try:
            await self._repo.insert_revision(
                prompt_id,
                scope.value,
                content=active_content,
                content_hash=digest,
                actor_id=actor_id,
                source="save",
                change_reason=request.change_reason,
            )
            await self._repo.enforce_retention(
                prompt_id,
                scope.value,
                keep=self._retention_limit,
            )
        except Exception as exc:
            logger.error(
                "prompt_history_record_failed",
                prompt_id=prompt_id,
                scope=scope.value,
                error=str(exc),
                exc_info=True,
            )

    async def list_history(
        self,
        prompt_id: str,
        *,
        scope: PromptHistoryScope = PromptHistoryScope.PROJECT,
        limit: int = 50,
        offset: int = 0,
    ) -> PromptHistoryListResponse:
        """List recorded revisions, newest first, with derived ``is_active``."""
        active_content = await self._active_content(prompt_id)
        active_hash = content_hash(active_content) if active_content is not None else None

        total = await self._repo.count(prompt_id, scope.value)
        revisions = await self._repo.list_revisions(
            prompt_id,
            scope.value,
            limit=limit,
            offset=offset,
        )

        return PromptHistoryListResponse(
            prompt_id=prompt_id,
            scope=scope,
            total=total,
            limit=limit,
            offset=offset,
            revisions=[revision_to_response(rev, active_hash=active_hash) for rev in revisions],
        )

    # compare_revisions / restore_revision live in HistoryCompareRestoreMixin
    # (RULE-04 split — see _history_compare_mixin.py).

    async def clear_history(
        self,
        prompt_id: str,
        *,
        scope: PromptHistoryScope = PromptHistoryScope.PROJECT,
    ) -> PromptHistoryClearedResponse:
        """Delete all history rows; the active override file is untouched."""
        deleted_count = await self._repo.delete_history(prompt_id, scope.value)
        return PromptHistoryClearedResponse(
            prompt_id=prompt_id,
            scope=scope,
            deleted_count=deleted_count,
        )
