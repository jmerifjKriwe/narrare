"""Shared fakes for extraction-apply unit tests.

Extracted from test_apply_extraction.py per RULE-04 (file size limits) —
the fakes are shared by test_apply_extraction.py,
test_apply_extraction_resolution.py, and test_apply_extraction_advanced.py.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError


class _FakeEntry:
    """Minimal fake KB entry returned by FakeKBService."""

    def __init__(
        self,
        name: str,
        entity_type: str = "character",
        novel_id: UUID | None = None,
        metadata_: dict[str, object] | None = None,
    ) -> None:
        self.id = uuid4()
        self.name = name
        self.entity_type = entity_type
        self.novel_id = novel_id
        self.metadata_ = metadata_


class _FakeKBService:
    """Fake KBService that records creates and updates."""

    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []
        self.updated: list[dict[str, object]] = []
        self.fail_next_create = False
        self.fail_next_update = False
        self._entry_index: dict[UUID, _FakeEntry] = {}

    def seed(
        self, name: str, entity_type: str = "character", entry_id: UUID | None = None
    ) -> _FakeEntry:
        """Pre-populate an entity for update lookups."""
        entry = _FakeEntry(name=name, entity_type=entity_type)
        if entry_id is not None:
            entry.id = entry_id
        self._entry_index[entry.id] = entry
        return entry

    async def create(
        self,
        novel_id: UUID,
        user_id: UUID,
        data: object,
    ) -> _FakeEntry:
        if self.fail_next_create:
            self.fail_next_create = False
            msg = "KB service create failed"
            raise RuntimeError(msg)

        entry_name = getattr(data, "name", "Unknown")
        entry_type = getattr(data, "entity_type", "unknown")
        entry = _FakeEntry(name=entry_name, entity_type=entry_type)
        self.created.append(
            {
                "novel_id": novel_id,
                "user_id": user_id,
                "data": data,
                "entry_id": entry.id,
            },
        )
        return entry

    async def update(
        self,
        novel_id: UUID,
        entry_id: UUID,
        user_id: UUID,
        data: object,
    ) -> _FakeEntry:
        if self.fail_next_update:
            self.fail_next_update = False
            msg = "KB service update failed"
            raise RuntimeError(msg)

        existing = self._entry_index.get(entry_id)
        entry_name = existing.name if existing else "Updated"
        entry_type = existing.entity_type if existing else "character"
        entry = _FakeEntry(name=entry_name, entity_type=entry_type)
        self.updated.append(
            {
                "novel_id": novel_id,
                "target_entry_id": entry_id,
                "user_id": user_id,
                "data": data,
                "returned_entry_id": entry.id,
            },
        )
        return entry


class _FakeRelationshipRepo:
    """Fake RelationshipRepository that records creates.

    ``exists`` mirrors the production ``uq_kb_relationships_unique``
    constraint (source_id, target_id, rel_type) over the recorded
    creates; ``fail_on_rel_types`` injects an IntegrityError for
    selected predicates (batch-robustness regression tests).
    """

    def __init__(self) -> None:
        self.created: list[object] = []
        self.fail_on_rel_types: set[str] = set()

    async def create(self, rel: object) -> object:
        rel_type = getattr(rel, "rel_type", None)
        if rel_type in self.fail_on_rel_types:
            raise IntegrityError("INSERT", {}, Exception("uq_kb_relationships_unique"))
        self.created.append(rel)
        return rel

    async def exists(self, source_id: UUID, target_id: UUID, rel_type: str) -> bool:
        """True when an identical edge was already recorded in this fake."""
        return any(
            getattr(rel, "source_id", None) == source_id
            and getattr(rel, "target_id", None) == target_id
            and getattr(rel, "rel_type", None) == rel_type
            for rel in self.created
        )


class _FakeNestedSavepoint:
    """Savepoint stand-in: records rollback vs release, never suppresses.

    Mirrors ``AsyncSessionTransaction`` semantics the apply service
    relies on: an exception passing through the context manager rolls
    back only this savepoint (the outer session stays usable) and is
    re-raised.
    """

    def __init__(self, owner: _FakeApplySession) -> None:
        self._owner = owner
        self.rolled_back = False

    async def __aenter__(self) -> _FakeNestedSavepoint:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> bool:
        if exc_type is not None:
            self.rolled_back = True
            self._owner.rollbacks += 1
        return False


class _FakeApplySession:
    """Minimal AsyncSession stand-in exposing only ``begin_nested``.

    Records how many savepoints were begun and how many rolled back so
    the batch-robustness tests can verify per-item SAVEPOINT semantics
    without a real database.
    """

    def __init__(self) -> None:
        self.begun = 0
        self.rollbacks = 0

    def begin_nested(self) -> _FakeNestedSavepoint:
        self.begun += 1
        return _FakeNestedSavepoint(self)


class _FakeKBRepoForApply:
    """Fake KBRepositoryProtocol — name-based and ID-based entity lookup."""

    def __init__(self) -> None:
        self._entries: dict[str, _FakeEntry] = {}
        self._by_id: dict[UUID, _FakeEntry] = {}

    def seed(
        self,
        name: str,
        entity_type: str = "character",
        entry_id: UUID | None = None,
        novel_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> _FakeEntry:
        entry = _FakeEntry(
            name=name,
            entity_type=entity_type,
            novel_id=novel_id,
            metadata_=metadata,
        )
        if entry_id is not None:
            entry.id = entry_id
        self._entries[name.lower()] = entry
        self._by_id[entry.id] = entry
        return entry

    async def get_by_id(self, entry_id: UUID) -> _FakeEntry | None:
        return self._by_id.get(entry_id)

    async def get_by_name(self, novel_id: UUID, name: str) -> _FakeEntry | None:
        return self._entries.get(name.lower())

    # Stub to satisfy the KBRepositoryProtocol interface for extraction_service
    async def list_entries(
        self, *args: object, **kwargs: object
    ) -> tuple[list[dict[str, Any]], int]:
        return [], 0
