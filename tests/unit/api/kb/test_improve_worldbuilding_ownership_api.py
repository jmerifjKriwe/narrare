"""S8 — IDOR regression tests: ownership gates on KB improve + worldbuilding (HTTP).

Router-level matrix over all four endpoints (improve analyze/apply,
worldbuilding analyze/apply). Before the S8 fix the routers carried
``CurrentUserIdDep`` but never threaded it into the services (worldbuilding
``apply`` passed ``user_id`` to a service that ignored it), so a foreign
caller received LLM improvement suggestions for another user's entry and
could write the foreign entry (field updates + relationships).

After the fix (plan S8): the owner's responses are unchanged (200); a
foreign caller gets 404 on every endpoint with zero side effects (no
entry write, no relationship row, no LLM/analyzer call, no cache probe);
unknown ids are shape-identical to foreign ones (anti-enumeration).

The service-level matrix lives in ``test_improve_worldbuilding_ownership.py``
(RULE-04 split).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare._app.rate_limits import AI_ANALYSIS_LIMITER
from narrare.kb.dependencies import get_kb_improve_service, get_worldbuilding_service

from ._test_fakes_improve_worldbuilding import (
    FakeKBEntry,
    make_improve_ownership_service,
    make_worldbuilding_analysis,
    make_worldbuilding_ownership_service,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

USER_A = uuid4()  # rightful owner of the novel + entry (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A
FOREIGN_NOVEL_ID = uuid4()  # owned by USER_B

ENTRY_ID = uuid4()  # USER_A's entry inside NOVEL_ID
FOREIGN_ENTRY_ID = uuid4()  # USER_B's entry inside FOREIGN_NOVEL_ID

_OWNERSHIP = {NOVEL_ID: USER_A, FOREIGN_NOVEL_ID: USER_B}

_IMPROVE_URL = "/api/v1/novels/{novel_id}/kb/entities/{entry_id}/improve"
_WB_URL = "/api/v1/novels/{novel_id}/kb/worldbuilding/{verb}"


@pytest.fixture
def app():
    """Test app with overridden auth and rate limiter.

    The improve/worldbuilding service dependencies are overridden
    per-test (see ``_install_services``), which replaces their whole
    subtree — no DB session is ever resolved.
    """
    application = create_app()

    async def _mock_auth() -> str:
        return application.state.auth_user

    async def _no_rate_limit() -> None:
        return None

    application.state.auth_user = str(USER_A)
    application.dependency_overrides[get_current_user_id] = _mock_auth
    application.dependency_overrides[AI_ANALYSIS_LIMITER] = _no_rate_limit
    return application


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"Origin": "http://localhost:3000"}
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


class _ImproveBundle:
    """All improve fakes + service, installed on the app."""

    def __init__(self, app: FastAPI) -> None:
        entries = {
            ENTRY_ID: FakeKBEntry(id=ENTRY_ID, novel_id=NOVEL_ID, metadata_={"age": 30}),
            FOREIGN_ENTRY_ID: FakeKBEntry(id=FOREIGN_ENTRY_ID, novel_id=FOREIGN_NOVEL_ID),
        }
        (
            service,
            self.analyzer,
            self.kb_repo,
            self.rel_repo,
            self.novel_repo,
        ) = make_improve_ownership_service(_OWNERSHIP, entries)
        app.dependency_overrides[get_kb_improve_service] = lambda: service


class _WorldbuildingBundle:
    """All worldbuilding fakes + service, installed on the app."""

    def __init__(self, app: FastAPI) -> None:
        (
            service,
            self.analyzer,
            self.rel_repo,
            self.cache,
            self.novel_repo,
        ) = make_worldbuilding_ownership_service(_OWNERSHIP)
        app.dependency_overrides[get_worldbuilding_service] = lambda: service


def _as_user(app: FastAPI, user_id: UUID) -> None:
    app.state.auth_user = str(user_id)


async def _improve(client: AsyncClient, entry_id: UUID, *, novel_id: UUID, apply: bool = False):
    url = _IMPROVE_URL.format(novel_id=novel_id, entry_id=entry_id)
    if apply:
        return await client.post(url + "/apply", json={"suggestion_ids": [0, 1]})
    return await client.post(url)


async def _worldbuilding(client: AsyncClient, *, novel_id: UUID, apply: bool = False):
    url = _WB_URL.format(novel_id=novel_id, verb="apply" if apply else "analyze")
    if apply:
        analysis = make_worldbuilding_analysis(novel_id)
        return await client.post(
            url, json={"finding_indices": [0], "analysis": analysis.model_dump()}
        )
    return await client.post(url, json={})


def _assert_404_novel(response, novel_id: UUID) -> None:
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": f"Novel ({novel_id}) not found", "code": "NOT_FOUND"}


# ---------------------------------------------------------------------------
# Improve endpoints
# ---------------------------------------------------------------------------


class TestImproveRouterOwnership:
    """POST improve analyze/apply: owner unchanged; foreign/unknown → 404."""

    async def test_owner_analyze_returns_200(self, app, client) -> None:
        bundle = _ImproveBundle(app)

        response = await _improve(client, ENTRY_ID, novel_id=NOVEL_ID)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.json()["suggestions"]) == 2
        assert bundle.analyzer.analyze_calls == [(NOVEL_ID, ENTRY_ID)]

    async def test_owner_apply_returns_200(self, app, client) -> None:
        bundle = _ImproveBundle(app)

        response = await _improve(client, ENTRY_ID, novel_id=NOVEL_ID, apply=True)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["success"] is True
        assert len(bundle.kb_repo.update_calls) == 1
        assert len(bundle.rel_repo.created) == 1

    @pytest.mark.parametrize("apply", [False, True])
    async def test_foreign_novel_404_without_side_effects(self, app, client, apply: bool) -> None:
        """USER_B on USER_A's novel → 404 BEFORE cache probe, LLM call, or write."""
        bundle = _ImproveBundle(app)
        _as_user(app, USER_B)

        response = await _improve(client, ENTRY_ID, novel_id=NOVEL_ID, apply=apply)

        _assert_404_novel(response, NOVEL_ID)
        assert bundle.analyzer.cached_calls == []
        assert bundle.analyzer.analyze_calls == []
        assert bundle.kb_repo.get_by_id_calls == []
        assert bundle.kb_repo.update_calls == []
        assert bundle.rel_repo.created == []

    @pytest.mark.parametrize("apply", [False, True])
    async def test_unknown_novel_404_shape_matches_foreign(self, app, client, apply: bool) -> None:
        _ImproveBundle(app)
        _as_user(app, USER_B)
        unknown_novel = uuid4()

        foreign = await _improve(client, ENTRY_ID, novel_id=NOVEL_ID, apply=apply)
        unknown = await _improve(client, ENTRY_ID, novel_id=unknown_novel, apply=apply)

        assert foreign.status_code == unknown.status_code == status.HTTP_404_NOT_FOUND
        assert foreign.json() == {"detail": f"Novel ({NOVEL_ID}) not found", "code": "NOT_FOUND"}
        assert unknown.json() == {
            "detail": f"Novel ({unknown_novel}) not found",
            "code": "NOT_FOUND",
        }

    @pytest.mark.parametrize("apply", [False, True])
    async def test_foreign_entry_under_own_novel_404(self, app, client, apply: bool) -> None:
        """USER_A names their own novel but a foreign entry → 404, no effects."""
        bundle = _ImproveBundle(app)

        foreign = await _improve(client, FOREIGN_ENTRY_ID, novel_id=NOVEL_ID, apply=apply)
        unknown = await _improve(client, uuid4(), novel_id=NOVEL_ID, apply=apply)

        assert foreign.status_code == unknown.status_code == status.HTTP_404_NOT_FOUND
        assert foreign.json() == {
            "detail": f"KBEntry ({FOREIGN_ENTRY_ID}) not found",
            "code": "NOT_FOUND",
        }
        assert unknown.json()["code"] == "NOT_FOUND"
        assert bundle.analyzer.cached_calls == []
        assert bundle.analyzer.analyze_calls == []
        assert bundle.kb_repo.update_calls == []
        assert bundle.rel_repo.created == []


# ---------------------------------------------------------------------------
# Worldbuilding endpoints
# ---------------------------------------------------------------------------


class TestWorldbuildingRouterOwnership:
    """POST worldbuilding analyze/apply: owner unchanged; foreign/unknown → 404."""

    async def test_owner_analyze_returns_200(self, app, client) -> None:
        bundle = _WorldbuildingBundle(app)

        response = await _worldbuilding(client, novel_id=NOVEL_ID)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["worldbuilding_score"] == 0.75
        assert bundle.analyzer.analyze_calls == [NOVEL_ID]

    async def test_owner_apply_returns_200(self, app, client) -> None:
        bundle = _WorldbuildingBundle(app)

        response = await _worldbuilding(client, novel_id=NOVEL_ID, apply=True)

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["created_count"] == 1
        assert len(bundle.rel_repo.created) == 1
        assert bundle.cache.delete_all_calls == [str(NOVEL_ID)]

    @pytest.mark.parametrize("apply", [False, True])
    async def test_foreign_novel_404_without_side_effects(self, app, client, apply: bool) -> None:
        bundle = _WorldbuildingBundle(app)
        _as_user(app, USER_B)

        response = await _worldbuilding(client, novel_id=NOVEL_ID, apply=apply)

        _assert_404_novel(response, NOVEL_ID)
        assert bundle.analyzer.analyze_calls == []
        assert bundle.rel_repo.exists_calls == []
        assert bundle.rel_repo.created == []
        assert bundle.cache.delete_all_calls == []

    @pytest.mark.parametrize("apply", [False, True])
    async def test_unknown_novel_404_shape_matches_foreign(self, app, client, apply: bool) -> None:
        _WorldbuildingBundle(app)
        _as_user(app, USER_B)
        unknown_novel = uuid4()

        foreign = await _worldbuilding(client, novel_id=NOVEL_ID, apply=apply)
        unknown = await _worldbuilding(client, novel_id=unknown_novel, apply=apply)

        assert foreign.status_code == unknown.status_code == status.HTTP_404_NOT_FOUND
        assert foreign.json() == {"detail": f"Novel ({NOVEL_ID}) not found", "code": "NOT_FOUND"}
        assert unknown.json() == {
            "detail": f"Novel ({unknown_novel}) not found",
            "code": "NOT_FOUND",
        }
