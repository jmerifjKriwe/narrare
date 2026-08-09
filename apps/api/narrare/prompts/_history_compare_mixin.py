"""Compare & restore mixin for ``PromptHistoryApiService`` (RULE-04 split).

Holds the read-side revision operations: resolving a compare side,
comparing two revisions, and the append-only restore. Extracted from
``history_service.py`` to respect the file-size hard limit.

The mixin relies on host-provided collaborators:

* ``self._active_content(prompt_id)`` — active override file content (or None)
* ``self._core`` — the core ``PromptManagementService`` (authoritative files)
* ``self._repo`` — the DB-backed ``PromptHistoryRepository``
* ``self._retention_limit`` — revisions to keep per ``(prompt_id, scope)``
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from narrare.prompts.history_mapping import (
    ACTIVE_TOKEN,
    content_hash,
    revision_to_response,
)
from narrare.prompts.schemas_prompt_history import (
    PromptHistoryScope,
    PromptRevisionCompareResponse,
    PromptRevisionRestoredResponse,
)
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from narrare.prompts.repository import PromptHistoryRepository
    from narrare_core.prompts.management import PromptManagementService


class HistoryCompareRestoreMixin:
    """Compare & restore revision operations (mixed into PromptHistoryApiService).

    Relies on host-provided collaborators (declared for type checkers):
    ``_core``, ``_repo``, ``_retention_limit``, and the ``_active_content``
    method — all assigned/implemented by :class:`PromptHistoryApiService`.
    """

    if TYPE_CHECKING:
        _core: PromptManagementService
        _repo: PromptHistoryRepository
        _retention_limit: int

    async def _active_content(self, prompt_id: str) -> str | None:
        """Return the active override FILE content, or ``None`` if none set.

        Implemented by the host class (``PromptHistoryApiService``).
        """
        raise NotImplementedError

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
