"""Deprecated-visibility tests for the KB surfaces (ADR-085 P4, spec §6.7/§9(c)).

Verification checklist item (c): list/search/graph exclude
``status='deprecated'`` entries unless explicitly requested. Three seams
are pinned:

1. **Repository** — ``list_entries``/``search`` compile a
   ``kb_entries.status != 'deprecated'`` condition into BOTH the list and
   the count statement by default; ``include_deprecated=True`` omits it.
   Asserted on the compiled SQL handed to the session (mocked results),
   so the filter itself is under test, not a fake.
2. **Service/router plumb-through** — the query parameter reaches the
   service with the documented default (backward-compatible: old clients
   get the new, spec-mandated default visibility).
3. **Graph** — ``GraphFilter.include_deprecated`` flows from the query
   string into the repository fetch, and deprecated rows are absent from
   the node set unless requested.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from narrare._app.dependencies_auth import get_current_user_id
from narrare.kb.dependencies import get_graph_service, get_kb_service
from narrare.kb.graph_schemas import GraphFilter, GraphResponse, GraphStats
from narrare.kb.graph_service import GraphService
from narrare.kb.models import KBEntry
from narrare.kb.repository import KBRepository
from narrare.kb.router import router as kb_router
from narrare.kb.router_graph import router as kb_graph_router
from narrare.kb.service import KBService

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol

# --- Repository seam (compiled-SQL assertions) -----------------------------------

_RESULT_ATTRS = ["scalars", "scalar_one_or_none", "scalar_one"]


def _make_result(**kwargs: object) -> object:
    from unittest.mock import MagicMock

    result = MagicMock(spec=_RESULT_ATTRS)
    for key, value in kwargs.items():
        setattr(result, key, value)
    return result


def _returning(value: object) -> object:
    from unittest.mock import MagicMock

    return MagicMock(spec=[], return_value=value)


def _where_sql(mock_session: AsyncMock, call_index: int) -> str:
    """Compile the WHERE clause of the statement passed to execute().

    The WHERE clause is the visibility discriminator — ``kb_entries.status``
    appears in every SELECT column list, so the full statement string is
    useless here.
    """
    stmt = mock_session.execute.call_args_list[call_index].args[0]
    return str(stmt.whereclause)


def _seed_repo_calls(mock_session: AsyncMock, *, count: int = 0) -> None:
    mock_session.execute.side_effect = [
        _make_result(scalar_one=_returning(count)),
        _make_result(scalars=_returning([])),
    ]


class TestRepositoryDeprecatedVisibility:
    """list_entries/search exclude deprecated rows unless asked (§9(c))."""

    async def test_list_entries_excludes_deprecated_by_default(self) -> None:
        mock_session = AsyncMock()
        _seed_repo_calls(mock_session, count=1)
        repo = KBRepository(mock_session)

        entries, total = await repo.list_entries(uuid4())

        assert entries == []
        assert total == 1
        list_sql = _where_sql(mock_session, 0)
        count_sql = _where_sql(mock_session, 1)
        # Both statements carry the visibility condition.
        assert "kb_entries.status" in list_sql
        assert "kb_entries.status" in count_sql

    async def test_list_entries_with_include_flag_has_no_status_filter(self) -> None:
        mock_session = AsyncMock()
        _seed_repo_calls(mock_session, count=1)
        repo = KBRepository(mock_session)

        await repo.list_entries(uuid4(), include_deprecated=True)

        assert "kb_entries.status" not in _where_sql(mock_session, 0)
        assert "kb_entries.status" not in _where_sql(mock_session, 1)

    async def test_search_excludes_deprecated_by_default(self) -> None:
        mock_session = AsyncMock()
        _seed_repo_calls(mock_session, count=1)
        repo = KBRepository(mock_session)

        await repo.search(uuid4(), "Anna")

        assert "kb_entries.status" in _where_sql(mock_session, 0)
        assert "kb_entries.status" in _where_sql(mock_session, 1)

    async def test_search_with_include_flag_has_no_status_filter(self) -> None:
        mock_session = AsyncMock()
        _seed_repo_calls(mock_session, count=1)
        repo = KBRepository(mock_session)

        await repo.search(uuid4(), "Anna", include_deprecated=True)

        assert "kb_entries.status" not in _where_sql(mock_session, 0)
        assert "kb_entries.status" not in _where_sql(mock_session, 1)

    async def test_get_by_id_still_returns_deprecated_rows(self) -> None:
        """Point lookups stay unfiltered — the merge executor reads losers."""
        deprecated = KBEntry(
            novel_id=uuid4(),
            entity_type="character",
            name="Anna",
            slug="anna",
            status="deprecated",
        )
        mock_session = AsyncMock()
        mock_session.execute.return_value = _make_result(scalar_one_or_none=_returning(deprecated))
        repo = KBRepository(mock_session)

        found = await repo.get_by_id(deprecated.id)

        assert found is deprecated
        assert "kb_entries.status" not in _where_sql(mock_session, 0)


# --- Service plumb-through ----------------------------------------------------------


class TestServicePlumbThrough:
    async def test_list_entries_passes_default_include_deprecated_false(self) -> None:
        repo = AsyncMock(spec=["list_entries"])
        repo.list_entries = AsyncMock(return_value=([], 0))
        service = KBService(repo=cast("KBRepositoryProtocol", repo))

        await service.list_entries(uuid4(), uuid4())

        assert repo.list_entries.await_args.kwargs["include_deprecated"] is False

    async def test_list_entries_passes_explicit_include_flag(self) -> None:
        repo = AsyncMock(spec=["list_entries"])
        repo.list_entries = AsyncMock(return_value=([], 0))
        service = KBService(repo=cast("KBRepositoryProtocol", repo))

        await service.list_entries(uuid4(), uuid4(), include_deprecated=True)

        assert repo.list_entries.await_args.kwargs["include_deprecated"] is True

    async def test_search_passes_default_include_deprecated_false(self) -> None:
        repo = AsyncMock(spec=["search"])
        repo.search = AsyncMock(return_value=([], 0))
        service = KBService(repo=cast("KBRepositoryProtocol", repo))

        await service.search(uuid4(), uuid4(), "Anna")

        assert repo.search.await_args.kwargs["include_deprecated"] is False


# --- Router plumb-through -----------------------------------------------------------


def _kb_service_app(service: AsyncMock) -> FastAPI:
    app = FastAPI()
    app.include_router(kb_router, prefix="/api/v1")
    app.dependency_overrides[get_current_user_id] = lambda: str(uuid4())
    app.dependency_overrides[get_kb_service] = lambda: service
    return app


class TestRouterPlumbThrough:
    def test_list_route_defaults_to_excluding_deprecated(self) -> None:
        service = AsyncMock(spec=KBService)
        service.list_entries = AsyncMock(return_value=([], 0))

        with TestClient(_kb_service_app(service)) as client:
            response = client.get(f"/api/v1/novels/{uuid4()}/kb/entries")

        assert response.status_code == 200
        assert service.list_entries.await_args.kwargs["include_deprecated"] is False

    def test_list_route_forwards_explicit_include_flag(self) -> None:
        service = AsyncMock(spec=KBService)
        service.list_entries = AsyncMock(return_value=([], 0))

        with TestClient(_kb_service_app(service)) as client:
            response = client.get(f"/api/v1/novels/{uuid4()}/kb/entries?include_deprecated=true")

        assert response.status_code == 200
        assert service.list_entries.await_args.kwargs["include_deprecated"] is True

    def test_search_route_forwards_explicit_include_flag(self) -> None:
        service = AsyncMock(spec=KBService)
        service.search = AsyncMock(return_value=([], 0))

        with TestClient(_kb_service_app(service)) as client:
            response = client.get(
                f"/api/v1/novels/{uuid4()}/kb/entries/search?q=anna&include_deprecated=true"
            )

        assert response.status_code == 200
        assert service.search.await_args.kwargs["include_deprecated"] is True

    def test_update_route_accepts_deprecated_status(self) -> None:
        """Backward compat: explicit status stays settable (un-deprecate path)."""
        from datetime import UTC, datetime

        from narrare.kb.schemas import KBEntryResponse

        updated = KBEntryResponse(
            id=uuid4(),
            novel_id=uuid4(),
            entity_type="character",
            name="Anna",
            slug="anna",
            status="active",
            tags=[],
            body="",
            template_version=None,
            source="user",
            review_status="approved",
            embeddings_dirty=False,
            created_at=datetime.now(tz=UTC),
            updated_at=datetime.now(tz=UTC),
        )
        service = AsyncMock(spec=KBService)
        service.update = AsyncMock(return_value=updated)

        with TestClient(_kb_service_app(service)) as client:
            response = client.patch(
                f"/api/v1/novels/{uuid4()}/kb/entries/{uuid4()}",
                json={"status": "active"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "active"


# --- Graph seam -----------------------------------------------------------------------


class _FakeGraphEntry:
    """Plain entry stand-in with the attributes GraphService renders."""

    def __init__(self, name: str, status: str) -> None:
        self.id = uuid4()
        self.name = name
        self.entity_type = "character"
        self.status = status
        self.tags: list[str] = []
        self.metadata_: dict[str, object] = {}


class _FakeGraphKbRepo:
    """list_entries double honoring the include_deprecated contract."""

    def __init__(self, entries: list[_FakeGraphEntry]) -> None:
        self._entries = entries
        self.include_deprecated_calls: list[bool] = []

    async def list_entries(
        self,
        novel_id: object,
        *,
        page: int = 1,
        page_size: int = 50,
        include_deprecated: bool = False,
    ) -> tuple[list[_FakeGraphEntry], int]:
        self.include_deprecated_calls.append(include_deprecated)
        if include_deprecated:
            return list(self._entries), len(self._entries)
        kept = [e for e in self._entries if e.status != "deprecated"]
        return kept, len(kept)


class _FakeGraphRelRepo:
    async def list_all_for_novel(self, novel_id: object) -> list[object]:
        return []

    async def get_adjacency_map(
        self, novel_id: object, entity_ids: object = None
    ) -> dict[str, set[str]]:
        return {}


class TestGraphDeprecatedVisibility:
    def _service(
        self,
    ) -> tuple[GraphService, _FakeGraphKbRepo, _FakeGraphEntry, _FakeGraphEntry]:
        active = _FakeGraphEntry("Anna Meyer", "active")
        deprecated = _FakeGraphEntry("Anna", "deprecated")
        repo = _FakeGraphKbRepo([active, deprecated])
        return (
            GraphService(
                cast("KBRepositoryProtocol", repo),
                cast("RelationshipRepositoryProtocol", _FakeGraphRelRepo()),
            ),
            repo,
            active,
            deprecated,
        )

    async def test_graph_excludes_deprecated_nodes_by_default(self) -> None:
        service, repo, _active, deprecated = self._service()

        response = await service.get_graph(novel_id=uuid4(), user_id=uuid4())

        assert repo.include_deprecated_calls == [False]
        assert all(node.id != deprecated.id for node in response.nodes)

    async def test_graph_includes_deprecated_nodes_when_requested(self) -> None:
        service, repo, _active, deprecated = self._service()
        novel_id = uuid4()

        response = await service.get_graph(
            novel_id=novel_id,
            user_id=uuid4(),
            filter=GraphFilter(include_deprecated=True),
        )

        assert repo.include_deprecated_calls == [True]
        assert any(node.id == deprecated.id for node in response.nodes)

    def test_graph_route_forwards_include_flag_into_filter(self) -> None:
        graph_service = AsyncMock(spec=GraphService)
        graph_service.get_graph = AsyncMock(
            return_value=GraphResponse(
                nodes=[],
                edges=[],
                stats=GraphStats(
                    node_count=0,
                    edge_count=0,
                    isolated_count=0,
                    connected_components=0,
                    entity_type_counts={},
                    rel_type_counts={},
                ),
            )
        )
        app = FastAPI()
        app.include_router(kb_graph_router, prefix="/api/v1")
        app.dependency_overrides[get_current_user_id] = lambda: str(uuid4())
        app.dependency_overrides[get_graph_service] = lambda: graph_service

        with TestClient(app) as client:
            response = client.get(f"/api/v1/novels/{uuid4()}/kb/graph?include_deprecated=true")

        assert response.status_code == 200
        sent_filter = graph_service.get_graph.await_args.kwargs["filter"]
        assert isinstance(sent_filter, GraphFilter)
        assert sent_filter.include_deprecated is True
