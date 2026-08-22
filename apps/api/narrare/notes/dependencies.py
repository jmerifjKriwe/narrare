# apps/api/narrare/notes/dependencies.py
"""Notes dependency injection factories — wiring only, no business logic."""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import SessionDep  # noqa: TC001 - needed at runtime for FastAPI DI

if TYPE_CHECKING:
    import uuid

    from narrare.notes.search_service import NoteSearchService
    from narrare.notes.service import NoteService
    from narrare.novels.repository import NovelRepository
    from narrare.series.repository import SeriesRepository


class _NovelOwnedLookup:
    """OwnedLinkLookupProtocol adapter over NovelRepository.get_by_id."""

    def __init__(self, repo: NovelRepository) -> None:
        self._repo = repo

    async def get_owned(self, entity_id: uuid.UUID, user_id: uuid.UUID) -> object | None:
        return await self._repo.get_by_id(entity_id, user_id)


class _SeriesOwnedLookup:
    """OwnedLinkLookupProtocol adapter — SeriesRepository.get has no user
    check, so ownership is compared here (wiring-level adapter, RULE-06).
    """

    def __init__(self, repo: SeriesRepository) -> None:
        self._repo = repo

    async def get_owned(self, entity_id: uuid.UUID, user_id: uuid.UUID) -> object | None:
        series = await self._repo.get(entity_id)
        if series is not None and series.user_id == user_id:
            return series
        return None


def get_note_service(session: SessionDep) -> NoteService:
    """Production wiring: NoteRepository + lookups + embedding dispatch/cleanup."""
    from narrare.embeddings.repository import EmbeddingRepository
    from narrare.embeddings.service import EmbeddingService
    from narrare.notes.embedding_dispatch import InProcessNoteEmbeddingDispatch
    from narrare.notes.repository import NoteRepository
    from narrare.notes.service import NoteService
    from narrare.novels.repository import NovelRepository
    from narrare.series.repository import SeriesRepository

    return NoteService(
        NoteRepository(session),
        novel_lookup=_NovelOwnedLookup(NovelRepository(session)),
        series_lookup=_SeriesOwnedLookup(SeriesRepository(session)),
        embedding_dispatch=InProcessNoteEmbeddingDispatch(),
        embedding_cleanup=EmbeddingService(EmbeddingRepository(session)),
    )


def get_note_search_service(session: SessionDep) -> NoteSearchService:
    """Production wiring for the search service (notes + embeddings repos)."""
    from narrare.embeddings.repository import EmbeddingRepository
    from narrare.notes.repository import NoteRepository
    from narrare.notes.search_service import NoteSearchService

    return NoteSearchService(NoteRepository(session), EmbeddingRepository(session))
