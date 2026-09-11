"""S13 — IDOR regression tests: ownership gate on GET /writing/novels/{id}/stats.

Router-level + dependency-level matrix for the generation-stats surface
(plan ``docs/superpowers/plans/2026-08-26-idor-remediation.md`` §S13).
Before the fix ``WritingService.get_stats`` accepted ``user_id`` but
ignored it: any authenticated caller could aggregate another user's
generation statistics by novel id (cross-user READ of generation
analytics).

Gate placement note (deviation from the plan's service-level one-liner,
documented in the plan §S13): ``writing/service.py`` sits exactly at the
RULE-04 hard limit (300 lines), so the gate lands as the established
S11a-style FastAPI route dependency (``writing/deps_ownership.py``) —
the same shape the plan prescribes for the embeddings admin surface.
``get_stats`` has no non-HTTP callers, so the route gate covers the full
attack surface.

After the fix the owner's response is unchanged; a foreign or unknown
novel id gets a 404 with ZERO service construction — the gate runs
before ``get_writing_service`` is ever called. Foreign ≡ unknown
(anti-enumeration, shape-identical 404s).

The DB layer is faked via ``FakeDbSession`` (queued ``execute()``
results — the same contract the settings S11a matrices use).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare.novels.models import Novel
from narrare.writing.deps_ownership import verify_novel_owned
from narrare.writing.schemas import GenerationStatsResponse
from narrare_core.shared.errors import NotFoundError
from tests.fakes.fake_db_session import FakeDbSession

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

USER_A = uuid4()  # rightful owner of the novel (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A

_STATS_URL = "/api/v1/writing/novels/{novel_id}/stats"

_STATS_PAYLOAD = {
    "total_generations": 5,
    "success_rate": 0.8,
    "avg_tokens": 1500.0,
    "avg_word_count": 2000.0,
    "most_used_model": "test-model",
}


def _owned_novel() -> Novel:
    """A novel row as the gate's ownership lookup would return it."""
    return Novel(id=NOVEL_ID, user_id=USER_A)


def _stats_response() -> GenerationStatsResponse:
    return GenerationStatsResponse(**_STATS_PAYLOAD)


# ---------------------------------------------------------------------------
# The gate dependency itself
# ---------------------------------------------------------------------------


class TestVerifyNovelOwnedDependency:
    """Direct unit matrix for the ownership dependency (S11a shape)."""

    async def test_owner_passes(self) -> None:
        session = FakeDbSession(results=[_owned_novel()])
        await verify_novel_owned(
            novel_id=NOVEL_ID,
            session=cast("AsyncSession", session),
            user_id=str(USER_A),
        )

    async def test_foreign_raises_not_found(self) -> None:
        session = FakeDbSession(results=[None])
        with pytest.raises(NotFoundError) as exc_info:
            await verify_novel_owned(
                novel_id=NOVEL_ID,
                session=cast("AsyncSession", session),
                user_id=str(USER_B),
            )
        assert str(exc_info.value) == f"Novel ({NOVEL_ID}) not found"

    async def test_unknown_shape_matches_foreign(self) -> None:
        unknown = uuid4()
        session = FakeDbSession(results=[None])
        with pytest.raises(NotFoundError) as exc_info:
            await verify_novel_owned(
                novel_id=unknown,
                session=cast("AsyncSession", session),
                user_id=str(USER_A),
            )
        assert str(exc_info.value) == f"Novel ({unknown}) not found"


# ---------------------------------------------------------------------------
# GET /writing/novels/{novel_id}/stats
# ---------------------------------------------------------------------------


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch):
    """Test app with overridden auth + a recording writing-service factory.

    ``get_writing_service`` is patched at the router module (where the
    handler resolves it) — the recording stub proves the gate runs
    BEFORE any service construction on denial.
    """
    import narrare.writing.router_stats as router_stats_module

    application = create_app()

    async def _mock_auth() -> str:
        return application.state.auth_user

    application.state.auth_user = str(USER_A)
    application.dependency_overrides[get_current_user_id] = _mock_auth

    factory_calls: list[UUID | None] = []

    async def _recording_factory(session: object, user_id: str, novel_id: UUID | None = None):
        factory_calls.append(novel_id)
        return _StatsStubService()

    monkeypatch.setattr(router_stats_module, "get_writing_service", _recording_factory)
    application.state.stats_factory_calls = factory_calls
    return application


class _StatsStubService:
    """Minimal WritingService stand-in — only ``get_stats`` is reachable."""

    async def get_stats(self, novel_id: UUID, user_id: str) -> GenerationStatsResponse:
        del novel_id, user_id
        return _stats_response()


@pytest.fixture
async def client(app: FastAPI):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", headers={"Origin": "http://localhost:3000"}
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


def _install_session(app: FastAPI, *queued: object) -> FakeDbSession:
    """Override the session dependency with a queued-result fake."""
    from narrare._app.database import get_async_session

    session = FakeDbSession(results=list(queued))
    app.dependency_overrides[get_async_session] = lambda: session
    return session


def _assert_404_novel(response, novel_id: UUID) -> None:
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json() == {"detail": f"Novel ({novel_id}) not found", "code": "NOT_FOUND"}


class TestStatsRouteOwnership:
    """Owner unchanged; foreign/unknown → 404 with zero service work."""

    async def test_owner_get_returns_200(self, app, client) -> None:
        _install_session(app, _owned_novel())

        response = await client.get(_STATS_URL.format(novel_id=NOVEL_ID))

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == _STATS_PAYLOAD
        assert app.state.stats_factory_calls == [NOVEL_ID]

    async def test_foreign_get_404_without_service_construction(self, app, client) -> None:
        session = _install_session(app, None)
        app.state.auth_user = str(USER_B)

        response = await client.get(_STATS_URL.format(novel_id=NOVEL_ID))

        _assert_404_novel(response, NOVEL_ID)
        assert app.state.stats_factory_calls == []
        assert len(session.statements) == 1  # only the gate's novel lookup

    async def test_unknown_get_404_shape_matches_foreign(self, app, client) -> None:
        _install_session(app, None)
        unknown = uuid4()

        foreign = await client.get(_STATS_URL.format(novel_id=NOVEL_ID))
        unknown_response = await client.get(_STATS_URL.format(novel_id=unknown))

        _assert_404_novel(foreign, NOVEL_ID)
        _assert_404_novel(unknown_response, unknown)
        assert app.state.stats_factory_calls == []
