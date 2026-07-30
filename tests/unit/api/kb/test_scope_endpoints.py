"""Unit tests for the KB scope-toggle endpoints (promote/demote HTTP paths).

Series Foundation Spec 1, Slice 3 Task 3.7.

Exercises the two ``kb/router_scope.py`` endpoints against a minimal FastAPI
app with dependency overrides (no DB / no JWT). The real
:class:`KBScopeService` is wired to a fake repository, so the full chain is
covered end-to-end at unit level: repository ``ValueError`` → service
``ConflictError`` → HTTP 409. A minimal ``ConflictError``→409 handler mirrors
the production mapping in ``_app/main.py`` (only the error this router raises).

Service-level logic (delegation, translation) is covered by the sibling
``test_scope_service.py`` (RULE-04 file-size split).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from narrare._app.dependencies_auth import get_current_user_id
from narrare.kb.dependencies import get_kb_scope_service
from narrare.kb.router import router as kb_router
from narrare.kb.scope_service import KBScopeService
from narrare_core.shared.errors import ConflictError

from ._scope_service_helpers import FakeKBRepo, make_novel_entry, make_series_entry

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def fake_repo() -> FakeKBRepo:
    return FakeKBRepo()


@pytest.fixture
def scope_app(fake_repo: FakeKBRepo) -> Iterator[tuple[FastAPI, TestClient]]:
    """Minimal FastAPI app wiring the real KBScopeService with a fake repo.

    Auth and the scope-service dependency are overridden so no DB/JWT is
    needed. A minimal ConflictError→409 handler mirrors the production
    mapping in ``_app/main.py`` (only the error this router can raise).
    """
    app = FastAPI()
    app.include_router(kb_router, prefix="/api/v1")

    @app.exception_handler(ConflictError)
    async def _conflict_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: ConflictError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc), "code": exc.code})

    app.dependency_overrides[get_current_user_id] = lambda: "test-user"
    app.dependency_overrides[get_kb_scope_service] = lambda: KBScopeService(
        fake_repo  # type: ignore[arg-type]
    )
    with TestClient(app) as client:
        yield app, client


class TestPromoteEndpoint:
    def test_returns_200_with_promoted_entry(
        self, fake_repo: FakeKBRepo, scope_app: tuple[FastAPI, TestClient]
    ) -> None:
        """A successful promote returns 200 and the promoted SeriesKBEntry."""
        novel_id = uuid.uuid4()
        entry_id = uuid.uuid4()
        series_id = uuid.uuid4()
        fake_repo.set_promote_result(make_series_entry(id=entry_id, series_id=series_id))

        _, client = scope_app
        response = client.post(f"/api/v1/novels/{novel_id}/kb/{entry_id}/promote")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(entry_id)
        assert body["scope"] == "series"
        assert body["series_id"] == str(series_id)
        assert body["novel_id"] is None

    def test_returns_409_on_invariant_violation(
        self, fake_repo: FakeKBRepo, scope_app: tuple[FastAPI, TestClient]
    ) -> None:
        """A repository ValueError (via service ConflictError) yields HTTP 409."""
        fake_repo.set_promote_error(ValueError("Entry not found or not overlay"))

        _, client = scope_app
        response = client.post(f"/api/v1/novels/{uuid.uuid4()}/kb/{uuid.uuid4()}/promote")

        assert response.status_code == 409
        assert response.json()["code"] == "CONFLICT"


class TestDemoteEndpoint:
    def test_returns_200_with_demoted_entry(
        self, fake_repo: FakeKBRepo, scope_app: tuple[FastAPI, TestClient]
    ) -> None:
        """A successful demote returns 200 and the demoted NovelKBEntry."""
        novel_id = uuid.uuid4()
        entry_id = uuid.uuid4()
        series_id = uuid.uuid4()
        target_novel_id = uuid.uuid4()
        fake_repo.set_demote_result(make_novel_entry(id=entry_id, novel_id=target_novel_id))

        _, client = scope_app
        response = client.post(
            f"/api/v1/novels/{novel_id}/kb/{entry_id}/demote",
            json={"series_id": str(series_id), "target_novel_id": str(target_novel_id)},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(entry_id)
        assert body["scope"] == "novel"
        assert body["novel_id"] == str(target_novel_id)
        assert fake_repo.demote_calls == [(series_id, entry_id, target_novel_id)]

    def test_returns_409_on_invariant_violation(
        self, fake_repo: FakeKBRepo, scope_app: tuple[FastAPI, TestClient]
    ) -> None:
        """A repository ValueError (via service ConflictError) yields HTTP 409."""
        fake_repo.set_demote_error(ValueError("Entry not canon of series"))

        _, client = scope_app
        response = client.post(
            f"/api/v1/novels/{uuid.uuid4()}/kb/{uuid.uuid4()}/demote",
            json={"series_id": str(uuid.uuid4()), "target_novel_id": str(uuid.uuid4())},
        )

        assert response.status_code == 409
        assert response.json()["code"] == "CONFLICT"

    def test_returns_422_on_missing_body_fields(
        self, scope_app: tuple[FastAPI, TestClient]
    ) -> None:
        """A body missing series_id/target_novel_id is rejected with 422."""
        _, client = scope_app
        response = client.post(
            f"/api/v1/novels/{uuid.uuid4()}/kb/{uuid.uuid4()}/demote",
            json={"series_id": str(uuid.uuid4())},
        )
        assert response.status_code == 422
