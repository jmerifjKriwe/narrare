"""RT-S1a — IDOR regression tests: owned-novel gate on POST /export.

Before the S1 fix, the export request path carried no caller identity at all:
``ExportServiceImpl.export`` trusted ``novel_id`` and created a job for ANY
authenticated caller, and the background runner then rendered the full foreign
manuscript (GAP-CRITICAL — worst exfiltration vector of the P-SEC sweep).

The fix is Pattern B (owned-parent gate, notes/chat precedent): the FIRST
statement of ``export`` resolves the novel through an
``OwnedLinkLookupProtocol`` adapter (user-scoped ``NovelRepository.get_by_id``)
and raises core ``NotFoundError`` → HTTP 404 via the global handler BEFORE any
job creation or dispatch. Foreign and unknown novels are indistinguishable
(anti-enumeration): the error message is a pure function of the caller's input.

Matrix (plan S1): (1) owner → 201 unchanged, (2) foreign novel → 404 AND no
side effect (no job row, no dispatch), (3) unknown novel → 404 identical in
shape to (2).
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from narrare._app.dependencies import get_current_user_id
from narrare.export import registry
from narrare.export.contracts import Artifact, ExportJobStatus
from narrare.export.dependencies import get_export_service
from narrare.export.errors import (
    ExportArtifactExpiredError,
    ExportError,
    ExportJobNotFoundError,
)
from narrare.export.options import ExportFormat
from narrare.export.router import router as export_router
from narrare.export.service import ExportServiceImpl
from narrare_core.shared.errors import NotFoundError
from tests.unit.api.export.conftest import (
    FakeNovelLookup,
    FakeRenderer,
    RecordingEnqueuer,
    make_options,
)

USER_A = uuid4()  # rightful owner
USER_B = uuid4()  # foreign caller


def _service_with_lookup(
    lookup: FakeNovelLookup,
) -> tuple[ExportServiceImpl, RecordingEnqueuer]:
    """Service with one available renderer + a recording enqueuer (no I/O)."""
    enqueue = RecordingEnqueuer()
    service = ExportServiceImpl(
        renderers={ExportFormat.MARKDOWN: FakeRenderer(ExportFormat.MARKDOWN, available=True)},
        enqueue=enqueue,
        novel_lookup=lookup,
    )
    return service, enqueue


def _ownership_app(service: ExportServiceImpl, *, caller: UUID) -> TestClient:
    """Minimal app: real export router + the two error handlers mirrored from
    ``_app/main.py`` (NarrareError → 404 for NotFoundError; ExportError) +
    service + auth overridden to ``caller`` (no DB / no lifespan).
    """
    app = FastAPI()
    app.include_router(export_router, prefix="/api/v1")

    @app.exception_handler(NotFoundError)
    async def _not_found_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: NotFoundError
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc), "code": exc.code})

    @app.exception_handler(ExportError)
    async def _export_error_handler(  # pyright: ignore[reportUnusedFunction]
        _: Request, exc: ExportError
    ) -> JSONResponse:
        # Mirrors _app/main.py: unknown/foreign job → 404, expired → 410,
        # unavailable format → 503, other ExportError → 400.
        from narrare.export.errors import (
            ExportArtifactExpiredError,
            ExportFormatUnavailableError,
            ExportJobNotFoundError,
        )

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

    async def _mock_auth() -> str:
        return str(caller)

    app.dependency_overrides[get_current_user_id] = _mock_auth
    return TestClient(app)


class TestExportGateServiceLevel:
    """``ExportServiceImpl.export`` gates BEFORE job creation (Pattern B)."""

    @pytest.mark.asyncio
    async def test_foreign_novel_raises_not_found_and_creates_no_job(self) -> None:

        lookup = FakeNovelLookup()
        foreign_novel = uuid4()
        lookup.seed_owned(foreign_novel, USER_A)  # exists — owned by USER_A
        service, enqueue = _service_with_lookup(lookup)

        with pytest.raises(NotFoundError):
            await service.export(foreign_novel, make_options(), USER_B)

        # No side effect: no job registered, nothing dispatched.
        assert enqueue.calls == []
        assert registry._JOBS == {}

    @pytest.mark.asyncio
    async def test_unknown_novel_raises_not_found(self) -> None:

        lookup = FakeNovelLookup()
        unknown_novel = uuid4()  # never seeded
        service, enqueue = _service_with_lookup(lookup)

        with pytest.raises(NotFoundError):
            await service.export(unknown_novel, make_options(), USER_B)
        assert enqueue.calls == []
        assert registry._JOBS == {}

    @pytest.mark.asyncio
    async def test_foreign_and_unknown_are_indistinguishable(self) -> None:
        """Anti-enumeration: the error is a pure function of the input id."""

        lookup = FakeNovelLookup()
        foreign_novel, unknown_novel = uuid4(), uuid4()
        lookup.seed_owned(foreign_novel, USER_A)
        service, _enqueue = _service_with_lookup(lookup)

        with pytest.raises(NotFoundError) as foreign_exc:
            await service.export(foreign_novel, make_options(), USER_B)
        with pytest.raises(NotFoundError) as unknown_exc:
            await service.export(unknown_novel, make_options(), USER_B)

        assert type(foreign_exc.value) is type(unknown_exc.value)
        assert str(foreign_exc.value) == f"Novel ({foreign_novel}) not found"
        assert str(unknown_exc.value) == f"Novel ({unknown_novel}) not found"

    @pytest.mark.asyncio
    async def test_owner_creates_pending_job_unchanged(self) -> None:

        lookup = FakeNovelLookup()
        owned_novel = uuid4()
        lookup.seed_owned(owned_novel, USER_A)
        service, enqueue = _service_with_lookup(lookup)

        job = await service.export(owned_novel, make_options(), USER_A)

        assert job.status is ExportJobStatus.PENDING
        assert len(enqueue.calls) == 1
        # The job is in the registry (bound to USER_A).
        assert registry.get(job.job_id, USER_A).job_id == job.job_id


class TestExportGateHttpLevel:
    """POST /api/v1/export — the 404 matrix through the real router."""

    def _post(self, client: TestClient, novel_id: UUID):
        return client.post(
            "/api/v1/export",
            json={"novel_id": str(novel_id), "options": {"format": "md"}},
        )

    def test_owner_returns_201(self) -> None:
        lookup = FakeNovelLookup()
        owned_novel = uuid4()
        lookup.seed_owned(owned_novel, USER_A)
        service, enqueue = _service_with_lookup(lookup)
        client = _ownership_app(service, caller=USER_A)

        response = self._post(client, owned_novel)

        assert response.status_code == 201
        assert response.json()["status"] == "pending"
        assert len(enqueue.calls) == 1

    def test_foreign_novel_returns_404_and_creates_no_job(self) -> None:
        lookup = FakeNovelLookup()
        foreign_novel = uuid4()
        lookup.seed_owned(foreign_novel, USER_A)
        service, enqueue = _service_with_lookup(lookup)
        client = _ownership_app(service, caller=USER_B)

        response = self._post(client, foreign_novel)

        assert response.status_code == 404
        assert response.json()["code"] == "NOT_FOUND"
        # No side effect: the registry stayed empty, nothing dispatched.
        assert registry._JOBS == {}
        assert enqueue.calls == []

    def test_unknown_novel_404_matches_foreign_shape(self) -> None:
        """Unknown and foreign 404s are identical up to the echoed input id."""
        lookup = FakeNovelLookup()
        foreign_novel, unknown_novel = uuid4(), uuid4()
        lookup.seed_owned(foreign_novel, USER_A)
        service, _enqueue = _service_with_lookup(lookup)
        client = _ownership_app(service, caller=USER_B)

        foreign = self._post(client, foreign_novel)
        unknown = self._post(client, unknown_novel)

        assert foreign.status_code == unknown.status_code == 404
        foreign_body, unknown_body = foreign.json(), unknown.json()
        assert foreign_body["code"] == unknown_body["code"] == "NOT_FOUND"
        # detail is a pure function of the caller's own input — no
        # existence/ownership information leaks.
        assert foreign_body["detail"] == f"Novel ({foreign_novel}) not found"
        assert unknown_body["detail"] == f"Novel ({unknown_novel}) not found"


# ---------------------------------------------------------------------------
# S1b — owner-bound jobs: poll + artifact download are owner-only
# ---------------------------------------------------------------------------


def _seed_completed_job(owner: UUID, tmp_dir: Path | None = None) -> tuple[str, str]:
    """Seed a COMPLETED job owned by ``owner`` directly in the registry
    (what the background runner does) and return ``(job_id, raw_token)``.

    The raw token exists only inside the delivery ``artifact_url`` — exactly
    what a polling thief would copy. `tmp_dir` defaults to a path that need
    not exist (the registry never reads the file on the rejected paths).
    """
    artifact = Artifact(
        format=ExportFormat.MARKDOWN,
        path=(tmp_dir or Path("/tmp")) / "victim-manuscript.md",
        media_type="text/markdown",
        suggested_filename="victim-manuscript.md",
    )
    job = registry.create(uuid4(), owner, ExportFormat.MARKDOWN)
    registry.mark_completed(job.job_id, artifact)
    completed = registry.get(job.job_id, owner)
    assert completed.artifact_url is not None
    token = parse_qs(urlparse(completed.artifact_url).query)["token"][0]
    return job.job_id, token


class TestJobOwnershipServiceLevel:
    """``get_job`` / ``consume_artifact`` treat owner-mismatch as unknown."""

    @pytest.mark.asyncio
    async def test_owner_binding_survives_poll_for_owner(self) -> None:
        job_id, _token = _seed_completed_job(USER_A)
        service, _enqueue = _service_with_lookup(FakeNovelLookup())

        polled = await service.get_job(job_id, USER_A)

        assert polled.job_id == job_id
        assert polled.status is ExportJobStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_foreign_user_polling_owners_job_raises_not_found(self) -> None:
        job_id, _token = _seed_completed_job(USER_A)
        service, _enqueue = _service_with_lookup(FakeNovelLookup())

        with pytest.raises(ExportJobNotFoundError):
            await service.get_job(job_id, USER_B)

    @pytest.mark.asyncio
    async def test_foreign_and_unknown_job_poll_are_indistinguishable(self) -> None:
        """Anti-enumeration: foreign-owned and unknown job ids raise the same
        error with the same message shape (a pure function of the input)."""
        job_id, _token = _seed_completed_job(USER_A)
        service, _enqueue = _service_with_lookup(FakeNovelLookup())

        with pytest.raises(ExportJobNotFoundError) as foreign_exc:
            await service.get_job(job_id, USER_B)
        with pytest.raises(ExportJobNotFoundError) as unknown_exc:
            await service.get_job("totally-unknown-job", USER_B)

        assert type(foreign_exc.value) is type(unknown_exc.value)
        assert str(foreign_exc.value) == f"Export job '{job_id}' not found"
        assert str(unknown_exc.value) == "Export job 'totally-unknown-job' not found"

    @pytest.mark.asyncio
    async def test_foreign_user_consume_with_valid_token_raises_and_leaves_artifact(
        self, tmp_path: Path
    ) -> None:
        """Stolen-token poll path: USER_B holds the FULL valid artifact_url of
        USER_A's job — the consume must 404 WITHOUT flipping the single-use
        flag (the owner can still download)."""
        job_id, token = _seed_completed_job(USER_A, tmp_path)
        service, _enqueue = _service_with_lookup(FakeNovelLookup())

        with pytest.raises(ExportJobNotFoundError):
            await service.consume_artifact(job_id, token, USER_B)

        # No side effect: the artifact is still unconsumed for the owner…
        consumed = await service.consume_artifact(job_id, token, USER_A)
        assert consumed is not None
        # …and single-use still holds afterwards.
        with pytest.raises(ExportArtifactExpiredError):
            await service.consume_artifact(job_id, token, USER_A)

    @pytest.mark.asyncio
    async def test_export_binds_creating_user_as_job_owner(self) -> None:
        """The job created by ``export`` is bound to the caller: another
        authenticated user cannot poll it (regression for the binding itself)."""
        lookup = FakeNovelLookup()
        owned_novel = uuid4()
        lookup.seed_owned(owned_novel, USER_A)
        service, _enqueue = _service_with_lookup(lookup)

        job = await service.export(owned_novel, make_options(), USER_A)

        assert (await service.get_job(job.job_id, USER_A)).job_id == job.job_id
        with pytest.raises(ExportJobNotFoundError):
            await service.get_job(job.job_id, USER_B)


class TestJobOwnershipHttpLevel:
    """GET /jobs/{job_id} + /artifact through the real router."""

    def test_owner_poll_returns_200(self) -> None:
        job_id, _token = _seed_completed_job(USER_A)
        service, _enqueue = _service_with_lookup(FakeNovelLookup())
        client = _ownership_app(service, caller=USER_A)

        response = client.get(f"/api/v1/export/jobs/{job_id}")

        assert response.status_code == 200
        assert response.json()["job_id"] == job_id

    def test_foreign_poll_returns_404_matching_unknown_job(self) -> None:
        job_id, _token = _seed_completed_job(USER_A)
        service, _enqueue = _service_with_lookup(FakeNovelLookup())
        client = _ownership_app(service, caller=USER_B)

        foreign = client.get(f"/api/v1/export/jobs/{job_id}")
        unknown = client.get("/api/v1/export/jobs/does-not-exist")

        assert foreign.status_code == unknown.status_code == 404
        assert foreign.json()["code"] == unknown.json()["code"] == "ExportJobNotFoundError"
        # Identical shape: detail echoes only the caller's own input.
        assert foreign.json()["detail"] == f"Export job '{job_id}' not found"
        assert unknown.json()["detail"] == "Export job 'does-not-exist' not found"

    def test_foreign_download_with_valid_token_returns_404(self, tmp_path: Path) -> None:
        """The worst vector closed: foreign user + full valid token → 404
        (never 200, never 410 — a 410 would confirm the job exists)."""
        job_id, token = _seed_completed_job(USER_A, tmp_path)
        service, _enqueue = _service_with_lookup(FakeNovelLookup())
        client = _ownership_app(service, caller=USER_B)

        response = client.get(f"/api/v1/export/jobs/{job_id}/artifact", params={"token": token})

        assert response.status_code == 404
        assert response.json()["code"] == "ExportJobNotFoundError"

    def test_owner_download_with_valid_token_streams_artifact(self, tmp_path: Path) -> None:
        artifact_path = tmp_path / "owner-manuscript.md"
        artifact_path.write_text("owner payload", encoding="utf-8")
        job = registry.create(uuid4(), USER_A, ExportFormat.MARKDOWN)
        registry.mark_completed(
            job.job_id,
            Artifact(
                format=ExportFormat.MARKDOWN,
                path=artifact_path,
                media_type="text/markdown",
                suggested_filename="owner-manuscript.md",
            ),
        )
        completed = registry.get(job.job_id, USER_A)
        assert completed.artifact_url is not None
        token = parse_qs(urlparse(completed.artifact_url).query)["token"][0]
        service, _enqueue = _service_with_lookup(FakeNovelLookup())
        client = _ownership_app(service, caller=USER_A)

        response = client.get(f"/api/v1/export/jobs/{job.job_id}/artifact", params={"token": token})

        assert response.status_code == 200
        assert response.text == "owner payload"
