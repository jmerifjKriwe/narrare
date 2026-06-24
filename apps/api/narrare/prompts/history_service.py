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

import uuid
from typing import TYPE_CHECKING

import structlog

from narrare.prompts.history_mapping import (
    ACTIVE_TOKEN,
    content_hash,
    revision_to_response,
)
from narrare.prompts.schemas_prompt_history import (
    PromptHistoryClearedResponse,
    PromptHistoryListResponse,
    PromptHistoryScope,
    PromptRevisionCompareResponse,
    PromptRevisionRestoredResponse,
)
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from narrare.prompts.repository import PromptHistoryRepository
    from narrare.prompts.schemas import SaveOverrideRequest
    from narrare_core.prompts.management import PromptManagementService

logger = structlog.get_logger(__name__)


class PromptHistoryApiService:
    """Prompt History service implementing ``PromptHistoryServiceProtocol``."""

    def __init__(
        self,
        core: PromptManagementService,
        repo: PromptHistoryRepository,
        *,
        retention_limit: int,
    ) -> None:
        self._core = core
        self._repo = repo
        self._retention_limit = retention_limit

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

    async def _resolve_compare_side(
        self,
        prompt_id: str,
        side: str,
    ) -> tuple[str, str]:
        """Resolve a compare side to ``(content, source_label)``.

        ``side`` is either the literal ``"active"`` or a revision UUID string.
        """
        if side == ACTIVE_TOKEN:
            active = await self._active_content(prompt_id)
            if active is None:
                raise NotFoundError("Active override", identifier=prompt_id)
            return active, ACTIVE_TOKEN

        try:
            revision_id = uuid.UUID(side)
        except (ValueError, TypeError) as exc:
            raise NotFoundError("Prompt revision", identifier=side) from exc

        revision = await self._repo.get_revision(revision_id)
        if revision is None:
            raise NotFoundError("Prompt revision", identifier=side)
        return revision.content, revision.source

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

    async def compare_revisions(
        self,
        prompt_id: str,
        *,
        from_id: str,
        to_id: str,
        scope: PromptHistoryScope = PromptHistoryScope.PROJECT,
    ) -> PromptRevisionCompareResponse:
        """Compare two revisions (or the literal ``"active"``) by content."""
        from_content, from_source = await self._resolve_compare_side(prompt_id, from_id)
        to_content, to_source = await self._resolve_compare_side(prompt_id, to_id)

        return PromptRevisionCompareResponse(
            prompt_id=prompt_id,
            from_id=from_id,
            to_id=to_id,
            from_source=from_source,
            to_source=to_source,
            from_content=from_content,
            to_content=to_content,
        )

    async def restore_revision(
        self,
        prompt_id: str,
        revision_id: uuid.UUID,
        *,
        actor_id: uuid.UUID,
        scope: PromptHistoryScope = PromptHistoryScope.PROJECT,
    ) -> PromptRevisionRestoredResponse:
        """Append-only restore: write the active file + record a NEW revision."""
        revision = await self._repo.get_revision(revision_id)
        if revision is None:
            raise NotFoundError("Prompt revision", identifier=str(revision_id))

        # Capture the previous active hash (before overwrite) for the response.
        previous_active = await self._active_content(prompt_id)
        previous_active_hash = (
            content_hash(previous_active) if previous_active is not None else None
        )

        content = revision.content

        # 1. Write the active file (authoritative) with the revision's content.
        #    The core re-injects override_of_version; since the stored content
        #    already carries it, the write is effectively idempotent.
        await self._core.save_override(prompt_id, content)

        # 2. Record a NEW revision (append-only).  Restore recording is NOT
        #    best-effort: the action should surface errors so the user knows
        #    the revision was not recorded.  The file write already succeeded
        #    and remains authoritative.
        digest = content_hash(content)
        restored = await self._repo.insert_revision(
            prompt_id,
            scope.value,
            content=content,
            content_hash=digest,
            actor_id=actor_id,
            source="restore",
            restored_from_id=revision.id,
        )
        await self._repo.enforce_retention(
            prompt_id,
            scope.value,
            keep=self._retention_limit,
        )

        # The restored revision is now active (its content == the file content).
        return PromptRevisionRestoredResponse(
            prompt_id=prompt_id,
            restored_revision=revision_to_response(restored, active_hash=digest),
            active_content=content,
            previous_active_hash=previous_active_hash,
        )

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
