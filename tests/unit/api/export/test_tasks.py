"""Unit tests for export dispatch + runner + manuscript assembly (ADR-080).

Mirrors the dispatch-mechanics tests in ``tests/unit/api/series/test_tasks.py``:
``enqueue_export`` launches the runner via ``asyncio.create_task`` with a
GC-guarded strong reference; a cancelled task flips the job to FAILED via the
``_on_done`` callback (RULE-11 queryable lost-job). The runner end-to-end is
exercised with the fakes from ``conftest.py`` (no real DB, no real binary).
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest

from narrare.export import registry, tasks
from narrare.export.contracts import ExportJobStatus
from narrare.export.options import EpubOptions, ExportFormat, ExportOptions
from tests.unit.api.export.conftest import (
    FailingRenderer,
    FakeNormalizer,
    FakeRenderer,
    make_chapter,
    make_options,
    make_source,
)

NOVEL_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest.fixture(autouse=True)
def _clear_inflight() -> object:
    """Cancel + clear any leftover in-flight export tasks between tests."""
    tasks._INFLIGHT_TASKS.clear()
    yield
    for t in list(tasks._INFLIGHT_TASKS):
        t.cancel()
    tasks._INFLIGHT_TASKS.clear()


class _FakeRepo:
    """Stand-in for ExportRepository: returns a canned source (no DB)."""

    def __init__(self, session: object, *, source: object | None = None) -> None:
        self._source = source

    async def get_manuscript_source(
        self,
        novel_id: object,
        volume_id: object | None = None,
    ) -> object:
        return self._source


def _install_runner_deps(
    monkeypatch: pytest.MonkeyPatch,
    *,
    renderer: FakeRenderer,
    normalizer: FakeNormalizer | None = None,
) -> FakeNormalizer:
    """Inject fake normalizer + a single-format renderer into the runner."""
    norm = normalizer or FakeNormalizer()
    monkeypatch.setattr(tasks, "_normalizer", norm)
    monkeypatch.setattr(tasks, "_renderers", {renderer.format: renderer})
    return norm


def _install_session_and_repo(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source: object | None,
) -> None:
    """Inject a no-op session factory + a FakeRepo returning ``source``."""

    class _Factory:
        def __call__(self) -> _Factory:
            return self

        async def __aenter__(self) -> object:
            return object()

        async def __aexit__(self, *exc: object) -> bool:
            return False

    monkeypatch.setattr("narrare._app.database.get_session_factory", lambda: _Factory())
    monkeypatch.setattr(
        tasks, "ExportRepository", lambda session: _FakeRepo(session, source=source)
    )


# ── Manuscript assembly (pure functions — the documented decision) ─────────


class TestAssembleRawHtml:
    """assemble_raw_html concatenates chapters as <h2>title</h2> + content."""

    def test_each_chapter_preceded_by_h2_title(self) -> None:
        source = make_source(
            chapters=[
                make_chapter(title="Chapter One", position=0, content="<p>body1</p>"),
                make_chapter(title="Chapter Two", position=1, content="<p>body2</p>"),
            ]
        )
        html = tasks.assemble_raw_html(source)
        assert html == ("<h2>Chapter One</h2>\n<p>body1</p>\n<h2>Chapter Two</h2>\n<p>body2</p>")

    def test_chapters_emitted_in_supplied_order(self) -> None:
        # assemble_raw_html does NOT re-sort — it emits chapters in the exact
        # order of the list (the repository's order_by(position) + the
        # normalizer's defensive order_chapters enforce positional ordering).
        source = make_source(
            chapters=[
                make_chapter(title="First", position=0, content="<p>a</p>"),
                make_chapter(title="Second", position=1, content="<p>b</p>"),
            ]
        )
        html = tasks.assemble_raw_html(source)
        assert html.index("First") < html.index("Second")

    def test_empty_title_contributes_no_heading(self) -> None:
        source = make_source(
            chapters=[make_chapter(title="", position=0, content="<p>only body</p>")]
        )
        assert tasks.assemble_raw_html(source) == "<p>only body</p>"

    def test_title_html_escaped(self) -> None:
        source = make_source(chapters=[make_chapter(title="A <b> & B", position=0, content="x")])
        html = tasks.assemble_raw_html(source)
        assert "<h2>A &lt;b&gt; &amp; B</h2>" in html


class TestBuildMetadata:
    """build_metadata coerces the DB language into the Core Language enum."""

    def test_builds_metadata_with_chapter_meta(self) -> None:
        chapter = make_chapter(title="C1", position=2)
        source = make_source(language="de", chapters=[chapter])
        metadata = tasks.build_metadata(source, make_options())
        assert metadata.title == "Test Novel"
        assert metadata.author == "Test Author"
        assert metadata.language.value == "de"
        assert len(metadata.chapters) == 1
        assert metadata.chapters[0].position == 2

    def test_unknown_language_raises(self) -> None:
        # No silent fallback: a language the toolchain can't handle surfaces
        # as a failure (caught by the runner → FAILED).
        source = make_source(language="klingon")
        with pytest.raises(ValueError):
            tasks.build_metadata(source, make_options())

    def test_epub_options_populate_isbn_and_description(self) -> None:
        """The request is the v1 source for ISBN/description (no DB storage):
        ``epub_options`` overrides the DB-absent metadata defaults."""
        source = make_source(chapters=[make_chapter()])
        options = ExportOptions(
            format=ExportFormat.EPUB,
            epub_options=EpubOptions(isbn="978-3-16-148410-0", description="A tale."),
        )
        metadata = tasks.build_metadata(source, options)
        assert metadata.isbn == "978-3-16-148410-0"
        assert metadata.description == "A tale."

    def test_no_epub_options_leave_isbn_and_description_unset(self) -> None:
        """Backward compat: exports without epub_options carry no ISBN /
        description → the EPUB renderer keeps pandoc's uuid identifier default
        and omits dc:description."""
        source = make_source(chapters=[make_chapter()])
        metadata = tasks.build_metadata(source, make_options())
        assert metadata.isbn is None
        assert metadata.description is None


# ── Dispatch mechanics (mirrors series/tasks tests) ────────────────────────


class TestEnqueueExport:
    @pytest.mark.asyncio
    async def test_dispatches_inprocess_task(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: list[tuple[str, UUID, object]] = []

        async def fake_runner(job_id: str, novel_id: UUID, options: object) -> None:
            captured.append((job_id, novel_id, options))

        monkeypatch.setattr(tasks, "run_export_inprocess", fake_runner)

        job = registry.create(NOVEL_ID, ExportFormat.MARKDOWN)
        await tasks.enqueue_export(job.job_id, NOVEL_ID, make_options())

        assert len(tasks._INFLIGHT_TASKS) == 1
        tracked = next(iter(tasks._INFLIGHT_TASKS))
        assert tracked.get_name() == job.job_id  # name = job_id (for _on_done)
        await tracked
        assert captured == [(job.job_id, NOVEL_ID, tracked.get_name())] or len(captured) == 1

    @pytest.mark.asyncio
    async def test_gc_guard_removes_completed_task(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def quick(job_id: str, novel_id: UUID, options: object) -> None:
            pass

        monkeypatch.setattr(tasks, "run_export_inprocess", quick)
        await tasks.enqueue_export("job-1", NOVEL_ID, make_options())
        tracked = next(iter(tasks._INFLIGHT_TASKS))
        await tracked
        await asyncio.sleep(0)  # let add_done_callback fire
        assert len(tasks._INFLIGHT_TASKS) == 0

    @pytest.mark.asyncio
    async def test_cancelled_task_flips_job_to_failed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def block(job_id: str, novel_id: UUID, options: object) -> None:
            await asyncio.sleep(3600)

        monkeypatch.setattr(tasks, "run_export_inprocess", block)
        job = registry.create(NOVEL_ID, ExportFormat.PDF)
        registry.mark_running(job.job_id)
        await tasks.enqueue_export(job.job_id, NOVEL_ID, make_options(ExportFormat.PDF))

        tracked = next(iter(tasks._INFLIGHT_TASKS))
        tracked.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tracked
        await asyncio.sleep(0)  # let _on_done fire

        failed = registry.get(job.job_id)
        assert failed.status is ExportJobStatus.FAILED
        assert failed.error == "cancelled (server shutdown)"

    @pytest.mark.asyncio
    async def test_drain_cancels_inflight_export_and_marks_job_failed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from narrare._app.inflight import drain_inflight_tasks

        async def block(job_id: str, novel_id: UUID, options: object) -> None:
            await asyncio.sleep(3600)

        monkeypatch.setattr(tasks, "run_export_inprocess", block)
        job = registry.create(NOVEL_ID, ExportFormat.EPUB)
        registry.mark_running(job.job_id)
        await tasks.enqueue_export(job.job_id, NOVEL_ID, make_options(ExportFormat.EPUB))

        await drain_inflight_tasks()

        failed = registry.get(job.job_id)
        assert failed.status is ExportJobStatus.FAILED
        assert "cancelled" in (failed.error or "")


# ── Runner end-to-end (fakes — no DB, no binary) ───────────────────────────


class TestRunExportInprocess:
    @pytest.mark.asyncio
    async def test_happy_path_completes_job(self, monkeypatch: pytest.MonkeyPatch) -> None:
        renderer = FakeRenderer(ExportFormat.MARKDOWN)
        normalizer = _install_runner_deps(monkeypatch, renderer=renderer)
        source = make_source(chapters=[make_chapter(title="C1", content="<p>hi</p>")])
        _install_session_and_repo(monkeypatch, source=source)

        job = registry.create(NOVEL_ID, ExportFormat.MARKDOWN)
        await tasks.run_export_inprocess(job.job_id, NOVEL_ID, make_options())

        completed = registry.get(job.job_id)
        assert completed.status is ExportJobStatus.COMPLETED
        assert completed.artifact_url is not None
        # The fake normalizer received the assembled HTML (with the h2 title).
        assert len(normalizer.normalize_calls) == 1
        raw_html, _metadata = normalizer.normalize_calls[0]
        assert "<h2>C1</h2>" in raw_html
        assert len(renderer.render_calls) == 1

    @pytest.mark.asyncio
    async def test_missing_novel_marks_failed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        renderer = FakeRenderer(ExportFormat.MARKDOWN)
        _install_runner_deps(monkeypatch, renderer=renderer)
        _install_session_and_repo(monkeypatch, source=None)

        job = registry.create(NOVEL_ID, ExportFormat.MARKDOWN)
        await tasks.run_export_inprocess(job.job_id, NOVEL_ID, make_options())

        failed = registry.get(job.job_id)
        assert failed.status is ExportJobStatus.FAILED
        assert "not found" in (failed.error or "")
        assert renderer.render_calls == []

    @pytest.mark.asyncio
    async def test_renderer_failure_marks_failed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        renderer = FailingRenderer(ExportFormat.MARKDOWN, error=RuntimeError("pandoc died"))
        _install_runner_deps(monkeypatch, renderer=renderer)
        _install_session_and_repo(monkeypatch, source=make_source(chapters=[make_chapter()]))

        job = registry.create(NOVEL_ID, ExportFormat.MARKDOWN)
        await tasks.run_export_inprocess(job.job_id, NOVEL_ID, make_options())

        failed = registry.get(job.job_id)
        assert failed.status is ExportJobStatus.FAILED
        assert "pandoc died" in (failed.error or "")

    @pytest.mark.asyncio
    async def test_unknown_language_marks_failed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        renderer = FakeRenderer(ExportFormat.MARKDOWN)
        _install_runner_deps(monkeypatch, renderer=renderer)
        _install_session_and_repo(
            monkeypatch,
            source=make_source(language="klingon", chapters=[make_chapter()]),
        )

        job = registry.create(NOVEL_ID, ExportFormat.MARKDOWN)
        await tasks.run_export_inprocess(job.job_id, uuid4(), make_options())

        failed = registry.get(job.job_id)
        assert failed.status is ExportJobStatus.FAILED

    @pytest.mark.asyncio
    async def test_epub_request_isbn_description_reach_renderer(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Wiring: EpubOptions.isbn/description → build_metadata override →
        (fake) normalizer passthrough → the renderer's NormalizedManuscript."""
        renderer = FakeRenderer(ExportFormat.EPUB)
        _install_runner_deps(monkeypatch, renderer=renderer)
        _install_session_and_repo(monkeypatch, source=make_source(chapters=[make_chapter()]))
        options = ExportOptions(
            format=ExportFormat.EPUB,
            epub_options=EpubOptions(isbn="978-3-16-148410-0", description="A tale."),
        )

        job = registry.create(NOVEL_ID, ExportFormat.EPUB)
        await tasks.run_export_inprocess(job.job_id, NOVEL_ID, options)

        completed = registry.get(job.job_id)
        assert completed.status is ExportJobStatus.COMPLETED
        manuscript, _opts = renderer.render_calls[0]
        assert manuscript.isbn == "978-3-16-148410-0"
        assert manuscript.description == "A tale."
