# apps/api/narrare/notes/contracts.py
"""Notes service contracts (RULE-03) — protocols only, no logic (NOTES-001)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid

    from narrare.notes.models import Note
    from narrare.notes.schemas import NoteCreateRequest, NoteUpdateRequest


@runtime_checkable
class NoteRepositoryProtocol(Protocol):
    async def get_by_id(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note | None: ...

    async def get_many_by_ids(self, note_ids: set[uuid.UUID], user_id: uuid.UUID) -> list[Note]: ...

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
    ) -> list[Note]: ...

    async def create(
        self,
        user_id: uuid.UUID,
        *,
        title: str | None,
        content: str,
        note_type: str,
        tags: list[str],
        novel_id: uuid.UUID | None,
        series_id: uuid.UUID | None,
    ) -> Note: ...

    async def update(self, note: Note, **patch: object) -> Note: ...

    async def delete(self, note: Note) -> None: ...

    async def distinct_tags(self, user_id: uuid.UUID, *, q: str | None = None) -> list[str]: ...


@runtime_checkable
class OwnedLinkLookupProtocol(Protocol):
    """Ownership check for an optional novel/series link.

    Implemented by thin adapters in ``narrare.notes.dependencies``; returns
    the entity when it exists AND belongs to the user, else ``None``.
    """

    async def get_owned(self, entity_id: uuid.UUID, user_id: uuid.UUID) -> object | None: ...


@runtime_checkable
class NoteEmbeddingDispatchProtocol(Protocol):
    """Fire-and-forget embedding dispatch (ADR-080 in-process pattern, §6a)."""

    async def dispatch(self, note_id: uuid.UUID, text: str) -> None: ...


@runtime_checkable
class EmbeddingCleanupProtocol(Protocol):
    """Deletes embeddings for a source (spec §6a: no ghost embeddings).

    Structurally satisfied by ``narrare.embeddings.service.EmbeddingService.delete``.
    """

    async def delete(self, source_type: str, source_id: uuid.UUID) -> None: ...


@runtime_checkable
class NoteServiceProtocol(Protocol):
    async def get(self, note_id: uuid.UUID, user_id: uuid.UUID) -> Note: ...

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
    ) -> list[Note]: ...

    async def create(self, user_id: uuid.UUID, request: NoteCreateRequest) -> Note: ...

    async def update(
        self, note_id: uuid.UUID, user_id: uuid.UUID, request: NoteUpdateRequest
    ) -> Note: ...

    async def delete(self, note_id: uuid.UUID, user_id: uuid.UUID) -> None: ...

    async def list_tags(self, user_id: uuid.UUID, q: str | None = None) -> list[str]: ...
