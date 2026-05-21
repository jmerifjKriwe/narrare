"""Tests für KBQueryServiceAdapter — Adapter zwischen KBAgent und KB-Repository.

Test-Strategie:
- Mock-Repositories (AsyncMock)
- Keine DB, keine echten LLM-Calls
- Testet die Adapter-Logik: novel_id-Vorausfüllung, Methoden-Übersetzung
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from narrare.kb.query_adapter import KBQueryServiceAdapter


def _make_uuid() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture()
def novel_id() -> uuid.UUID:
    return _make_uuid()


@pytest.fixture()
def mock_repo() -> AsyncMock:
    repo = AsyncMock()
    return repo


@pytest.fixture()
def mock_rel_repo() -> AsyncMock:
    return AsyncMock()


@pytest.fixture()
def adapter(
    novel_id: uuid.UUID, mock_repo: AsyncMock, mock_rel_repo: AsyncMock
) -> KBQueryServiceAdapter:
    return KBQueryServiceAdapter(
        repository=mock_repo,
        relationship_repo=mock_rel_repo,
        novel_id=novel_id,
    )


class TestKBQueryServiceAdapter:
    """Test adapter method translation."""

    @pytest.mark.asyncio
    async def test_search_delegates_to_repo_with_novel_id(
        self,
        adapter: KBQueryServiceAdapter,
        mock_repo: AsyncMock,
        novel_id: uuid.UUID,
    ) -> None:
        entries = [SimpleNamespace(name="Anna", entity_type="character")]
        mock_repo.search.return_value = (entries, 1)

        result = await adapter.search("Anna")

        assert result == entries
        mock_repo.search.assert_awaited_once_with(
            novel_id,
            "Anna",
            entity_type=None,
            page_size=10,
        )

    @pytest.mark.asyncio
    async def test_search_with_entity_type_filter(
        self,
        adapter: KBQueryServiceAdapter,
        mock_repo: AsyncMock,
        novel_id: uuid.UUID,
    ) -> None:
        mock_repo.search.return_value = ([], 0)

        await adapter.search("Anna", entity_type="character")

        mock_repo.search.assert_awaited_once_with(
            novel_id,
            "Anna",
            entity_type="character",
            page_size=10,
        )

    @pytest.mark.asyncio
    async def test_search_returns_entries_only(
        self,
        adapter: KBQueryServiceAdapter,
        mock_repo: AsyncMock,
    ) -> None:
        entries = [SimpleNamespace(name="A"), SimpleNamespace(name="B")]
        mock_repo.search.return_value = (entries, 42)

        result = await adapter.search("anything")

        assert result == entries
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_by_name_delegates_to_repo(
        self,
        adapter: KBQueryServiceAdapter,
        mock_repo: AsyncMock,
        novel_id: uuid.UUID,
    ) -> None:
        entity = SimpleNamespace(name="Anna", entity_type="character")
        mock_repo.get_by_name.return_value = entity

        result = await adapter.get_by_name("Anna")

        assert result == entity
        mock_repo.get_by_name.assert_awaited_once_with(novel_id, "Anna")

    @pytest.mark.asyncio
    async def test_get_by_name_returns_none_when_not_found(
        self,
        adapter: KBQueryServiceAdapter,
        mock_repo: AsyncMock,
    ) -> None:
        mock_repo.get_by_name.return_value = None

        result = await adapter.get_by_name("Ghost")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_related_delegates_to_rel_repo(
        self,
        adapter: KBQueryServiceAdapter,
        mock_rel_repo: AsyncMock,
    ) -> None:
        entity_id = _make_uuid()
        rels = [SimpleNamespace(target_name="Peter", rel_type="ally")]
        mock_rel_repo.list_for_entry.return_value = rels

        result = await adapter.get_related(entity_id)

        assert result == rels
        mock_rel_repo.list_for_entry.assert_awaited_once_with(entity_id, direction=None)

    @pytest.mark.asyncio
    async def test_get_related_filters_by_relation_type(
        self,
        adapter: KBQueryServiceAdapter,
        mock_rel_repo: AsyncMock,
    ) -> None:
        entity_id = _make_uuid()
        rels = [
            SimpleNamespace(target_name="Peter", rel_type="ally"),
            SimpleNamespace(target_name="Berlin", rel_type="lives_in"),
        ]
        mock_rel_repo.list_for_entry.return_value = rels

        result = await adapter.get_related(entity_id, relation_type="ally")

        assert len(result) == 1
        assert result[0].target_name == "Peter"  # type: ignore[union-attr]

    @pytest.mark.asyncio
    async def test_get_related_returns_all_when_no_filter(
        self,
        adapter: KBQueryServiceAdapter,
        mock_rel_repo: AsyncMock,
    ) -> None:
        entity_id = _make_uuid()
        rels = [
            SimpleNamespace(target_name="Peter", rel_type="ally"),
            SimpleNamespace(target_name="Berlin", rel_type="lives_in"),
        ]
        mock_rel_repo.list_for_entry.return_value = rels

        result = await adapter.get_related(entity_id)

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_related_returns_empty_list(
        self,
        adapter: KBQueryServiceAdapter,
        mock_rel_repo: AsyncMock,
    ) -> None:
        entity_id = _make_uuid()
        mock_rel_repo.list_for_entry.return_value = []

        result = await adapter.get_related(entity_id)

        assert result == []
