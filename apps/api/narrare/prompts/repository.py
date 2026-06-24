"""CR-AUFG-07-19 — ``PromptHistoryRepository`` (DB queries only, RULE-06).

Persistence layer for the append-only ``prompt_revisions`` table.  All
SQLAlchemy queries live here — the service never writes SQL directly
(RULE-07).  Retention is enforced here so the service can delegate the whole
write + prune step in one repository call.

The repository is agnostic to the file-based active override: it only reads
and writes revision rows.  ``is_active`` derivation (hashing the current file)
lives in the service, not here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, func, select

from narrare._app.base_repository import BaseRepository
from narrare.prompts.models import PromptRevision

if TYPE_CHECKING:
    import uuid


class PromptHistoryRepository(BaseRepository):
    """SQLAlchemy queries for the ``prompt_revisions`` table."""

    async def insert_revision(
        self,
        prompt_id: str,
        scope: str,
        *,
        content: str,
        content_hash: str,
        actor_id: uuid.UUID | None,
        source: str,
        change_reason: str | None = None,
        restored_from_id: uuid.UUID | None = None,
    ) -> PromptRevision:
        """Insert a single revision row and return the refreshed model.

        Args:
            prompt_id: Logical prompt identity (``{cat}/{lang}/{mode}``).
            scope: ``"project"`` or ``"user"``.
            content: The override content text captured at save time.
            content_hash: sha256 hex of ``content`` (computed by the caller).
            actor_id: User who triggered the revision (NULL for system saves).
            source: Provenance tag (``"save"``, ``"restore"``).
            change_reason: Optional human-readable reason.
            restored_from_id: Set when this row is an append-only restore.

        Returns:
            The persisted :class:`PromptRevision` with server defaults loaded.
        """
        revision = PromptRevision(
            prompt_id=prompt_id,
            scope=scope,
            content=content,
            content_hash=content_hash,
            actor_id=actor_id,
            source=source,
            change_reason=change_reason,
            restored_from_id=restored_from_id,
        )
        self._session.add(revision)
        await self._flush_and_refresh(revision)
        return revision

    async def list_revisions(
        self,
        prompt_id: str,
        scope: str,
        *,
        limit: int,
        offset: int,
    ) -> list[PromptRevision]:
        """List revisions for a prompt + scope, newest first.

        Args:
            prompt_id: Logical prompt identity.
            scope: ``"project"`` or ``"user"``.
            limit: Maximum rows to return.
            offset: Number of leading (newest) rows to skip.

        Returns:
            Revisions ordered by ``created_at`` descending.
        """
        stmt = (
            select(PromptRevision)
            .where(
                PromptRevision.prompt_id == prompt_id,
                PromptRevision.scope == scope,
            )
            .order_by(PromptRevision.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_revision(self, revision_id: uuid.UUID) -> PromptRevision | None:
        """Fetch a single revision by primary key.

        Args:
            revision_id: The revision UUID.

        Returns:
            The revision, or ``None`` if no such row exists.
        """
        stmt = select(PromptRevision).where(PromptRevision.id == revision_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_latest_revision(
        self,
        prompt_id: str,
        scope: str,
    ) -> PromptRevision | None:
        """Return the most recent revision for a prompt + scope.

        Used by the service for dedup (skip recording if the content hash
        matches the latest row).

        Args:
            prompt_id: Logical prompt identity.
            scope: ``"project"`` or ``"user"``.

        Returns:
            The newest revision, or ``None`` when no history exists.
        """
        stmt = (
            select(PromptRevision)
            .where(
                PromptRevision.prompt_id == prompt_id,
                PromptRevision.scope == scope,
            )
            .order_by(PromptRevision.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def count(self, prompt_id: str, scope: str) -> int:
        """Count revisions for a prompt + scope.

        Args:
            prompt_id: Logical prompt identity.
            scope: ``"project"`` or ``"user"``.

        Returns:
            Number of matching revision rows.
        """
        stmt = (
            select(func.count())
            .select_from(PromptRevision)
            .where(
                PromptRevision.prompt_id == prompt_id,
                PromptRevision.scope == scope,
            )
        )
        result = await self._session.execute(stmt)
        return int(result.scalar_one())

    async def delete_history(self, prompt_id: str, scope: str) -> int:
        """Delete all revisions for a prompt + scope.

        The active override file is untouched — clearing is history-only.

        Args:
            prompt_id: Logical prompt identity.
            scope: ``"project"`` or ``"user"``.

        Returns:
            Number of rows deleted.
        """
        existing = await self.count(prompt_id, scope)
        if existing == 0:
            return 0
        stmt = delete(PromptRevision).where(
            PromptRevision.prompt_id == prompt_id,
            PromptRevision.scope == scope,
        )
        await self._session.execute(stmt)
        await self._flush()
        return existing

    async def enforce_retention(
        self,
        prompt_id: str,
        scope: str,
        *,
        keep: int = 100,
    ) -> int:
        """Prune oldest revisions beyond ``keep`` for a prompt + scope.

        Resolves the IDs of the ``keep`` newest rows and deletes every other
        row for the identity.  The id-set approach is deterministic and immune
        to ``created_at`` ties (PostgreSQL ``now()`` is transaction-start, so
        rows saved in the same transaction can share a timestamp).  No-op when
        the row count is at or below ``keep``.

        Args:
            prompt_id: Logical prompt identity.
            scope: ``"project"`` or ``"user"``.
            keep: Maximum number of newest revisions to retain.

        Returns:
            Number of rows deleted.
        """
        total = await self.count(prompt_id, scope)
        if total <= keep:
            return 0

        # IDs of the ``keep`` newest rows to retain.
        keep_stmt = (
            select(PromptRevision.id)
            .where(
                PromptRevision.prompt_id == prompt_id,
                PromptRevision.scope == scope,
            )
            .order_by(PromptRevision.created_at.desc())
            .limit(keep)
        )
        keep_result = await self._session.execute(keep_stmt)
        keep_ids = set(keep_result.scalars().all())

        # Delete every row for the identity that is NOT among the retained set.
        delete_stmt = delete(PromptRevision).where(
            PromptRevision.prompt_id == prompt_id,
            PromptRevision.scope == scope,
            PromptRevision.id.not_in(keep_ids),
        )
        await self._session.execute(delete_stmt)
        await self._flush()
        # Deterministic: every non-retained row was deleted.
        return total - len(keep_ids)
