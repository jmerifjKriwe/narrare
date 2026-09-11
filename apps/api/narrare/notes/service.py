# apps/api/narrare/notes/service.py
"""Note service — business logic (NOTES-001).

Owns: tag normalization, scope validation (incl. merged PATCH state), link
ownership checks, embedding dispatch on create/update, embedding cleanup on
delete, and the core NoteSnapshot mapping for chat (§6b).
RULE-06: no SQL, no HTTP.

PATCH semantics (schema §5 — "explicit null clears a field"):
- ``title``/``novel_id``/``series_id`` null → clears the nullable column;
- ``content``/``tags`` null → clears to the empty value (columns are NOT NULL);
- ``note_type`` null → rejected with :class:`ValidationError` (a note must
  always have a type).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.notes.contracts import NoteSnapshot
from narrare_core.notes.types import effective_title, normalize_tags, validate_scope
from narrare_core.shared.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    import uuid

    from narrare.notes.contracts import (
        EmbeddingCleanupProtocol,
        NoteEmbeddingDispatchProtocol,
        NoteRepositoryProtocol,
        OwnedLinkLookupProtocol,
    )
    from narrare.notes.models import Note
    from narrare.notes.schemas import NoteCreateRequest, NoteUpdateRequest

logger = structlog.get_logger(__name__)


class NoteService:
    """Business logic for scratchpad notes.

    Implements ``NoteServiceProtocol`` (API contracts) and the core
    ``NoteLookupProtocol`` via :meth:`get_note_snapshot` (§6b).
    """

    def __init__(
        self,
        repo: NoteRepositoryProtocol,
        *,
        novel_lookup: OwnedLinkLookupProtocol | None = None,
        series_lookup: OwnedLinkLookupProtocol | None = None,
        embedding_dispatch: NoteEmbeddingDispatchProtocol | None = None,
        embedding_cleanup: EmbeddingCleanupProtocol | None = None,
    ) -> None:
        self._repo = repo
        self._novel_lookup = novel_lookup
        self._series_lookup = series_lookup
        self._embedding_dispatch = embedding_dispatch
        self._embedding_cleanup = embedding_cleanup

    async def get(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note:
        """Load a note, verifying ownership.

        Raises:
            NotFoundError: If the note does not exist or is not owned by the user.
        """
        note = await self._repo.get_by_id(note_id, user_id)
        if note is None:
            raise NotFoundError("Note", identifier=str(note_id))
        return note

    async def list_notes(
        self,
        user_id: uuid.UUID,
        *,
        note_type: str | None = None,
        tag: str | None = None,
        novel_id: uuid.UUID | None = None,
        series_id: uuid.UUID | None = None,
        q: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Note]:
        """Filtered list; filtering semantics live in the repository (RULE-06)."""
        return await self._repo.list_notes(
            user_id,
            note_type=note_type,
            tag=tag,
            novel_id=novel_id,
            series_id=series_id,
            q=q,
            limit=limit,
            offset=offset,
        )

    async def create(self, user_id: uuid.UUID, request: NoteCreateRequest) -> Note:
        """Create a note and dispatch embedding generation (fire-and-forget, §6a)."""
        validate_scope(request.novel_id, request.series_id)
        await self._validate_link(self._novel_lookup, "Novel", request.novel_id, user_id)
        await self._validate_link(self._series_lookup, "Series", request.series_id, user_id)
        note = await self._repo.create(
            user_id,
            title=request.title,
            content=request.content,
            note_type=request.note_type.value,
            tags=normalize_tags(request.tags),
            novel_id=request.novel_id,
            series_id=request.series_id,
        )
        await self._dispatch_embedding(note)
        logger.info("note_created", note_id=str(note.id))
        return note

    async def update(
        self, note_id: uuid.UUID, user_id: uuid.UUID, request: NoteUpdateRequest
    ) -> Note:
        """Partially update a note; re-embed only when title/content changed.

        The patch is derived from ``model_fields_set`` (explicitly provided
        fields only) and validated against the MERGED state — the stored note
        plus the patch — so e.g. setting ``series_id`` on a novel-linked note
        raises :class:`ScopeError` even though the request alone looks valid.
        """
        note = await self.get(note_id, user_id)
        fields_set = request.model_fields_set

        patch: dict[str, object] = {}
        if "title" in fields_set:
            patch["title"] = request.title
        if "content" in fields_set:
            # Explicit null clears NOT NULL columns to their empty value.
            patch["content"] = request.content or ""
        if "note_type" in fields_set:
            if request.note_type is None:
                msg = "note_type cannot be cleared — a note must always have a type"
                raise ValidationError(msg)
            patch["note_type"] = request.note_type.value
        if "tags" in fields_set:
            patch["tags"] = normalize_tags(request.tags or [])
        if "novel_id" in fields_set:
            patch["novel_id"] = request.novel_id
        if "series_id" in fields_set:
            patch["series_id"] = request.series_id

        merged_novel = request.novel_id if "novel_id" in fields_set else note.novel_id
        merged_series = request.series_id if "series_id" in fields_set else note.series_id
        validate_scope(merged_novel, merged_series)
        if "novel_id" in fields_set and merged_novel is not None:
            await self._validate_link(self._novel_lookup, "Novel", merged_novel, user_id)
        if "series_id" in fields_set and merged_series is not None:
            await self._validate_link(self._series_lookup, "Series", merged_series, user_id)

        content_changed = "content" in fields_set and patch["content"] != note.content
        title_changed = "title" in fields_set and patch["title"] != note.title
        updated = await self._repo.update(note, **patch)
        if content_changed or title_changed:
            await self._dispatch_embedding(updated)
        logger.info("note_updated", note_id=str(note_id))
        return updated

    async def delete(self, note_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Hard-delete a note and clean up its embeddings (§6a, no ghosts)."""
        note = await self.get(note_id, user_id)
        await self._repo.delete(note)
        if self._embedding_cleanup is not None:
            try:
                await self._embedding_cleanup.delete("note", note_id)
            except Exception:
                logger.warning("note_embedding_cleanup_failed", note_id=str(note_id), exc_info=True)
        logger.info("note_deleted", note_id=str(note_id))

    async def list_tags(self, user_id: uuid.UUID, q: str | None = None) -> list[str]:
        """Distinct existing tags for autocomplete (spec §5)."""
        return await self._repo.distinct_tags(user_id, q=q)

    async def get_note_snapshot(
        self, note_id: uuid.UUID, user_id: uuid.UUID
    ) -> NoteSnapshot | None:
        """Core NoteLookupProtocol implementation — consumed by chat (§6b).

        Returns ``None`` (not an error) when the note is missing or owned by
        another user: a snapshot lookup is a best-effort context enrichment.
        """
        note = await self._repo.get_by_id(note_id, user_id)
        if note is None:
            return None
        return NoteSnapshot(
            id=note.id,
            title=note.title or "",
            content=note.content,
            note_type=note.note_type,
            tags=list(note.tags or []),
        )

    async def _validate_link(
        self,
        lookup: OwnedLinkLookupProtocol | None,
        resource: str,
        entity_id: uuid.UUID | None,
        user_id: uuid.UUID,
    ) -> None:
        """A linked novel/series must exist AND belong to the user (ownership)."""
        if entity_id is None or lookup is None:
            return
        if await lookup.get_owned(entity_id, user_id) is None:
            raise NotFoundError(resource, identifier=str(entity_id))

    async def _dispatch_embedding(self, note: Note) -> None:
        """Fire-and-forget embedding dispatch; failures never block saves (RULE-11)."""
        if self._embedding_dispatch is None:
            return
        text = f"{effective_title(note.title, note.content)}\n{note.content}"
        try:
            await self._embedding_dispatch.dispatch(note.id, text)
        except Exception:
            logger.warning("note_embedding_dispatch_failed", note_id=str(note.id), exc_info=True)
