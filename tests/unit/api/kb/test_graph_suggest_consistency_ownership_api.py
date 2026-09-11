"""S9 — IDOR regression tests: ownership gates on KB graph + suggest + consistency (HTTP).

Router-level matrix over all four endpoints (GET graph, GET graph
shortest-path, GET kb suggestions, POST consistency-check). Before the
S9 fix the routers already carried ``CurrentUserIdDep`` (the suggest and
consistency handlers even received ``user_id``) but the services ignored
it: a foreign caller received the victim's full KB graph, BFS paths,
proactive suggestions over the victim's chapter, and a full consistency
report (LLM analysis included).

After the fix (plan S9): the owner's responses are unchanged (200); a
foreign caller gets 404 on every endpoint with zero side effects (no
entry/relationship/adjacency read, no chapter load, no cache probe, no
analyzer/LLM call); unknown ids are shape-identical to foreign ones
(anti-enumeration).

The service-level matrix lives in
``test_graph_suggest_consistency_ownership.py`` (RULE-04 split).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare.kb.dependencies import (
    get_consistency_service,
    get_graph_service,
    get_kb_suggest_service,
)

from ._test_fakes_graph_suggest_consistency import (
    FakeGraphEntry,
    FakeGraphRelationship,
    FakeSuggestChapter,
    make_consistency_ownership_service,
    make_graph_ownership_service,
    make_suggest_ownership_service,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

USER_A = uuid4()  # rightful owner of the novel (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A
FOREIGN_NOVEL_ID = uuid4()  # owned by USER_B

_OWNERSHIP = {NOVEL_ID: USER_A, FOREIGN_NOVEL_ID: USER_B}

_CHAPTER_ID = uuid4()

_GRAPH_URL = "/api/v1/novels/{novel_id}/kb/graph"
_PATH_URL = "/api/v1/novels/{novel_id}/kb/graph/shortest-path"
_SUGGEST_URL = "/api/v1/novels/{novel_id}/kb/suggestions/{chapter_id}"
_CONSISTENCY_URL = "/api/v1/novels/{novel_id}/kb/consistency-check"


@pytest.fixture
def app():
    """Test app with overridden auth.

    The graph/suggest/consistency service dependencies are overridden
    per-test (see the bundles below), which replaces their whole
    subtree — no DB session is ever resolved.
    """
    application = create_app()

    async def _mock_auth() -> str:
        return application.state.auth_user

    application.state.auth_user = str(USER_A)
    application.dependency_overrides[get_current_user_id] = _mock_auth
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"Origin": "http://localhost:3000"}
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


class _GraphBundle:
    """Graph fakes + service, installed on the app."""

    def __init__(self, app: FastAPI) -> None:
        e1 = FakeGraphEntry(id=uuid4(), novel_id=NOVEL_ID, name="Alice")
        e2 = FakeGraphEntry(id=uuid4(), novel_id=NOVEL_ID, name="Bob")
        rel = FakeGraphRelationship(source_id=e1.id, target_id=e2.id)
        adjacency = {str(e1.id): {str(e2.id)}, str(e2.id): {str(e1.id)}}
        (
            service,
            self.kb_repo,
            self.rel_repo,
            self.novel_repo,
        ) = make_graph_ownership_service(_OWNERSHIP, [e1, e2], [rel], adjacency)
        self.source_id = e1.id
        self.target_id = e2.id
        app.dependency_overrides[get_graph_service] = lambda: service


class _SuggestBundle:
    """Suggest fakes + service, installed on the app."""

    def __init__(self, app: FastAPI) -> None:
        (
            service,
            self.chapter_repo,
            self.kb_repo,
            self.proactive,
            self.novel_repo,
        ) = make_suggest_ownership_service(
            _OWNERSHIP,
            chapter=FakeSuggestChapter(),
            entries=[FakeGraphEntry(novel_id=NOVEL_ID)],
        )
        app.dependency_overrides[get_kb_suggest_service] = lambda: service


class _ConsistencyBundle:
    """Consistency fakes + service, installed on the app."""

    def __init__(self, app: FastAPI) -> None:
        (
            service,
            self.analyzer,
            self.asymmetry,
            self.cache,
            self.novel_repo,
        ) = make_consistency_ownership_service(_OWNERSHIP)
        app.dependency_overrides[get_consistency_service] = lambda: service


def _as_user(app: FastAPI, user_id: UUID) -> None:
    app.state.auth_user = str(user_id)


def _assert_404_novel(response, novel_id: UUID) -> None:
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": f"Novel ({novel_id}) not found", "code": "NOT_FOUND"}


async def _get_graph(client: AsyncClient, novel_id: UUID):
    return await client.get(_GRAPH_URL.format(novel_id=novel_id))


async def _get_path(client: AsyncClient, novel_id: UUID, source_id: UUID, target_id: UUID):
    return await client.get(
        _PATH_URL.format(novel_id=novel_id),
        params={"source_id": str(source_id), "target_id": str(target_id)},
    )


async def _get_suggestions(client: AsyncClient, novel_id: UUID):
    return await client.get(
        _SUGGEST_URL.format(novel_id=novel_id, chapter_id=_CHAPTER_ID),
        params={"max_results": 5},
    )


async def _post_consistency(client: AsyncClient, novel_id: UUID):
    return await client.post(
        _CONSISTENCY_URL.format(novel_id=novel_id),
        json={"include_cross_entity": False},
    )


# ---------------------------------------------------------------------------
# Graph endpoints
# ---------------------------------------------------------------------------


class TestGraphRouterOwnership:
    """GET graph + shortest-path: owner unchanged; foreign/unknown → 404."""

    async def test_owner_graph_returns_200(self, app, client) -> None:
        bundle = _GraphBundle(app)

        response = await _get_graph(client, NOVEL_ID)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["nodes"]) == 2
        assert bundle.kb_repo.list_entries_calls == [NOVEL_ID]

    async def test_owner_shortest_path_returns_200(self, app, client) -> None:
        bundle = _GraphBundle(app)

        response = await _get_path(client, NOVEL_ID, bundle.source_id, bundle.target_id)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["length"] == 1

    async def test_foreign_novel_graph_404_without_side_effects(self, app, client) -> None:
        """USER_B on USER_A's novel → 404, zero entries/relationships/adjacency read."""
        bundle = _GraphBundle(app)
        _as_user(app, USER_B)

        graph = await _get_graph(client, NOVEL_ID)
        path = await _get_path(client, NOVEL_ID, bundle.source_id, bundle.target_id)

        _assert_404_novel(graph, NOVEL_ID)
        _assert_404_novel(path, NOVEL_ID)
        assert bundle.kb_repo.list_entries_calls == []
        assert bundle.kb_repo.get_by_id_calls == []
        assert bundle.rel_repo.list_all_calls == []
        assert bundle.rel_repo.adjacency_calls == []

    async def test_unknown_novel_graph_404_shape_matches_foreign(self, app, client) -> None:
        _GraphBundle(app)
        _as_user(app, USER_B)
        unknown_novel = uuid4()

        foreign = await _get_graph(client, NOVEL_ID)
        unknown = await _get_graph(client, unknown_novel)

        assert foreign.status_code == unknown.status_code == status.HTTP_404_NOT_FOUND
        assert foreign.json() == {"detail": f"Novel ({NOVEL_ID}) not found", "code": "NOT_FOUND"}
        assert unknown.json() == {
            "detail": f"Novel ({unknown_novel}) not found",
            "code": "NOT_FOUND",
        }


# ---------------------------------------------------------------------------
# Suggestions endpoint
# ---------------------------------------------------------------------------


class TestSuggestRouterOwnership:
    """GET kb suggestions: owner unchanged; foreign/unknown → 404."""

    async def test_owner_suggestions_returns_200(self, app, client) -> None:
        bundle = _SuggestBundle(app)

        response = await _get_suggestions(client, NOVEL_ID)

        assert response.status_code == status.HTTP_200_OK
        assert [s["name"] for s in response.json()] == ["Aria"]
        assert bundle.proactive.suggest_calls == [NOVEL_ID]

    async def test_foreign_novel_404_without_side_effects(self, app, client) -> None:
        """USER_B on USER_A's novel → 404 BEFORE chapter load, KB read,
        and the proactive suggestion pipeline (no LLM enrichment)."""
        bundle = _SuggestBundle(app)
        _as_user(app, USER_B)

        response = await _get_suggestions(client, NOVEL_ID)

        _assert_404_novel(response, NOVEL_ID)
        assert bundle.chapter_repo.get_by_id_calls == []
        assert bundle.kb_repo.list_entries_calls == []
        assert bundle.proactive.suggest_calls == []

    async def test_unknown_novel_404_shape_matches_foreign(self, app, client) -> None:
        _SuggestBundle(app)
        _as_user(app, USER_B)
        unknown_novel = uuid4()

        foreign = await _get_suggestions(client, NOVEL_ID)
        unknown = await _get_suggestions(client, unknown_novel)

        assert foreign.status_code == unknown.status_code == status.HTTP_404_NOT_FOUND
        assert foreign.json() == {"detail": f"Novel ({NOVEL_ID}) not found", "code": "NOT_FOUND"}
        assert unknown.json() == {
            "detail": f"Novel ({unknown_novel}) not found",
            "code": "NOT_FOUND",
        }


# ---------------------------------------------------------------------------
# Consistency endpoint
# ---------------------------------------------------------------------------


class TestConsistencyRouterOwnership:
    """POST consistency-check: owner unchanged; foreign/unknown → 404."""

    async def test_owner_check_returns_200(self, app, client) -> None:
        bundle = _ConsistencyBundle(app)

        response = await _post_consistency(client, NOVEL_ID)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["novel_id"] == str(NOVEL_ID)
        assert bundle.cache.set_calls == [str(NOVEL_ID)]

    async def test_foreign_novel_404_without_side_effects(self, app, client) -> None:
        """USER_B on USER_A's novel → 404 BEFORE the cache probe and every
        analysis phase — no LLM call, no report, no cache write."""
        bundle = _ConsistencyBundle(app)
        _as_user(app, USER_B)

        response = await _post_consistency(client, NOVEL_ID)

        _assert_404_novel(response, NOVEL_ID)
        assert bundle.cache.get_calls == []
        assert bundle.cache.set_calls == []
        assert bundle.asymmetry.check_calls == []
        assert bundle.analyzer.analyze_calls == []

    async def test_unknown_novel_404_shape_matches_foreign(self, app, client) -> None:
        _ConsistencyBundle(app)
        _as_user(app, USER_B)
        unknown_novel = uuid4()

        foreign = await _post_consistency(client, NOVEL_ID)
        unknown = await _post_consistency(client, unknown_novel)

        assert foreign.status_code == unknown.status_code == status.HTTP_404_NOT_FOUND
        assert foreign.json() == {"detail": f"Novel ({NOVEL_ID}) not found", "code": "NOT_FOUND"}
        assert unknown.json() == {
            "detail": f"Novel ({unknown_novel}) not found",
            "code": "NOT_FOUND",
        }
