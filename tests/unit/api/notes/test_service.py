"""Unit tests for NoteService — business rules with fakes (NOTES-001 §6a/§6b)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from narrare.notes.schemas import NoteCreateRequest, NoteUpdateRequest
from narrare.notes.service import NoteService
from narrare_core.notes.contracts import NoteSnapshot
from narrare_core.notes.types import ScopeError
from narrare_core.shared.errors import NotFoundError, ValidationError
from tests.factories import make_note
from tests.fakes.fake_notes_repository import FakeNotesRepository


class FakeDispatch:
    """NoteEmbeddingDispatchProtocol double — records dispatches, never fails."""

    def __init__(self) -> None:
        self.calls: list[tuple[UUID, str]] = []

    async def dispatch(self, note_id: UUID, text: str) -> None:
        self.calls.append((note_id, text))


class FailingDispatch:
    """NoteEmbeddingDispatchProtocol double — always raises (RULE-11 path)."""

    async def dispatch(self, note_id: UUID, text: str) -> None:
        msg = "boom"
        raise RuntimeError(msg)


class FakeCleanup:
    """EmbeddingCleanupProtocol double — records deletions."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, UUID]] = []

    async def delete(self, source_type: str, source_id: UUID) -> None:
        self.calls.append((source_type, source_id))


class FailingCleanup:
    """EmbeddingCleanupProtocol double — always raises (RULE-11 path)."""

    async def delete(self, source_type: str, source_id: UUID) -> None:
        msg = "cleanup boom"
        raise RuntimeError(msg)


class FakeOwnedLookup:
    """OwnedLinkLookupProtocol double — only the listed ids are 'owned'."""

    def __init__(self, *owned: UUID) -> None:
        self._owned = set(owned)

    async def get_owned(self, entity_id: UUID, user_id: UUID) -> object | None:
        return object() if entity_id in self._owned else None


def _service(
    *,
    novel_ids: tuple[UUID, ...] = (),
    series_ids: tuple[UUID, ...] = (),
) -> tuple[NoteService, FakeNotesRepository, FakeDispatch, FakeCleanup]:
    repo = FakeNotesRepository()
    dispatch = FakeDispatch()
    cleanup = FakeCleanup()
    service = NoteService(
        repo,
        novel_lookup=FakeOwnedLookup(*novel_ids),
        series_lookup=FakeOwnedLookup(*series_ids),
        embedding_dispatch=dispatch,
        embedding_cleanup=cleanup,
    )
    return service, repo, dispatch, cleanup


class TestGet:
    async def test_get_returns_owned_note(self) -> None:
        service, repo, _, _ = _service()
        note = make_note()
        repo.seed(note)
        assert await service.get(note.id, note.user_id) is note

    async def test_get_missing_note_raises_not_found(self) -> None:
        service, _, _, _ = _service()
        with pytest.raises(NotFoundError):
            await service.get(uuid4(), uuid4())


class TestListNotes:
    async def test_list_notes_delegates_filters_to_repository(self) -> None:
        service, repo, _, _ = _service()
        user_id = uuid4()
        repo.seed(make_note(user_id=user_id, note_type="idea"))
        repo.seed(make_note(user_id=user_id, note_type="question"))
        result = await service.list_notes(user_id, note_type="question")
        assert [n.note_type for n in result] == ["question"]


class TestCreate:
    async def test_create_dispatches_embedding_with_title_plus_content(self) -> None:
        service, _, dispatch, _ = _service()
        user_id = uuid4()
        request = NoteCreateRequest(title="Twist", content="The aunt did it")
        note = await service.create(user_id, request)
        assert dispatch.calls == [(note.id, "Twist\nThe aunt did it")]

    async def test_create_uses_content_fallback_title_when_untitled(self) -> None:
        service, _, dispatch, _ = _service()
        note = await service.create(uuid4(), NoteCreateRequest(content="First line\nrest"))
        # embedding text = effective title + "\n" + content
        assert dispatch.calls == [(note.id, "First line\nFirst line\nrest")]

    async def test_normalizes_tags_before_persisting(self) -> None:
        service, _, _, _ = _service()
        note = await service.create(
            uuid4(), NoteCreateRequest(content="x", tags=["Plot", "plot", " world "])
        )
        assert note.tags == ["plot", "world"]

    async def test_unknown_novel_link_raises_not_found(self) -> None:
        service, _, _, _ = _service()  # no ids owned
        with pytest.raises(NotFoundError):
            await service.create(uuid4(), NoteCreateRequest(content="x", novel_id=uuid4()))

    async def test_unknown_series_link_raises_not_found(self) -> None:
        service, _, _, _ = _service()  # no ids owned
        with pytest.raises(NotFoundError):
            await service.create(uuid4(), NoteCreateRequest(content="x", series_id=uuid4()))

    async def test_dispatch_failure_does_not_block_create(self) -> None:
        repo = FakeNotesRepository()
        service = NoteService(repo, embedding_dispatch=FailingDispatch())
        note = await service.create(uuid4(), NoteCreateRequest(content="x"))
        assert note.content == "x"
        assert repo.created == [note]


class TestUpdate:
    async def test_reembeds_when_content_changes(self) -> None:
        service, repo, dispatch, _ = _service()
        note = make_note()
        repo.seed(note)
        await service.update(note.id, note.user_id, NoteUpdateRequest(content="new body"))
        assert dispatch.calls and dispatch.calls[-1][1].endswith("new body")

    async def test_reembeds_when_title_changes(self) -> None:
        service, repo, dispatch, _ = _service()
        note = make_note(title="old")
        repo.seed(note)
        await service.update(note.id, note.user_id, NoteUpdateRequest(title="new"))
        assert dispatch.calls and dispatch.calls[-1][1].startswith("new")

    async def test_no_dispatch_when_content_unchanged(self) -> None:
        service, repo, dispatch, _ = _service()
        note = make_note(content="stable")
        repo.seed(note)
        await service.update(note.id, note.user_id, NoteUpdateRequest(tags=[]))
        assert dispatch.calls == []

    async def test_explicit_null_clears_link(self) -> None:
        service, repo, _, _ = _service()
        note = make_note(novel_id=uuid4())
        repo.seed(note)
        updated = await service.update(note.id, note.user_id, NoteUpdateRequest(novel_id=None))
        assert updated.novel_id is None

    async def test_explicit_null_note_type_rejected(self) -> None:
        """A note must always have a type — DB column is NOT NULL (T5 review)."""
        service, repo, _, _ = _service()
        note = make_note()
        repo.seed(note)
        with pytest.raises(ValidationError, match="note_type"):
            await service.update(note.id, note.user_id, NoteUpdateRequest(note_type=None))

    async def test_explicit_null_tags_clears_to_empty_list(self) -> None:
        service, repo, _, _ = _service()
        note = make_note(tags=["plot"])
        repo.seed(note)
        updated = await service.update(note.id, note.user_id, NoteUpdateRequest(tags=None))
        assert updated.tags == []

    async def test_explicit_null_content_clears_to_empty_string(self) -> None:
        service, repo, _, _ = _service()
        note = make_note(content="body")
        repo.seed(note)
        updated = await service.update(note.id, note.user_id, NoteUpdateRequest(content=None))
        assert updated.content == ""

    async def test_merged_scope_conflict_raises(self) -> None:
        """PATCH series_id onto a novel-linked note conflicts (T5 review, Important)."""
        service, repo, _, _ = _service()
        note = make_note(novel_id=uuid4())
        repo.seed(note)
        with pytest.raises(ScopeError, match="not both"):
            await service.update(note.id, note.user_id, NoteUpdateRequest(series_id=uuid4()))

    async def test_merged_scope_conflict_when_setting_novel_on_series_note(self) -> None:
        """Mirror case: PATCH novel_id onto a series-linked note conflicts too."""
        service, repo, _, _ = _service()
        note = make_note(series_id=uuid4())
        repo.seed(note)
        with pytest.raises(ScopeError, match="not both"):
            await service.update(note.id, note.user_id, NoteUpdateRequest(novel_id=uuid4()))

    async def test_scope_switch_with_both_patch_fields_succeeds(self) -> None:
        """Clearing series and setting novel in ONE patch is a valid switch."""
        novel_id = uuid4()
        service, repo, _, _ = _service(novel_ids=(novel_id,))
        note = make_note(series_id=uuid4())
        repo.seed(note)
        updated = await service.update(
            note.id, note.user_id, NoteUpdateRequest(novel_id=novel_id, series_id=None)
        )
        assert updated.novel_id == novel_id
        assert updated.series_id is None

    async def test_update_unknown_novel_link_raises_not_found(self) -> None:
        service, repo, _, _ = _service()  # no ids owned
        note = make_note()
        repo.seed(note)
        with pytest.raises(NotFoundError):
            await service.update(note.id, note.user_id, NoteUpdateRequest(novel_id=uuid4()))

    async def test_update_missing_note_raises_not_found(self) -> None:
        service, _, _, _ = _service()
        with pytest.raises(NotFoundError):
            await service.update(uuid4(), uuid4(), NoteUpdateRequest(content="x"))


class TestDelete:
    async def test_deletes_note_and_cleans_embeddings(self) -> None:
        service, repo, _, cleanup = _service()
        note = make_note()
        repo.seed(note)
        await service.delete(note.id, note.user_id)
        assert repo.deleted == [note]
        assert cleanup.calls == [("note", note.id)]

    async def test_missing_note_raises_not_found(self) -> None:
        service, _, _, _ = _service()
        with pytest.raises(NotFoundError):
            await service.delete(uuid4(), uuid4())

    async def test_cleanup_failure_does_not_block_delete(self) -> None:
        repo = FakeNotesRepository()
        service = NoteService(repo, embedding_cleanup=FailingCleanup())
        note = make_note()
        repo.seed(note)
        await service.delete(note.id, note.user_id)
        assert repo.deleted == [note]


class TestSnapshot:
    async def test_get_note_snapshot_maps_orm_to_core_snapshot(self) -> None:
        service, repo, _, _ = _service()
        note = make_note(title=None, content="Derived title\nbody", tags=["plot"])
        repo.seed(note)
        snapshot = await service.get_note_snapshot(note.id, note.user_id)
        assert isinstance(snapshot, NoteSnapshot)
        assert snapshot.note_type == note.note_type
        assert snapshot.display_title == "Derived title"

    async def test_get_note_snapshot_none_for_other_user(self) -> None:
        service, repo, _, _ = _service()
        note = make_note()
        repo.seed(note)
        assert await service.get_note_snapshot(note.id, uuid4()) is None

    async def test_get_note_snapshot_none_for_missing_note(self) -> None:
        service, _, _, _ = _service()
        assert await service.get_note_snapshot(uuid4(), uuid4()) is None


class TestListTags:
    async def test_delegates_to_repository(self) -> None:
        service, repo, _, _ = _service()
        note = make_note(tags=["alpha", "beta"])
        repo.seed(note)
        assert await service.list_tags(note.user_id) == ["alpha", "beta"]
