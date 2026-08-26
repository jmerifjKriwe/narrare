"""Unit tests for ``ExportServiceImpl`` — the RULE-12 public API."""

from __future__ import annotations

from uuid import uuid4

import pytest

from narrare.export import registry
from narrare.export.contracts import ExportJobStatus
from narrare.export.errors import (
    ExportArtifactExpiredError,
    ExportFormatUnavailableError,
    ExportJobNotFoundError,
)
from narrare.export.options import ExportFormat
from narrare.export.service import ExportServiceImpl
from tests.unit.api.export.conftest import (
    FakeNovelLookup,
    FakeRenderer,
    RecordingEnqueuer,
    make_options,
)


def _service(
    *,
    renderers: dict[ExportFormat, FakeRenderer] | None = None,
    enqueue: RecordingEnqueuer | None = None,
    lookup: FakeNovelLookup | None = None,
) -> ExportServiceImpl:
    """Build a service with all three renderers available by default.

    The default lookup owns ``NOVEL_ID`` for ``USER_ID`` (the happy-path
    caller); ownership tests build their own scoped lookup.
    """
    renderers = renderers or {
        ExportFormat.PDF: FakeRenderer(ExportFormat.PDF, available=True),
        ExportFormat.EPUB: FakeRenderer(ExportFormat.EPUB, available=True),
        ExportFormat.MARKDOWN: FakeRenderer(ExportFormat.MARKDOWN, available=True),
    }
    owned_lookup = lookup
    if owned_lookup is None:
        owned_lookup = FakeNovelLookup()
        owned_lookup.seed_owned(NOVEL_ID, USER_ID)
    return ExportServiceImpl(
        renderers=renderers,
        enqueue=enqueue or RecordingEnqueuer(),
        novel_lookup=owned_lookup,
    )


NOVEL_ID = uuid4()
USER_ID = uuid4()


class TestListFormats:
    @pytest.mark.asyncio
    async def test_reports_each_renderers_availability(self) -> None:
        renderers = {
            ExportFormat.PDF: FakeRenderer(ExportFormat.PDF, available=True),
            ExportFormat.EPUB: FakeRenderer(ExportFormat.EPUB, available=False),
            ExportFormat.MARKDOWN: FakeRenderer(ExportFormat.MARKDOWN, available=True),
        }
        service = _service(renderers=renderers)
        result = await service.list_formats()
        assert dict(result) == {
            ExportFormat.PDF: True,
            ExportFormat.EPUB: False,
            ExportFormat.MARKDOWN: True,
        }

    @pytest.mark.asyncio
    async def test_returns_stable_order(self) -> None:
        service = _service()
        result = await service.list_formats()
        # list_formats iterates the injected dict in insertion order;
        # _service() builds it in exactly this literal order.
        assert [fmt for fmt, _ok in result] == [
            ExportFormat.PDF,
            ExportFormat.EPUB,
            ExportFormat.MARKDOWN,
        ]


class TestExportFastFail:
    @pytest.mark.asyncio
    async def test_unavailable_format_raises_before_creating_job(self) -> None:
        enqueue = RecordingEnqueuer()
        renderers = {ExportFormat.MARKDOWN: FakeRenderer(ExportFormat.MARKDOWN, available=False)}
        service = _service(renderers=renderers, enqueue=enqueue)

        with pytest.raises(ExportFormatUnavailableError):
            await service.export(NOVEL_ID, make_options(ExportFormat.MARKDOWN), USER_ID)

        # No job was registered and nothing was dispatched (RULE-11 fast-fail).
        assert enqueue.calls == []
        assert registry._JOBS == {}

    @pytest.mark.asyncio
    async def test_unregistered_format_raises(self) -> None:
        service = _service(renderers={ExportFormat.PDF: FakeRenderer(ExportFormat.PDF)})
        with pytest.raises(ExportFormatUnavailableError):
            await service.export(NOVEL_ID, make_options(ExportFormat.MARKDOWN), USER_ID)


class TestExportHappyPath:
    @pytest.mark.asyncio
    async def test_creates_pending_job_and_dispatches(self) -> None:
        enqueue = RecordingEnqueuer()
        service = _service(enqueue=enqueue)

        job = await service.export(NOVEL_ID, make_options(ExportFormat.MARKDOWN), USER_ID)

        assert job.status is ExportJobStatus.PENDING
        assert job.format is ExportFormat.MARKDOWN
        # The dispatcher received the job_id + novel_id + options.
        assert len(enqueue.calls) == 1
        dispatched_job_id, dispatched_novel, dispatched_opts = enqueue.calls[0]
        assert dispatched_job_id == job.job_id
        assert dispatched_novel == NOVEL_ID
        assert dispatched_opts.format is ExportFormat.MARKDOWN
        # The job is in the registry.
        assert registry.get(job.job_id, USER_ID).job_id == job.job_id


class TestGetJobAndConsume:
    @pytest.mark.asyncio
    async def test_get_unknown_raises(self) -> None:
        service = _service()
        with pytest.raises(ExportJobNotFoundError):
            await service.get_job("nope", USER_ID)

    @pytest.mark.asyncio
    async def test_consume_unknown_raises(self) -> None:
        service = _service()
        with pytest.raises(ExportJobNotFoundError):
            await service.consume_artifact("nope", "token", USER_ID)

    @pytest.mark.asyncio
    async def test_consume_delegates_to_registry(self, tmp_path: object) -> None:
        # Seed the registry directly (the runner would do this on completion).
        from pathlib import Path

        from narrare.export.contracts import Artifact

        job = registry.create(NOVEL_ID, USER_ID, ExportFormat.MARKDOWN)
        artifact = Artifact(
            format=ExportFormat.MARKDOWN,
            path=Path("/tmp/something.md"),
            media_type="text/markdown",
            suggested_filename="novel.md",
        )
        registry.mark_completed(job.job_id, artifact)
        from urllib.parse import parse_qs, urlparse

        token = str(
            parse_qs(urlparse(registry.get(job.job_id, USER_ID).artifact_url).query)["token"][0]  # type: ignore[arg-type]
        )

        service = _service()
        consumed = await service.consume_artifact(job.job_id, token, USER_ID)
        assert consumed.path == artifact.path

        # Single-use honoured through the service layer.
        with pytest.raises(ExportArtifactExpiredError):
            await service.consume_artifact(job.job_id, token, USER_ID)
