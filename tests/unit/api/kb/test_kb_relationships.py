"""Unit tests for KB RelationshipService — create, list, delete relationships.

Tests validation logic: entry ownership, self-reference, uniqueness.
Repositories are faked — no DB.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from narrare.kb.models import KBEntry, KBRelationship
from narrare.kb.schemas import KBRelationshipCreate
from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError

# ---------------------------------------------------------------------------
# Fake repositories
# ---------------------------------------------------------------------------


class FakeEntryRepo:
    """Fake KBRepositoryProtocol implementation."""

    def __init__(self) -> None:
        self._entries: dict[uuid.UUID, KBEntry] = {}

    def seed(self, *entries: KBEntry) -> None:
        for e in entries:
            self._entries[e.id] = e

    async def get_by_id(self, entry_id: uuid.UUID) -> KBEntry | None:
        return self._entries.get(entry_id)


class FakeRelRepo:
    """Fake RelationshipRepositoryProtocol implementation."""

    def __init__(self) -> None:
        self._rels: list[KBRelationship] = []
        self._existing: set[tuple[uuid.UUID, uuid.UUID, str]] = set()

    def seed(self, *rels: KBRelationship) -> None:
        for r in rels:
            self._rels.append(r)
            self._existing.add((r.source_id, r.target_id, r.rel_type))

    async def create(self, rel: KBRelationship) -> KBRelationship:
        self._rels.append(rel)
        self._existing.add((rel.source_id, rel.target_id, rel.rel_type))
        return rel

    async def get_by_id(self, rel_id: uuid.UUID) -> KBRelationship | None:
        for r in self._rels:
            if r.id == rel_id:
                return r
        return None

    async def list_for_entry(
        self,
        entry_id: uuid.UUID,
        direction: str | None = None,
    ) -> list[KBRelationship]:
        return [r for r in self._rels if r.source_id == entry_id or r.target_id == entry_id]

    async def delete(self, rel: KBRelationship) -> None:
        self._rels = [r for r in self._rels if r.id != rel.id]

    async def exists(self, source_id: uuid.UUID, target_id: uuid.UUID, rel_type: str) -> bool:
        return (source_id, target_id, rel_type) in self._existing


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def novel_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def entry_repo() -> FakeEntryRepo:
    return FakeEntryRepo()


@pytest.fixture
def rel_repo() -> FakeRelRepo:
    return FakeRelRepo()


@pytest.fixture
def service(entry_repo: FakeEntryRepo, rel_repo: FakeRelRepo) -> Any:
    from narrare.kb.relationship_service import RelationshipService

    return RelationshipService(
        rel_repo=rel_repo,  # type: ignore[arg-type]
        entry_repo=entry_repo,  # type: ignore[arg-type]
    )


def _make_entry(novel_id: uuid.UUID, **overrides: Any) -> KBEntry:
    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "novel_id": novel_id,
        "entity_type": "character",
        "name": "Anna",
        "slug": "anna",
        "status": "canon",
    }
    defaults.update(overrides)
    entry = KBEntry(**defaults)
    return entry


# ---------------------------------------------------------------------------
# create
# ---------------------------------------------------------------------------


class TestCreateRelationship:
    async def test_create_relationship_successfully(
        self,
        service: Any,
        entry_repo: FakeEntryRepo,
        rel_repo: FakeRelRepo,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        source = _make_entry(novel_id, name="Anna", slug="anna")
        target = _make_entry(
            novel_id, name="Berlin", entity_type="location", slug="berlin", id=uuid.uuid4()
        )
        entry_repo.seed(source, target)

        data = KBRelationshipCreate(
            source_id=source.id,
            target_id=target.id,
            rel_type="lives_in",
            label="Lives in Berlin",
        )

        result = await service.create(novel_id, user_id, data)

        assert isinstance(result, KBRelationship)
        assert result.source_id == source.id
        assert result.target_id == target.id
        assert result.rel_type == "lives_in"

    async def test_create_rejects_source_not_found(
        self,
        service: Any,
        entry_repo: FakeEntryRepo,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        target = _make_entry(novel_id, name="Berlin", entity_type="location", slug="berlin")
        entry_repo.seed(target)

        data = KBRelationshipCreate(
            source_id=uuid.uuid4(),
            target_id=target.id,
            rel_type="lives_in",
        )

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.create(novel_id, user_id, data)

    async def test_create_rejects_target_not_found(
        self,
        service: Any,
        entry_repo: FakeEntryRepo,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        source = _make_entry(novel_id, name="Anna", slug="anna")
        entry_repo.seed(source)

        data = KBRelationshipCreate(
            source_id=source.id,
            target_id=uuid.uuid4(),
            rel_type="lives_in",
        )

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.create(novel_id, user_id, data)

    async def test_create_rejects_self_reference(
        self,
        service: Any,
        entry_repo: FakeEntryRepo,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        entry = _make_entry(novel_id, name="Anna", slug="anna")
        entry_repo.seed(entry)

        data = KBRelationshipCreate(
            source_id=entry.id,
            target_id=entry.id,
            rel_type="ally",
        )

        with pytest.raises(ValidationError, match="Self-referencing"):
            await service.create(novel_id, user_id, data)

    async def test_create_rejects_duplicate(
        self,
        service: Any,
        entry_repo: FakeEntryRepo,
        rel_repo: FakeRelRepo,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        source = _make_entry(novel_id, name="Anna", slug="anna")
        target = _make_entry(
            novel_id, name="Berlin", entity_type="location", slug="berlin", id=uuid.uuid4()
        )
        entry_repo.seed(source, target)

        # Pre-seed the existing relationship
        existing = KBRelationship(
            source_id=source.id,
            target_id=target.id,
            rel_type="lives_in",
        )
        rel_repo.seed(existing)

        data = KBRelationshipCreate(
            source_id=source.id,
            target_id=target.id,
            rel_type="lives_in",
        )

        with pytest.raises(ConflictError, match="already exists"):
            await service.create(novel_id, user_id, data)

    async def test_create_rejects_source_wrong_novel(
        self,
        service: Any,
        entry_repo: FakeEntryRepo,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        other_novel = uuid.uuid4()
        source = _make_entry(other_novel, name="Anna", slug="anna")
        target = _make_entry(
            novel_id, name="Berlin", entity_type="location", slug="berlin", id=uuid.uuid4()
        )
        entry_repo.seed(source, target)

        data = KBRelationshipCreate(
            source_id=source.id,
            target_id=target.id,
            rel_type="lives_in",
        )

        with pytest.raises(NotFoundError):
            await service.create(novel_id, user_id, data)


# ---------------------------------------------------------------------------
# list_for_entry
# ---------------------------------------------------------------------------


class TestListForEntry:
    async def test_get_relationships_for_entity(
        self,
        service: Any,
        entry_repo: FakeEntryRepo,
        rel_repo: FakeRelRepo,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        source = _make_entry(novel_id, name="Anna", slug="anna")
        target = _make_entry(
            novel_id, name="Berlin", entity_type="location", slug="berlin", id=uuid.uuid4()
        )
        entry_repo.seed(source, target)

        rel = KBRelationship(
            source_id=source.id,
            target_id=target.id,
            rel_type="lives_in",
        )
        rel_repo.seed(rel)

        result = await service.list_for_entry(novel_id, source.id, user_id)

        assert len(result) == 1
        assert result[0].rel_type == "lives_in"

    async def test_list_for_entry_raises_not_found(
        self,
        service: Any,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        with pytest.raises(NotFoundError):
            await service.list_for_entry(novel_id, uuid.uuid4(), user_id)


# ---------------------------------------------------------------------------
# delete
# ---------------------------------------------------------------------------


class TestDeleteRelationship:
    async def test_delete_relationship_successfully(
        self,
        service: Any,
        entry_repo: FakeEntryRepo,
        rel_repo: FakeRelRepo,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        source = _make_entry(novel_id, name="Anna", slug="anna")
        target = _make_entry(
            novel_id, name="Berlin", entity_type="location", slug="berlin", id=uuid.uuid4()
        )
        entry_repo.seed(source, target)

        rel = KBRelationship(
            source_id=source.id,
            target_id=target.id,
            rel_type="lives_in",
        )
        rel_repo.seed(rel)

        await service.delete(novel_id, rel.id, user_id)

        # Verify relationship is gone
        remaining = await rel_repo.list_for_entry(source.id)
        assert len(remaining) == 0

    async def test_delete_raises_not_found_for_missing_rel(
        self,
        service: Any,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        with pytest.raises(NotFoundError, match="KBRelationship"):
            await service.delete(novel_id, uuid.uuid4(), user_id)


# ---------------------------------------------------------------------------
# get_inverse_suggestion
# ---------------------------------------------------------------------------


class TestGetInverseSuggestion:
    def test_returns_inverse_for_known_type(self, service: Any) -> None:
        result = service.get_inverse_suggestion("mentor")
        assert result == "mentee"

    def test_returns_none_for_unknown_type(self, service: Any) -> None:
        result = service.get_inverse_suggestion("unknown_type")
        assert result is None
