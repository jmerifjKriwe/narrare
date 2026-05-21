"""Tests für KBQueryService Protocol — Compliance-Checks.

Test-Strategie:
- Runtime-Protocol-Checks (isinstance)
- Keine echten LLM-Calls, kein I/O
"""

from __future__ import annotations

from narrare_core.agents.kb_agent import KBDeps
from narrare_core.kb.query_service import KBQueryService


class _MockKBService:
    """Minimal mock satisfying KBQueryService."""

    async def search(self, query: str, *, entity_type: str | None = None) -> list[object]:
        return []

    async def get_by_name(self, name: str) -> object | None:
        return None

    async def get_related(
        self, entity_id: object, *, relation_type: str | None = None
    ) -> list[object]:
        return []


class TestKBQueryServiceProtocol:
    """KBQueryService Protocol compliance checks."""

    def test_mock_service_satisfies_protocol(self) -> None:
        """MockKBService satisfies KBQueryService at runtime."""
        service = _MockKBService()
        assert isinstance(service, KBQueryService)

    def test_kb_deps_accepts_protocol_impl(self) -> None:
        """KBDeps.kb_service accepts KBQueryService implementations."""
        service = _MockKBService()
        deps = KBDeps(kb_service=service)
        assert isinstance(deps.kb_service, KBQueryService)

    def test_kb_deps_none_by_default(self) -> None:
        """KBDeps.kb_service defaults to None."""
        deps = KBDeps()
        assert deps.kb_service is None

    def test_kb_deps_explicit_none(self) -> None:
        """KBDeps can be constructed with explicit None."""
        deps = KBDeps(kb_service=None)
        assert deps.kb_service is None
