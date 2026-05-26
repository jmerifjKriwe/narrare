"""Unit tests for GraphService.get_shortest_path — BFS path finding.

Tests shortest path, disconnected entities, missing source, and wrong novel
with faked dependencies (no I/O, no DB, no LLM).
"""

from __future__ import annotations

import types
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from narrare.kb.graph_service import GraphService
from narrare_core.shared.errors import NotFoundError

# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _make_entry(
    *,
    entity_type: str = "character",
    name: str = "Test Entity",
    novel_id: UUID | None = None,
    entry_id: UUID | None = None,
) -> types.SimpleNamespace:
    """Create a minimal KBEntry-like object for testing."""
    return types.SimpleNamespace(
        id=entry_id or uuid4(),
        novel_id=novel_id or uuid4(),
        entity_type=entity_type,
        name=name,
        slug=name.lower().replace(" ", "-"),
        status="draft",
        tags=None,
        metadata_=None,
    )


def _make_service(
    *,
    entries: list[types.SimpleNamespace] | None = None,
    adjacency: dict[str, set[str]] | None = None,
) -> tuple[GraphService, dict[str, AsyncMock]]:
    """Create a GraphService with faked dependencies."""
    kb_repo = AsyncMock()
    rel_repo = AsyncMock()
    _entries = entries or []
    kb_repo.list_entries = AsyncMock(return_value=(_entries, len(_entries)))
    kb_repo.get_by_id = AsyncMock(return_value=None)
    rel_repo.list_all_for_novel = AsyncMock(return_value=[])
    rel_repo.get_adjacency_map = AsyncMock(return_value=adjacency or {})
    service = GraphService(kb_repo=kb_repo, rel_repo=rel_repo)
    return service, {"kb_repo": kb_repo, "rel_repo": rel_repo}


# ===========================================================================


class TestGetShortestPath:
    """Tests for GraphService.get_shortest_path()."""

    async def test_find_path_returns_shortest_path(self) -> None:
        """Verify BFS finds path between two connected entities."""
        novel_id = uuid4()
        user_id = uuid4()
        e1 = _make_entry(name="Alice", novel_id=novel_id, entry_id=uuid4())
        e2 = _make_entry(name="Bob", novel_id=novel_id, entry_id=uuid4())
        e3 = _make_entry(name="Castle", novel_id=novel_id, entry_id=uuid4())

        adjacency = {
            str(e1.id): {str(e2.id)},
            str(e2.id): {str(e1.id), str(e3.id)},
            str(e3.id): {str(e2.id)},
        }

        service, mocks = _make_service(entries=[e1, e2, e3], adjacency=adjacency)
        entry_map = {e1.id: e1, e2.id: e2, e3.id: e3}
        mocks["kb_repo"].get_by_id = AsyncMock(side_effect=lambda eid: entry_map.get(eid))

        result = await service.get_shortest_path(
            novel_id=novel_id,
            user_id=user_id,
            source_id=e1.id,
            target_id=e3.id,
        )

        assert result.path is not None
        assert result.length == 2  # Alice -> Bob -> Castle (2 hops)
        assert result.path == [e1.id, e2.id, e3.id]
        assert result.entity_names == ["Alice", "→", "Bob", "→", "Castle"]

    async def test_find_path_returns_not_found(self) -> None:
        """Verify no path between disconnected entities returns None."""
        novel_id = uuid4()
        user_id = uuid4()
        e1 = _make_entry(name="Alice", novel_id=novel_id, entry_id=uuid4())
        e2 = _make_entry(name="Bob", novel_id=novel_id, entry_id=uuid4())

        adjacency: dict[str, set[str]] = {}

        service, mocks = _make_service(entries=[e1, e2], adjacency=adjacency)
        entry_map = {e1.id: e1, e2.id: e2}
        mocks["kb_repo"].get_by_id = AsyncMock(side_effect=lambda eid: entry_map.get(eid))

        result = await service.get_shortest_path(
            novel_id=novel_id,
            user_id=user_id,
            source_id=e1.id,
            target_id=e2.id,
        )

        assert result.path is None
        assert result.length is None
        assert result.entity_names is None

    async def test_find_path_raises_not_found_for_missing_source(self) -> None:
        """Verify NotFoundError when source entity doesn't exist."""
        novel_id = uuid4()
        user_id = uuid4()
        missing_id = uuid4()

        service, mocks = _make_service()
        mocks["kb_repo"].get_by_id = AsyncMock(return_value=None)

        with pytest.raises(NotFoundError):
            await service.get_shortest_path(
                novel_id=novel_id,
                user_id=user_id,
                source_id=missing_id,
                target_id=uuid4(),
            )

    async def test_find_path_raises_not_found_for_wrong_novel(self) -> None:
        """Verify NotFoundError when entity belongs to a different novel."""
        novel_id = uuid4()
        other_novel_id = uuid4()
        user_id = uuid4()

        e1 = _make_entry(name="Alice", novel_id=other_novel_id, entry_id=uuid4())

        service, mocks = _make_service()
        mocks["kb_repo"].get_by_id = AsyncMock(return_value=e1)

        with pytest.raises(NotFoundError):
            await service.get_shortest_path(
                novel_id=novel_id,
                user_id=user_id,
                source_id=e1.id,
                target_id=uuid4(),
            )
