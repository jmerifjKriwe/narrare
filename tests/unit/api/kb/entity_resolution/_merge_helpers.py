"""Shared fakes for the merge-executor unit tests (ADR-085 P4, spec §6).

Extracted from ``test_merge_executor.py`` per RULE-04 (file-size limits) —
mirrors the ``_router_helpers.py`` / ``_apply_extraction_helpers.py``
pattern. The fakes stand in for ``KBRepository``, ``RelationshipRepository``,
and the ``AsyncSession`` savepoint seam; ``_FakeRelRepo.exists`` mirrors the
production ``uq_kb_relationships_unique`` shape (source, target, rel_type).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

from narrare.kb.entity_resolution.merge_executor import MergeExecutor
from narrare.kb.entity_resolution.schemas_resolution import MergePlan

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository

NOVEL = uuid4()
USER = uuid4()
SUGGESTION_ID = "0123456789abcdef"


class _FakeEntry:
    """Minimal KBEntry stand-in exposing the columns the executor touches."""

    def __init__(
        self,
        *,
        name: str,
        metadata: dict[str, object] | None = None,
        status: str = "reviewed",
        novel_id: UUID | None = NOVEL,
        created_at: datetime | None = None,
    ) -> None:
        self.id = uuid4()
        self.novel_id = novel_id
        self.name = name
        self.status = status
        self.metadata_ = dict(metadata or {})
        self.embeddings_dirty = False
        self.created_at = created_at or datetime.now(tz=UTC)


class _FakeEdge:
    """Minimal KBRelationship stand-in (uq shape: source/target/rel_type)."""

    def __init__(self, *, source_id: UUID, target_id: UUID, rel_type: str = "ally") -> None:
        self.id = uuid4()
        self.source_id = source_id
        self.target_id = target_id
        self.rel_type = rel_type


class _FakeKBRepo:
    def __init__(self) -> None:
        self.entries: dict[UUID, _FakeEntry] = {}
        self.updates: list[tuple[UUID, dict[str, object]]] = []

    def seed(self, entry: _FakeEntry) -> _FakeEntry:
        self.entries[entry.id] = entry
        return entry

    async def get_by_id(self, entry_id: UUID) -> _FakeEntry | None:
        return self.entries.get(entry_id)

    async def update(self, entry: _FakeEntry, data: dict[str, object]) -> _FakeEntry:
        for field, value in data.items():
            setattr(entry, field, value)
        self.updates.append((entry.id, dict(data)))
        return entry


class _FakeRelRepo:
    """Fake RelationshipRepository; ``exists`` mirrors ``uq_kb_relationships_unique``."""

    def __init__(self) -> None:
        self.edges: list[_FakeEdge] = []
        self.updates: list[tuple[UUID, dict[str, object]]] = []
        self.fail_next_update = False

    def add_edge(self, source_id: UUID, target_id: UUID, rel_type: str = "ally") -> _FakeEdge:
        edge = _FakeEdge(source_id=source_id, target_id=target_id, rel_type=rel_type)
        self.edges.append(edge)
        return edge

    async def list_for_entry(self, entry_id: UUID, direction: str | None = None) -> list[_FakeEdge]:
        return [e for e in self.edges if entry_id in (e.source_id, e.target_id)]

    async def exists(self, source_id: UUID, target_id: UUID, rel_type: str) -> bool:
        return any(
            e.source_id == source_id and e.target_id == target_id and e.rel_type == rel_type
            for e in self.edges
        )

    async def update(self, rel: _FakeEdge, data: dict[str, object]) -> _FakeEdge:
        if self.fail_next_update:
            self.fail_next_update = False
            msg = "edge update failed"
            raise RuntimeError(msg)
        for field, value in data.items():
            setattr(rel, field, value)
        self.updates.append((rel.id, dict(data)))
        return rel


class _FakeSavepoint:
    """Savepoint stand-in: counts rollback, never suppresses (apply-flow pattern)."""

    def __init__(self, owner: _FakeSession) -> None:
        self._owner = owner

    async def __aenter__(self) -> _FakeSavepoint:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> bool:
        if exc_type is not None:
            self._owner.rollbacks += 1
        return False


class _FakeSession:
    """Minimal AsyncSession stand-in exposing only ``begin_nested``."""

    def __init__(self) -> None:
        self.begun = 0
        self.rollbacks = 0

    def begin_nested(self) -> _FakeSavepoint:
        self.begun += 1
        return _FakeSavepoint(self)


class _World:
    """Seeded fakes plus a MergeExecutor wired over a survivor/loser pair."""

    def __init__(self, *, survivor: _FakeEntry, loser: _FakeEntry) -> None:
        self.survivor = survivor
        self.loser = loser
        self.kb_repo = _FakeKBRepo()
        self.kb_repo.seed(survivor)
        self.kb_repo.seed(loser)
        self.rel_repo = _FakeRelRepo()
        self.session = _FakeSession()
        self.executor = MergeExecutor(
            kb_repo=cast("KBRepository", self.kb_repo),
            rel_repo=cast("RelationshipRepository", self.rel_repo),
            session=cast("AsyncSession", self.session),
        )

    def plan(self, *, result_name: str | None = None, confidence: float | None = 0.91) -> MergePlan:
        return MergePlan(
            survivor_id=self.survivor.id,
            loser_id=self.loser.id,
            suggestion_id=SUGGESTION_ID,
            confidence=confidence,
            result_name=result_name,
        )


def _world(
    *,
    survivor: _FakeEntry | None = None,
    loser: _FakeEntry | None = None,
) -> _World:
    """Default pair: survivor "Anna Meyer" ← loser "Anna" (the §4 worked example)."""
    return _World(
        survivor=survivor or _FakeEntry(name="Anna Meyer"),
        loser=loser or _FakeEntry(name="Anna"),
    )
