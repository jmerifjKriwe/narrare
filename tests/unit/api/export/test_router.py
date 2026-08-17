"""Router + DI smoke + HTTP-integration tests for the export domain.

RULE-06 (router purity) and RULE-19 (SessionDep, not bare AsyncSession) are
mechanically enforced by ``scripts/check_architecture.py`` — these tests cover
what the checker cannot: that the four routes are registered with the right
paths/methods, the DI factories wire the renderers + production enqueuer, and
that the real routes + the ``ExportError`` → HTTP mapping (mirrored from
``_app/main.py``) behave end-to-end against a minimal FastAPI app with
dependency overrides (no DB / no lifespan).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from narrare.export import registry
from narrare.export.contracts import Artifact
from narrare.export.dependencies import get_export_renderers, get_export_service
from narrare.export.errors import (
    ExportArtifactExpiredError,
    ExportError,
    ExportFormatUnavailableError,
    ExportJobNotFoundError,
)
from narrare.export.options import ExportFormat
from narrare.export.router import router as export_router
from narrare.export.service import ExportServiceImpl
from narrare.export.tasks import enqueue_export
from tests.unit.api.export.conftest import FakeRenderer, RecordingEnqueuer

if TYPE_CHECKING:
    from collections.abc import Iterator


class TestExportRouterShape:
    def test_has_the_four_routes_with_expected_paths(self) -> None:
        paths_methods = {
            (route.path, frozenset(route.methods or set()))
            for route in export_router.routes
            if isinstance(route, APIRoute)
        }
        assert ("/export/formats", frozenset({"GET"})) in paths_methods
        assert ("/export", frozenset({"POST"})) in paths_methods
        assert ("/export/jobs/{job_id}", frozenset({"GET"})) in paths_methods
        assert ("/export/jobs/{job_id}/artifact", frozenset({"GET"})) in paths_methods

    def test_router_tag_and_prefix(self) -> None:
        assert export_router.prefix == "/export"
        assert "export" in export_router.tags


class TestDependencyFactories:
    def test_get_export_renderers_returns_four_renderers(self) -> None:
        renderers = get_export_renderers()
        assert set(renderers.keys()) == {
            ExportFormat.PDF,
            ExportFormat.EPUB,
            ExportFormat.MARKDOWN,
            ExportFormat.DOCX,
        }
        # Each renderer advertises its own format.
        for fmt, renderer in renderers.items():
            assert renderer.format == fmt

    def test_get_export_service_wires_renderers_and_production_enqueuer(self) -> None:
        service = get_export_service()
        assert isinstance(service, ExportServiceImpl)
        assert set(service._renderers.keys()) == {
            ExportFormat.PDF,
            ExportFormat.EPUB,
            ExportFormat.MARKDOWN,
            ExportFormat.DOCX,
        }
        # The production enqueuer is wired (not a recording fake).
        assert service._enqueue is enqueue_export


class TestAppRegistrationSmoke:
    def test_export_routes_are_mounted_on_the_app(self) -> None:
        # ``create_app`` builds the FastAPI app + registers every router (no
        # lifespan / DB). The OpenAPI schema is the canonical flattened view of
        # mounted endpoints (robust across FastAPI versions, which wrap
        # included routers in ``_IncludedRouter``). Asserting these paths are
        # present confirms the mount + that importing the router graph is clean.
        from narrare._app.main import create_app

        app = create_app(test_mode=True)
        paths = set(app.openapi()["paths"].keys())
        assert "/api/v1/export/formats" in paths
        assert "/api/v1/export" in paths
        assert "/api/v1/export/jobs/{job_id}" in paths
        assert "/api/v1/export/jobs/{job_id}/artifact" in paths


def _build_export_app(service: ExportServiceImpl) -> tuple[FastAPI, TestClient]:
    """Minimal FastAPI app: real export router + ExportError handler (mirrors
    ``_app/main.py``) + ``get_export_service`` overridden to ``service``.

    No lifespan / DB: the in-memory registry + the fakes carry the state.
    """

    app = FastAPI()
    app.include_router(export_router, prefix="/api/v1")

    @app.exception_handler(ExportError)
    async def _export_error_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: ExportError
    ) -> JSONResponse:
        if isinstance(exc, ExportJobNotFoundError):
            status_code = 404
        elif isinstance(exc, ExportArtifactExpiredError):
            status_code = 410
        elif isinstance(exc, ExportFormatUnavailableError):
            status_code = 503
        else:
            status_code = 400
        return JSONResponse(
            status_code=status_code, content={"detail": str(exc), "code": type(exc).__name__}
        )

    app.dependency_overrides[get_export_service] = lambda: service
    return app, TestClient(app)


def _service_with(renderers: dict[ExportFormat, FakeRenderer]) -> ExportServiceImpl:
    return ExportServiceImpl(renderers=renderers, enqueue=RecordingEnqueuer())


@pytest.fixture
def _export_app() -> Iterator[tuple[TestClient, ExportServiceImpl]]:
    service = _service_with(
        {
            ExportFormat.PDF: FakeRenderer(ExportFormat.PDF, available=False),
            ExportFormat.EPUB: FakeRenderer(ExportFormat.EPUB, available=True),
            ExportFormat.MARKDOWN: FakeRenderer(ExportFormat.MARKDOWN, available=True),
        }
    )
    _app, client = _build_export_app(service)
    yield client, service


class TestRouterEndpoints:
    """End-to-end HTTP behaviour: routes + ExportError → HTTP mapping."""

    def test_list_formats_returns_availability(
        self, _export_app: tuple[TestClient, ExportServiceImpl]
    ) -> None:
        client, _service = _export_app
        response = client.get("/api/v1/export/formats")
        assert response.status_code == 200
        body = {row["format"]: row["available"] for row in response.json()}
        assert body == {
            ExportFormat.PDF.value: False,
            ExportFormat.EPUB.value: True,
            ExportFormat.MARKDOWN.value: True,
        }

    def test_post_export_with_unavailable_format_returns_503(
        self, _export_app: tuple[TestClient, ExportServiceImpl]
    ) -> None:
        client, _service = _export_app
        response = client.post(
            "/api/v1/export",
            json={"novel_id": str(uuid4()), "options": {"format": ExportFormat.PDF.value}},
        )
        assert response.status_code == 503
        assert response.json()["code"] == "ExportFormatUnavailableError"
        # Fast-fail: no job was created.
        assert registry._JOBS == {}

    def test_post_export_with_available_format_creates_job(
        self, _export_app: tuple[TestClient, ExportServiceImpl]
    ) -> None:
        client, service = _export_app
        novel_id = uuid4()
        response = client.post(
            "/api/v1/export",
            json={"novel_id": str(novel_id), "options": {"format": ExportFormat.MARKDOWN.value}},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "pending"
        assert body["format"] == ExportFormat.MARKDOWN.value
        # The dispatcher recorded the call.
        assert len(service._enqueue.calls) == 1

    def test_get_unknown_job_returns_404(
        self, _export_app: tuple[TestClient, ExportServiceImpl]
    ) -> None:
        client, _service = _export_app
        response = client.get("/api/v1/export/jobs/does-not-exist")
        assert response.status_code == 404
        assert response.json()["code"] == "ExportJobNotFoundError"

    def test_consume_artifact_with_wrong_token_returns_410(
        self, _export_app: tuple[TestClient, ExportServiceImpl], tmp_path: Path
    ) -> None:
        client, _service = _export_app
        # Seed the registry with a COMPLETED job (the runner would do this).
        job = registry.create(uuid4(), ExportFormat.MARKDOWN)
        registry.mark_completed(
            job.job_id,
            Artifact(
                format=ExportFormat.MARKDOWN,
                path=tmp_path / "art.md",
                media_type="text/markdown",
                suggested_filename="novel.md",
            ),
        )
        # A wrong token → 410 (ExportArtifactExpiredError).
        response = client.get(
            f"/api/v1/export/jobs/{job.job_id}/artifact",
            params={"token": "wrong-token"},
        )
        assert response.status_code == 410
        assert response.json()["code"] == "ExportArtifactExpiredError"
