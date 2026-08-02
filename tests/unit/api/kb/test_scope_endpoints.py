"""Unit tests for the KB scope-toggle endpoints (promote/demote HTTP paths).

Series Foundation Spec 1, Slice 3 Task 3.7.

Exercises the two ``kb/router_scope.py`` endpoints against a minimal FastAPI
app with dependency overrides (no DB / no JWT). The real
:class:`KBScopeService` is wired to a fake KB repo + ownership-seeded Novel /
Series fakes, so the full chain is covered end-to-end at unit level: ownership
``ForbiddenError`` → HTTP 403, repository ``ConflictError`` → HTTP 409, success
→ HTTP 200. A minimal handler mirrors the production mapping in ``_app/main.py``
(only the errors this router raises).

Service-level logic (delegation, ownership) is covered by the sibling
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
from narrare_core.series.schemas import Series
from narrare_core.shared.errors import ConflictError, ForbiddenError
from tests.factories import make_novel
from tests.fakes.fake_novel_repo import FakeNovelRepository
from tests.fakes.fake_series_repo import FakeSeriesRepository

from ._scope_service_helpers import FakeKBRepo, make_novel_entry, make_series_entry

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def scope_app() -> Iterator[
    tuple[FastAPI, TestClient, FakeKBRepo, str, uuid.UUID, uuid.UUID, uuid.UUID]
]:
    """Minimal FastAPI app wiring the real KBScopeService with ownership-seeded fakes.

    Returns the app, client, kb fake, and the seeded user/novel/series/target ids
    so tests can target owned resources. Auth is overridden to the seeded user.
    """
    user_id = uuid.uuid4()
    novel_id = uuid.uuid4()
    series_id = uuid.uuid4()
    target_novel_id = uuid.uuid4()

    kb_repo = FakeKBRepo()
    novel_repo = FakeNovelRepository()
    novel_repo.seed(make_novel(id=novel_id, user_id=user_id))
    novel_repo.seed(make_novel(id=target_novel_id, user_id=user_id))
    series_repo = FakeSeriesRepository()
    series_repo.seed(Series(id=series_id, user_id=user_id, title="Test Series"))

    app = FastAPI()
    app.include_router(kb_router, prefix="/api/v1")

    @app.exception_handler(ConflictError)
    async def _conflict_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: ConflictError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc), "code": exc.code})

    @app.exception_handler(ForbiddenError)
    async def _forbidden_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: ForbiddenError
    ) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc), "code": exc.code})

    app.dependency_overrides[get_current_user_id] = lambda: str(user_id)
    app.dependency_overrides[get_kb_scope_service] = lambda: KBScopeService(
        kb_repo, novel_repo, series_repo
    )
    with TestClient(app) as client:
        yield app, client, kb_repo, str(user_id), novel_id, series_id, target_novel_id


class TestPromoteEndpoint:
    def test_returns_200_with_promoted_entry(self, scope_app: tuple) -> None:
        """A successful promote returns 200 and the promoted SeriesKBEntry."""
        _, client, kb_repo, _, novel_id, _, _ = scope_app
        entry_id = uuid.uuid4()
        series_id = uuid.uuid4()
        kb_repo.set_promote_result(make_series_entry(id=entry_id, series_id=series_id))

        response = client.post(f"/api/v1/novels/{novel_id}/kb/{entry_id}/promote")

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(entry_id)
        assert body["scope"] == "series"
        assert body["series_id"] == str(series_id)
        assert body["novel_id"] is None

    def test_returns_403_when_novel_not_owned(self, scope_app: tuple) -> None:
        """A novel not owned by the caller → 403 (anti-enumeration)."""
        _, client, _, _, _, _, _ = scope_app

        response = client.post(f"/api/v1/novels/{uuid.uuid4()}/kb/{uuid.uuid4()}/promote")

        assert response.status_code == 403
        assert response.json()["code"] == "FORBIDDEN"

    def test_returns_409_on_invariant_violation(self, scope_app: tuple) -> None:
        """A repository ConflictError (via service) yields HTTP 409."""
        _, client, kb_repo, _, novel_id, _, _ = scope_app
        kb_repo.set_promote_error(ConflictError("Entry not an overlay"))

        response = client.post(f"/api/v1/novels/{novel_id}/kb/{uuid.uuid4()}/promote")

        assert response.status_code == 409
        assert response.json()["code"] == "CONFLICT"


class TestDemoteEndpoint:
    def test_returns_200_with_demoted_entry(self, scope_app: tuple) -> None:
        """A successful demote returns 200 and the demoted NovelKBEntry."""
        _, client, kb_repo, _, _, series_id, target_novel_id = scope_app
        entry_id = uuid.uuid4()
        kb_repo.set_demote_result(make_novel_entry(id=entry_id, novel_id=target_novel_id))

        response = client.post(
            f"/api/v1/novels/{target_novel_id}/kb/{entry_id}/demote",
            json={"series_id": str(series_id), "target_novel_id": str(target_novel_id)},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["id"] == str(entry_id)
        assert body["scope"] == "novel"
        assert body["novel_id"] == str(target_novel_id)
        assert kb_repo.demote_calls == [(series_id, entry_id, target_novel_id)]

    def test_returns_403_when_series_not_owned(self, scope_app: tuple) -> None:
        """A series not owned by the caller → 403."""
        _, client, _, _, _, _, target_novel_id = scope_app

        response = client.post(
            f"/api/v1/novels/{target_novel_id}/kb/{uuid.uuid4()}/demote",
            json={
                "series_id": str(uuid.uuid4()),  # not owned / unknown
                "target_novel_id": str(target_novel_id),
            },
        )

        assert response.status_code == 403

    def test_returns_409_on_invariant_violation(self, scope_app: tuple) -> None:
        """A repository ConflictError (guard/invariant) yields HTTP 409."""
        _, client, kb_repo, _, _, series_id, target_novel_id = scope_app
        kb_repo.set_demote_error(ConflictError("rely on it"))

        response = client.post(
            f"/api/v1/novels/{target_novel_id}/kb/{uuid.uuid4()}/demote",
            json={"series_id": str(series_id), "target_novel_id": str(target_novel_id)},
        )

        assert response.status_code == 409
        assert response.json()["code"] == "CONFLICT"

    def test_returns_422_on_missing_body_fields(self, scope_app: tuple) -> None:
        """A body missing series_id/target_novel_id is rejected with 422."""
        _, client, _, _, _, _, _ = scope_app
        response = client.post(
            f"/api/v1/novels/{uuid.uuid4()}/kb/{uuid.uuid4()}/demote",
            json={"series_id": str(uuid.uuid4())},
        )
        assert response.status_code == 422
