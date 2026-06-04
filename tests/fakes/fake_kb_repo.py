"""Fake KB repository for unit tests.

Replaces bare ``MagicMock`` with an in-memory implementation
for ``KBRepositoryProtocol``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tests.fakes._shared import CallRecord

if TYPE_CHECKING:
    import uuid

    from narrare.kb.models import KBEntry


class FakeKBRepository:
    """In-memory fake for ``KBRepositoryProtocol``.

    Stores KB entries keyed by ``entry_id``.
    """

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, KBEntry] = {}
        self.calls: list[CallRecord] = []
        self._return_values: dict[str, Any] = {}

    def configure(self, method: str, return_value: Any) -> None:
        """Configure a custom return value for the next call to *method*."""
        self._return_values[method] = return_value

    def seed(self, *entries: KBEntry) -> None:
        """Pre-populate the store."""
        for e in entries:
            self._store[e.id] = e

    async def get_by_id(self, entry_id: uuid.UUID) -> KBEntry | None:
        self.calls.append(CallRecord("get_by_id", kwargs={"entry_id": entry_id}))
        if "get_by_id" in self._return_values:
            return self._return_values.pop("get_by_id")
        return self._store.get(entry_id)

    async def create(self, entry: KBEntry) -> KBEntry:
        self.calls.append(CallRecord("create"))
        self._store[entry.id] = entry
        return entry

    async def get_by_slug(self, novel_id: uuid.UUID, slug: str) -> KBEntry | None:
        self.calls.append(CallRecord("get_by_slug"))
        if "get_by_slug" in self._return_values:
            return self._return_values.pop("get_by_slug")
        return None

    async def get_by_name(self, novel_id: uuid.UUID, name: str) -> KBEntry | None:
        self.calls.append(CallRecord("get_by_name"))
        return None

    async def search_by_name_prefix(
        self, novel_id: uuid.UUID, prefix: str, limit: int = 10
    ) -> list[KBEntry]:
        self.calls.append(CallRecord("search_by_name_prefix"))
        return []

    async def list_entries(
        self,
        novel_id: uuid.UUID,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[KBEntry], int]:
        self.calls.append(CallRecord("list_entries"))
        return [], 0

    async def update(self, entry: KBEntry, data: dict[str, object]) -> KBEntry:
        self.calls.append(CallRecord("update"))
        return entry

    async def delete(self, entry: KBEntry) -> None:
        self.calls.append(CallRecord("delete"))
        self._store.pop(entry.id, None)

    async def search(
        self,
        novel_id: uuid.UUID,
        query: str,
        entity_type: str | None = None,
        tags: list[str] | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[KBEntry], int]:
        self.calls.append(CallRecord("search"))
        return [], 0

    async def count_by_novel(self, novel_id: uuid.UUID) -> int:
        self.calls.append(CallRecord("count_by_novel"))
        return len(self._store)

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
