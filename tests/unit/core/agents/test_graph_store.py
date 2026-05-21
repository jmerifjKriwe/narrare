"""Tests für GraphStateStore Protocol.

Test-Strategie:
- Protocol ist runtime_checkable → isinstance-Prüfung
- Mock-Implementierung testet das Contract-Verhalten
- Keine echten DB/LLM-Calls
"""

from __future__ import annotations

import pytest

from narrare_core.agents.graph_store import GraphStateStore


class TestGraphStateStoreProtocol:
    """GraphStateStore is a Protocol — runtime_checkable."""

    def test_is_runtime_checkable(self) -> None:
        """Das Protocol kann per isinstance() geprüft werden."""
        assert hasattr(GraphStateStore, "__instancecheck__")


class MockGraphStateStore:
    """Minimaler Mock für Tests."""

    def __init__(self) -> None:
        self.saves: list[tuple[str, object]] = []
        self.loaded: str | None = None
        self.deleted: str | None = None

    async def save(self, run_id: str, state: object) -> None:
        self.saves.append((run_id, state))

    async def load(self, run_id: str) -> object | None:
        self.loaded = run_id
        return None

    async def delete(self, run_id: str) -> None:
        self.deleted = run_id


class TestMockGraphStateStore:
    """MockGraphStateStore erfüllt das GraphStateStore Protocol."""

    def test_mock_is_protocol_compliant(self) -> None:
        store = MockGraphStateStore()
        assert isinstance(store, GraphStateStore)

    @pytest.mark.asyncio
    async def test_save_records_call(self) -> None:
        store = MockGraphStateStore()
        await store.save("run-1", {"key": "val"})
        assert len(store.saves) == 1
        assert store.saves[0][0] == "run-1"

    @pytest.mark.asyncio
    async def test_load_returns_none_by_default(self) -> None:
        store = MockGraphStateStore()
        result = await store.load("run-1")
        assert result is None
        assert store.loaded == "run-1"

    @pytest.mark.asyncio
    async def test_delete_records_call(self) -> None:
        store = MockGraphStateStore()
        await store.delete("run-1")
        assert store.deleted == "run-1"
