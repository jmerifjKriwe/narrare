"""Shared test fixtures für KBAgent tests.

Mock-Services die das KBQueryService-Protocol erfüllen.
Ausgelagert aus test_kb_agent.py wegen RULE-04 (<200 Zeilen).
"""

from __future__ import annotations


class MockKBService:
    """Minimal mock satisfying KBQueryService for happy-path tests."""

    def __init__(
        self,
        search_results: list[object] | None = None,
        entity: object | None = None,
        related: list[object] | None = None,
    ) -> None:
        self._search_results = search_results or []
        self._entity = entity
        self._related = related or []

    async def search(self, query: str, *, entity_type: str | None = None) -> list[object]:
        return self._search_results

    async def get_by_name(self, name: str) -> object | None:
        return self._entity

    async def get_related(
        self, entity_id: object, *, relation_type: str | None = None
    ) -> list[object]:
        return self._related


class BrokenSearchService:
    """Service that raises on search."""

    async def search(self, query: str, *, entity_type: str | None = None) -> list[object]:
        raise ConnectionError("Connection refused")

    async def get_by_name(self, name: str) -> object | None:
        return None

    async def get_related(
        self, entity_id: object, *, relation_type: str | None = None
    ) -> list[object]:
        return []


class BrokenGetByNameService:
    """Service that raises on get_by_name."""

    async def search(self, query: str, *, entity_type: str | None = None) -> list[object]:
        return []

    async def get_by_name(self, name: str) -> object:
        raise ValueError("Not found in DB")

    async def get_related(
        self, entity_id: object, *, relation_type: str | None = None
    ) -> list[object]:
        return []


class BrokenGetRelatedService:
    """Service that raises on get_related."""

    def __init__(self, entity: object) -> None:
        self._entity = entity

    async def search(self, query: str, *, entity_type: str | None = None) -> list[object]:
        return []

    async def get_by_name(self, name: str) -> object | None:
        return self._entity

    async def get_related(
        self, entity_id: object, *, relation_type: str | None = None
    ) -> list[object]:
        raise RuntimeError("DB timeout")
