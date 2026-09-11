"""S13 — IDOR regression tests: ownership gates on the embeddings admin API.

Router-level + dependency-level matrix for the embedding admin surface
(plan ``docs/superpowers/plans/2026-08-26-idor-remediation.md`` §S13,
PO decision D3:a):

* GET  ``/api/v1/admin/embeddings/status/{novel_id}`` — novel-scoped
  (the path addresses the victim's novel) → S11a-style ownership gate.
* POST ``/api/v1/admin/embeddings/reprocess/{novel_id}`` — novel-scoped
  (inert today: the router passes no source_ids, so the service queues
  nothing) → same gate, so a future wiring change inherits the gate.
* GET  ``/api/v1/admin/embeddings/model`` — global-inert (returns the
  active embedding model, no per-user data) → minimal gate: any
  authenticated user; 401 without a token. Documented single-user-trust
  stance (local-first product).

After the fix the owner's responses are unchanged; a foreign or unknown
novel id gets a 404 with ZERO service resolution — the route dependency
runs before ``get_embedding_service`` is ever called. Foreign ≡ unknown
(anti-enumeration, shape-identical 404s).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID, uuid4

import pytest
from fastapi import status
from httpx import ASGITransport, AsyncClient

from narrare._app.dependencies import get_current_user_id
from narrare._app.main import create_app
from narrare.embeddings.dependencies import get_embedding_service, verify_novel_owned
from narrare.novels.models import Novel
from narrare_core.embeddings.store import EmbeddingStats
from narrare_core.shared.errors import NotFoundError
from tests.fakes.fake_db_session import FakeDbSession

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

USER_A = uuid4()  # rightful owner of the novel (the victim)
USER_B = uuid4()  # foreign caller

NOVEL_ID = uuid4()  # owned by USER_A

_STATUS_URL = "/api/v1/admin/embeddings/status/{novel_id}"
_REPROCESS_URL = "/api/v1/admin/embeddings/reprocess/{novel_id}"
_MODEL_URL = "/api/v1/admin/embeddings/model"


def _owned_novel() -> Novel:
    """A novel row as the gate's ownership lookup would return it."""
    return Novel(id=NOVEL_ID, user_id=USER_A)


class _RecordingEmbeddingService:
    """Fake EmbeddingService — records calls, never touches the DB."""

    def __init__(self) -> None:
        self.model = "text-embedding-3-small"
        self.dimension = 1536
        self.provider = "openai"
        self.status_calls: list[UUID] = []
        self.reprocess_calls: list[tuple[UUID, str | None]] = []

    async def get_status(
        self,
        novel_id: UUID,
        source_ids: set[UUID] | None = None,
    ) -> EmbeddingStats:
        del source_ids
        self.status_calls.append(novel_id)
        return EmbeddingStats(
            total=10,
            embedded=8,
            pending=2,
            failed=0,
            coverage_percentage=80.0,
        )

    async def reprocess(
        self,
        novel_id: UUID,
        model: str | None = None,
        source_ids: list[tuple[UUID, str]] | None = None,
    ) -> int:
        del source_ids
        self.reprocess_calls.append((novel_id, model))
        return 5


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
# Admin routes over HTTP
# ---------------------------------------------------------------------------


@pytest.fixture
def app():
    """Test app with overridden auth + a recording embedding service."""
    application = create_app()

    async def _mock_auth() -> str:
        return application.state.auth_user

    application.state.auth_user = str(USER_A)
    application.dependency_overrides[get_current_user_id] = _mock_auth

    service = _RecordingEmbeddingService()
    application.dependency_overrides[get_embedding_service] = lambda: service
    application.state.embedding_service = service
    return application


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


class TestEmbeddingsAdminOwnership:
    """Owner unchanged; foreign/unknown → 404 with zero service work."""

    async def test_owner_status_200(self, app, client) -> None:
        _install_session(app, _owned_novel())

        response = await client.get(_STATUS_URL.format(novel_id=NOVEL_ID))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["total"] == 10
        assert app.state.embedding_service.status_calls == [NOVEL_ID]

    async def test_owner_reprocess_200(self, app, client) -> None:
        _install_session(app, _owned_novel())

        response = await client.post(_REPROCESS_URL.format(novel_id=NOVEL_ID))

        assert response.status_code == status.HTTP_200_OK
        assert response.json()["queued"] == 5
        assert app.state.embedding_service.reprocess_calls == [(NOVEL_ID, None)]

    async def test_foreign_status_404_without_service_resolution(self, app, client) -> None:
        session = _install_session(app, None)
        app.state.auth_user = str(USER_B)

        response = await client.get(_STATUS_URL.format(novel_id=NOVEL_ID))

        _assert_404_novel(response, NOVEL_ID)
        assert app.state.embedding_service.status_calls == []
        assert len(session.statements) == 1  # only the gate's novel lookup

    async def test_foreign_reprocess_404_without_service_resolution(self, app, client) -> None:
        _install_session(app, None)
        app.state.auth_user = str(USER_B)

        response = await client.post(_REPROCESS_URL.format(novel_id=NOVEL_ID))

        _assert_404_novel(response, NOVEL_ID)
        assert app.state.embedding_service.reprocess_calls == []

    async def test_unknown_status_404_shape_matches_foreign(self, app, client) -> None:
        _install_session(app, None)
        unknown = uuid4()

        foreign = await client.get(_STATUS_URL.format(novel_id=NOVEL_ID))
        unknown_response = await client.get(_STATUS_URL.format(novel_id=unknown))

        _assert_404_novel(foreign, NOVEL_ID)
        _assert_404_novel(unknown_response, unknown)


class TestModelInfoMinimalGate:
    """``/model`` is global-inert (D3:a): authenticated-user minimal gate."""

    async def test_model_info_401_without_auth(self) -> None:
        """No token → 401 — the minimal gate for the global-inert read."""
        unauthenticated_app = create_app()
        transport = ASGITransport(app=unauthenticated_app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(_MODEL_URL)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
