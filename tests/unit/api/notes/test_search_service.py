# tests/unit/api/notes/test_search_service.py
"""Unit tests for NoteSearchService — semantic + RULE-11 lexical fallback (§6a)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest

import narrare.notes.search_service as search_module
from narrare.notes.schemas import NoteSearchRequest
from narrare.notes.search_service import NoteSearchService
from narrare_core.notes.types import NoteType
from tests.factories import make_note
from tests.fakes.fake_notes_repository import FakeNotesRepository

if TYPE_CHECKING:
    from narrare.embeddings.contracts import EmbeddingRepositoryProtocol
    from narrare.embeddings.search_queries import SearchRow


class FakeEmbeddingRepo:
    """EmbeddingRepositoryProtocol.search double — canned rows keyed by marker."""

    def __init__(self, rows_by_marker: dict[float, list[tuple[UUID, float]]]) -> None:
        self._rows_by_marker = rows_by_marker
        self.calls: list[dict[str, object]] = []

    async def search(
        self,
        query_embedding: list[float],
        *,
        source_type: str | None = None,
        source_ids: set[UUID] | None = None,
        threshold: float = 0.7,
        limit: int = 20,
        model: str | None = None,
    ) -> list[SearchRow]:
        self.calls.append(
            {
                "source_type": source_type,
                "source_ids": source_ids,
                "limit": limit,
                "vector": query_embedding,
            }
        )
        from narrare.embeddings.models import Embedding
        from narrare.embeddings.search_queries import SearchRow as Row

        return [
            Row(
                embedding=Embedding(
                    id=uuid4(),
                    source_type="note",
                    source_id=sid,
                    content_hash="h",
                    embedding=[0.0],
                    model="m",
                    dimension=1,
                    generated_at=datetime.now(UTC),
                ),
                similarity=sim,
                usage_count=0,
                last_referenced_at=None,
            )
            for sid, sim in self._rows_by_marker.get(query_embedding[0], [])
        ]


async def _fake_embed(texts: list[str], *, model: str | None = None) -> list[list[float]]:
    # Marker 1.0 identifies the "magic" query; anything else maps to 0.0.
    marker = 1.0 if texts[0] == "magic" else 0.0
    return [[marker, 0.5]]


@pytest.fixture
def patched_embed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_module, "embed_texts", _fake_embed)


class TestSemanticSearch:
    async def test_returns_semantic_hits_ordered_by_similarity(self, patched_embed: None) -> None:
        user_id = uuid4()
        note_a = make_note(user_id=user_id, content="alpha")
        note_b = make_note(user_id=user_id, content="beta")
        repo = FakeNotesRepository([note_a, note_b])
        embedding_repo = FakeEmbeddingRepo({1.0: [(note_b.id, 0.9), (note_a.id, 0.8)]})
        service = NoteSearchService(repo, cast("EmbeddingRepositoryProtocol", embedding_repo))

        response = await service.search(note_a.user_id, NoteSearchRequest(query="magic"))

        assert response.mode == "semantic"
        assert [r.id for r in response.results] == [note_b.id, note_a.id]
        assert response.results[0].similarity == pytest.approx(0.9)

    async def test_filters_candidates_before_vector_search(self, patched_embed: None) -> None:
        user_id = uuid4()
        note_a = make_note(user_id=user_id, content="alpha", note_type="question")
        note_b = make_note(user_id=user_id, content="beta")
        repo = FakeNotesRepository([note_a, note_b])
        embedding_repo = FakeEmbeddingRepo({})
        service = NoteSearchService(repo, cast("EmbeddingRepositoryProtocol", embedding_repo))

        await service.search(
            note_a.user_id, NoteSearchRequest(query="magic", note_type=NoteType.QUESTION)
        )

        call = embedding_repo.calls[0]
        assert call["source_type"] == "note"
        assert call["source_ids"] == {note_a.id}


class TestLexicalFallback:
    async def test_embedding_failure_falls_back_to_lexical(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def _boom(texts: list[str], *, model: str | None = None) -> list[list[float]]:
            msg = "no provider"
            raise RuntimeError(msg)

        monkeypatch.setattr(search_module, "embed_texts", _boom)
        note = make_note(content="the aunt did it")
        repo = FakeNotesRepository([note])
        service = NoteSearchService(
            repo, cast("EmbeddingRepositoryProtocol", FakeEmbeddingRepo({}))
        )

        response = await service.search(note.user_id, NoteSearchRequest(query="aunt"))

        assert response.mode == "lexical"
        assert [r.id for r in response.results] == [note.id]
        assert response.results[0].similarity is None

    async def test_no_candidates_returns_empty_lexical(self, patched_embed: None) -> None:
        repo = FakeNotesRepository([])
        service = NoteSearchService(
            repo, cast("EmbeddingRepositoryProtocol", FakeEmbeddingRepo({}))
        )

        response = await service.search(uuid4(), NoteSearchRequest(query="magic"))

        assert response.mode == "lexical"
        assert response.results == []
