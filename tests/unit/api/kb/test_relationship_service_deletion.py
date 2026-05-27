"""Unit tests for RelationshipService — delete and inverse suggestion.

Tests RelationshipService.delete and get_inverse_suggestion
with validation rules (ownership, existence, known types).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.kb.relationship_service import RelationshipService
from narrare_core.shared.errors import NotFoundError

# ---------------------------------------------------------------------------
# Fake classes (mirrored from test_relationship_service.py for isolation)
# ---------------------------------------------------------------------------


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

    async def get_by_id(self, rel_id: object) -> FakeKBRelationship | None:
        return self._rels.get(rel_id)

    async def delete(self, rel: FakeKBRelationship) -> None:
        self._rels.pop(rel.id, None)

    def seed_rel(self, rel: FakeKBRelationship) -> None:
        self._rels[rel.id] = rel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service() -> tuple[RelationshipService, FakeEntryRepo, FakeRelRepo]:
    """Create a RelationshipService with fake dependencies."""
    entry_repo = FakeEntryRepo()
    rel_repo = FakeRelRepo()
    service = RelationshipService(
        rel_repo=rel_repo,  # type: ignore[arg-type]
        entry_repo=entry_repo,  # type: ignore[arg-type]
    )
    return service, entry_repo, rel_repo


# ---------------------------------------------------------------------------
# Tests: delete
# ---------------------------------------------------------------------------


class TestDelete:
    """Tests for RelationshipService.delete."""

    @pytest.mark.asyncio
    async def test_delete_happy_path(self) -> None:
        """Valid relationship is deleted."""
        service, entry_repo, rel_repo = _make_service()
        novel_id = uuid4()
        source = FakeKBEntry(novel_id=novel_id)
        entry_repo.seed(source)
        rel = FakeKBRelationship(source_id=source.id)
        rel_repo.seed_rel(rel)

        await service.delete(novel_id, rel.id, uuid4())  # type: ignore[arg-type]

        assert rel.id not in rel_repo._rels

    @pytest.mark.asyncio
    async def test_delete_relationship_not_found_raises(self) -> None:
        """Missing relationship raises NotFoundError."""
        service, _entry_repo, _rel_repo = _make_service()

        with pytest.raises(NotFoundError, match="KBRelationship"):
            await service.delete(uuid4(), uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_delete_wrong_novel_raises_not_found(self) -> None:
        """Source entry from different novel raises NotFoundError."""
        service, entry_repo, rel_repo = _make_service()
        wrong_novel = uuid4()
        other_novel = uuid4()
        source = FakeKBEntry(novel_id=other_novel)
        entry_repo.seed(source)
        rel = FakeKBRelationship(source_id=source.id)
        rel_repo.seed_rel(rel)

        with pytest.raises(NotFoundError, match="KBRelationship"):
            await service.delete(wrong_novel, rel.id, uuid4())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests: get_inverse_suggestion
# ---------------------------------------------------------------------------


class TestGetInverseSuggestion:
    """Tests for RelationshipService.get_inverse_suggestion."""

    def test_get_inverse_known_type_returns_inverse(self) -> None:
        """Known relationship type returns inverse suggestion."""
        service, _, _ = _make_service()

        result = service.get_inverse_suggestion("mentor")

        assert result == "mentee"

    def test_get_inverse_unknown_type_returns_none(self) -> None:
        """Unknown relationship type returns None."""
        service, _, _ = _make_service()

        result = service.get_inverse_suggestion("totally_custom_rel")

        assert result is None
