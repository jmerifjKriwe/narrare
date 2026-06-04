"""Fake relationship repository for unit tests.

Replaces bare ``MagicMock`` with an in-memory implementation
for ``RelationshipRepositoryProtocol``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    import uuid

    from narrare.kb.models import KBRelationship
    from narrare.kb.relationship_repository import RelationshipEdgeRow


class FakeRelationshipRepository:
    """In-memory fake for ``RelationshipRepositoryProtocol``."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, KBRelationship] = {}
        self.calls: list[CallRecord] = []
        self._return_values: dict[str, Any] = {}

    def configure(self, method: str, return_value: Any) -> None:
        """Configure a custom return value for the next call to *method*."""
        self._return_values[method] = return_value

    def seed(self, *rels: KBRelationship) -> None:
        for r in rels:
            self._store[r.id] = r

    async def create(self, rel: KBRelationship) -> KBRelationship:
        self.calls.append(CallRecord("create"))
        self._store[rel.id] = rel
        return rel

    async def get_by_id(self, rel_id: uuid.UUID) -> KBRelationship | None:
        self.calls.append(CallRecord("get_by_id", kwargs={"rel_id": rel_id}))
        return self._store.get(rel_id)

    async def list_for_entry(
        self,
        entry_id: uuid.UUID,
        direction: str | None = None,
    ) -> list[KBRelationship]:
        self.calls.append(
            CallRecord("list_for_entry", kwargs={"entry_id": entry_id, "direction": direction})
        )
        if "list_for_entry" in self._return_values:
            return self._return_values.pop("list_for_entry")
        return []

    async def delete(self, rel: KBRelationship) -> None:
        self.calls.append(CallRecord("delete"))
        self._store.pop(rel.id, None)

    async def exists(self, source_id: uuid.UUID, target_id: uuid.UUID, rel_type: str) -> bool:
        self.calls.append(CallRecord("exists"))
        return False

    async def list_all_for_novel(self, novel_id: uuid.UUID) -> list[KBRelationship]:
        self.calls.append(CallRecord("list_all_for_novel"))
        return []

    async def get_adjacency_map(
        self,
        novel_id: uuid.UUID,
        entity_ids: set[uuid.UUID] | None = None,
    ) -> dict[str, set[str]]:
        self.calls.append(CallRecord("get_adjacency_map"))
        return {}

    async def get_relationships_with_names(
        self,
        novel_id: uuid.UUID,
        entity_ids: set[uuid.UUID] | None = None,
    ) -> list[RelationshipEdgeRow]:
        self.calls.append(CallRecord("get_relationships_with_names"))
        return []

    # ------------------------------------------------------------------
    # Assertion helpers
    # ------------------------------------------------------------------

    def call_count(self, method: str) -> int:
        return sum(1 for c in self.calls if c.method == method)

    def assert_called_once(self, method: str) -> None:
        count = self.call_count(method)
        if count != 1:
            raise AssertionError(f"Expected 1 call to {method}, got {count}")

    def assert_not_called(self, method: str) -> None:
        count = self.call_count(method)
        if count > 0:
            raise AssertionError(f"Expected 0 calls to {method}, got {count}")
