"""Unit tests for RelationshipService — KB relationship business logic.

Tests create, list_for_entry, delete, and get_inverse_suggestion
with validation rules (no self-ref, uniqueness, entry ownership).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest

from narrare.kb.relationship_service import RelationshipService
from narrare.kb.schemas import KBRelationshipCreate
from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol

# ---------------------------------------------------------------------------
# Fake classes
# ---------------------------------------------------------------------------


class FakeKBEntry:
    """Minimal stand-in for KBEntry with fields needed by RelationshipService."""

    def __init__(
        self,
        *,
        id: object | None = None,
        novel_id: object | None = None,
        name: str = "Test",
        entity_type: str = "character",
    ) -> None:
        self.id = id if id is not None else uuid4()
        self.novel_id = novel_id if novel_id is not None else uuid4()
        self.name = name
        self.entity_type = entity_type


class FakeKBRelationship:
    """Minimal stand-in for KBRelationship."""

    def __init__(
        self,
        *,
        id: object | None = None,
        source_id: object | None = None,
        target_id: object | None = None,
        rel_type: str = "ally",
        label: str | None = None,
        direction: str = "directed",
    ) -> None:
        self.id = id if id is not None else uuid4()
        self.source_id = source_id if source_id is not None else uuid4()
        self.target_id = target_id if target_id is not None else uuid4()
        self.rel_type = rel_type
        self.label = label
        self.direction = direction


class FakeEntryRepo:
    """In-memory fake for KBRepositoryProtocol (entry lookups only)."""

    def __init__(self, entries: dict[object, FakeKBEntry] | None = None) -> None:
        self._entries: dict[object, FakeKBEntry] = entries or {}

    async def get_by_id(self, entry_id: object) -> FakeKBEntry | None:
        return self._entries.get(entry_id)

    def seed(self, entry: FakeKBEntry) -> None:
        self._entries[entry.id] = entry


class FakeRelRepo:
    """In-memory fake for RelationshipRepositoryProtocol."""

    def __init__(self) -> None:
        self._rels: dict[object, FakeKBRelationship] = {}
        self._exists_flag = False

    async def create(self, rel: FakeKBRelationship) -> FakeKBRelationship:
        self._rels[rel.id] = rel
        return rel

    async def get_by_id(self, rel_id: object) -> FakeKBRelationship | None:
        return self._rels.get(rel_id)

    async def list_for_entry(
        self,
        entry_id: object,
        direction: str | None = None,
    ) -> list[FakeKBRelationship]:
        return [
            r for r in self._rels.values() if r.source_id == entry_id or r.target_id == entry_id
        ]

    async def delete(self, rel: FakeKBRelationship) -> None:
        self._rels.pop(rel.id, None)

    async def exists(
        self,
        source_id: object,
        target_id: object,
        rel_type: str,
    ) -> bool:
        return self._exists_flag

    def seed_rel(self, rel: FakeKBRelationship) -> None:
        self._rels[rel.id] = rel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(
    *,
    rel_exists: bool = False,
) -> tuple[RelationshipService, FakeEntryRepo, FakeRelRepo]:
    """Create a RelationshipService with fake dependencies.

    The novel gate is permissive (IDOR S10): every caller owns the novel.
    The ownership matrix lives in
    ``test_relationship_dismissed_extraction_ownership.py``.
    """
    from ._test_fakes import FakeNovelRepo

    entry_repo = FakeEntryRepo()
    rel_repo = FakeRelRepo()
    rel_repo._exists_flag = rel_exists

    service = RelationshipService(
        rel_repo=cast("RelationshipRepositoryProtocol", rel_repo),
        entry_repo=cast("KBRepositoryProtocol", entry_repo),
        novel_repo=cast("NovelRepositoryProtocol", FakeNovelRepo()),
    )
    return service, entry_repo, rel_repo


def _make_create_data(
    *,
    source_id: UUID | None = None,
    target_id: UUID | None = None,
    rel_type: str = "ally",
) -> KBRelationshipCreate:
    return KBRelationshipCreate(
        source_id=source_id or uuid4(),
        target_id=target_id or uuid4(),
        rel_type=rel_type,
    )


# ---------------------------------------------------------------------------
# Tests: create
# ---------------------------------------------------------------------------


class TestCreate:
    """Tests for RelationshipService.create validation and creation."""

    @pytest.mark.asyncio
    async def test_create_happy_path_creates_relationship(self) -> None:
        """Valid source and target entries create relationship."""
        service, entry_repo, _rel_repo = _make_service()
        novel_id = uuid4()
        user_id = uuid4()
        source = FakeKBEntry(novel_id=novel_id)
        target = FakeKBEntry(novel_id=novel_id)
        entry_repo.seed(source)
        entry_repo.seed(target)

        data = _make_create_data(
            source_id=cast("UUID", source.id), target_id=cast("UUID", target.id)
        )
        result = await service.create(novel_id, user_id, data)

        assert result.source_id == source.id
        assert result.target_id == target.id

    @pytest.mark.asyncio
    async def test_create_source_not_found_raises_not_found(self) -> None:
        """Missing source entry raises NotFoundError."""
        service, _entry_repo, _rel_repo = _make_service()
        novel_id = uuid4()
        user_id = uuid4()

        data = _make_create_data(source_id=uuid4(), target_id=uuid4())

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.create(novel_id, user_id, data)

    @pytest.mark.asyncio
    async def test_create_target_not_found_raises_not_found(self) -> None:
        """Missing target entry raises NotFoundError."""
        service, entry_repo, _rel_repo = _make_service()
        novel_id = uuid4()
        user_id = uuid4()
        source = FakeKBEntry(novel_id=novel_id)
        entry_repo.seed(source)

        data = _make_create_data(source_id=cast("UUID", source.id), target_id=uuid4())

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.create(novel_id, user_id, data)

    @pytest.mark.asyncio
    async def test_create_self_reference_raises_validation(self) -> None:
        """Source_id == target_id raises ValidationError."""
        service, entry_repo, _rel_repo = _make_service()
        novel_id = uuid4()
        user_id = uuid4()
        entry = FakeKBEntry(novel_id=novel_id)
        entry_repo.seed(entry)

        data = _make_create_data(source_id=cast("UUID", entry.id), target_id=cast("UUID", entry.id))

        with pytest.raises(ValidationError, match="Self-referencing"):
            await service.create(novel_id, user_id, data)

    @pytest.mark.asyncio
    async def test_create_duplicate_raises_conflict(self) -> None:
        """Duplicate relationship raises ConflictError."""
        service, entry_repo, _rel_repo = _make_service(rel_exists=True)
        novel_id = uuid4()
        user_id = uuid4()
        source = FakeKBEntry(novel_id=novel_id)
        target = FakeKBEntry(novel_id=novel_id)
        entry_repo.seed(source)
        entry_repo.seed(target)

        data = _make_create_data(
            source_id=cast("UUID", source.id), target_id=cast("UUID", target.id)
        )

        with pytest.raises(ConflictError, match="already exists"):
            await service.create(novel_id, user_id, data)


# ---------------------------------------------------------------------------
# Tests: list_for_entry
# ---------------------------------------------------------------------------


class TestListForEntry:
    """Tests for RelationshipService.list_for_entry."""

    @pytest.mark.asyncio
    async def test_list_for_entry_happy_path(self) -> None:
        """Valid entry returns relationships."""
        service, entry_repo, rel_repo = _make_service()
        novel_id = uuid4()
        entry = FakeKBEntry(novel_id=novel_id)
        entry_repo.seed(entry)
        rel = FakeKBRelationship(source_id=entry.id, target_id=uuid4())
        rel_repo.seed_rel(rel)

        result = await service.list_for_entry(novel_id, cast("UUID", entry.id), uuid4())

        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_for_entry_not_found_raises(self) -> None:
        """Missing entry raises NotFoundError."""
        service, _entry_repo, _rel_repo = _make_service()
        novel_id = uuid4()

        with pytest.raises(NotFoundError, match="KBEntry"):
            await service.list_for_entry(novel_id, uuid4(), uuid4())
