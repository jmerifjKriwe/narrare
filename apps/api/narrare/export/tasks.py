"""Export in-process dispatch + the export runner (ADR-080 pattern, IO-001).

Mirrors :mod:`narrare.series.tasks` faithfully:

- ``_INFLIGHT_TASKS`` — the GC-guard set of strong references to in-flight
  export coroutines (prevents ``asyncio.create_task`` from being garbage-
  collected mid-flight). Registered in ``_DRAIN_SOURCES`` so graceful shutdown
  cancels + awaits every export task **before** the DB engine is disposed.
- ``enqueue_export(...)`` — the production enqueuer the service DI-injects
  (tests substitute a recording fake — RULE-07). Launches the runner
  fire-and-forget via ``asyncio.create_task``.
- ``run_export_inprocess(...)`` — the runner. Builds its **own** DB session via
  ``get_session_factory()`` (never the request session), loads the manuscript,
  normalizes (Core), renders (adapter), and registers the artifact.
- ``_on_done`` — done-callback. If the task was cancelled (drain on shutdown),
  flips the job to ``FAILED "cancelled (server shutdown)"`` (RULE-11 queryable
  lost-job — a polled job returns a typed failure instead of hanging).

Manuscript-HTML assembly decision (documented per the IO-001 plan)
------------------------------------------------------------------
``NarrareNormalizer.normalize`` takes a *single* ``raw_tiptap_html`` blob, but a
manuscript is many chapters (each ``Chapter.content`` is its own TipTap HTML).
The runner assembles the blob in :func:`assemble_raw_html`:

- Chapters are concatenated in **position order** (the repository's
  ``order_by(Chapter.position)``; the Core normalizer also defensively stable-
  sorts via ``order_chapters``).
- Each chapter is preceded by its title as an ``<h2>`` heading
  (``<h2>{html-escaped title}</h2>``); a chapter with an empty title contributes
  no heading. Chapters are joined by a newline.

Why ``<h2>`` (not ``<h1>``) and no body-level ``<h1`` book title:

1. The book title is **metadata**, not a body heading — it is carried in
   ``ManuscriptMetadata.title`` and consumed by the renderers via
   ``NarrareRomanConfig`` (Typst) / pandoc metadata, NOT as an ``<h1>`` in the
   body. Keeping it out of the body avoids an H1 collision and keeps the body a
   pure sequence of chapter sections.
2. Chapter titles as ``<h2>`` lets the Markdown renderer apply
   ``--shift-heading-level-by=-1`` (seam fix F-1) to promote them to ``H1`` —
   matching ``MarkdownOptions.chapter_heading_level = 1``. The Typst narrare-
   roman wrapper maps headings to chapter/page breaks. So a single source
   heading level (``<h2>``) serves both renderers with format-specific shifts.

This is the pandoc-friendly form: explicit, heading-based chapter boundaries
that downstream renderers can paginate on, with the title handled out-of-band.

Non-LLM (no ``narrare_core.agents`` / ``narrare_core.prompts`` imports) — export
is a deterministic render pipeline.
"""

from __future__ import annotations

import asyncio
import html
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

import structlog

from narrare.export import registry
from narrare.export.contracts import (
    ExportFormat,
    ExportOptions,
    ManuscriptRenderer,
)
from narrare.export.repository import ChapterRow, ExportRepository, ManuscriptSource
from narrare_core.export.contracts import (
    ChapterMeta,
    Language,
    ManuscriptMetadata,
    ManuscriptNormalizer,
    NormalizedManuscript,
)

if TYPE_CHECKING:
    from uuid import UUID

logger = structlog.get_logger(__name__)

#: Export-job enqueuer signature — the DI-injected callable the service calls
#: to dispatch a job. The production impl (:func:`enqueue_export`) launches the
#: runner in-process; tests substitute a recording fake (RULE-07).
ExportEnqueuer = Callable[[str, "UUID", ExportOptions], Awaitable[None]]

#: Strong references to in-flight export coroutines (ADR-080 GC guard).
#: Drained on graceful shutdown via ``_DRAIN_SOURCES`` (see
#: :mod:`narrare._app.inflight`). Entries auto-remove via ``_on_done``.
_INFLIGHT_TASKS: set[asyncio.Task[None]] = set()

# Module-level runner dependencies, resolved lazily on first use (mirrors the
# series runner's self-resolving ``build_band_summary_service`` call). Tests
# override these directly to inject fakes (same monkeypatch style as
# ``tests/unit/api/series/test_tasks.py``).
_normalizer: ManuscriptNormalizer | None = None
_renderers: dict[ExportFormat, ManuscriptRenderer] | None = None


def _resolve_runner_deps() -> tuple[ManuscriptNormalizer, dict[ExportFormat, ManuscriptRenderer]]:
    """Lazily build the normalizer + the three renderer adapters.

    Renderers are stateless (each only caches a ``shutil.which`` probe), so
    module-level singletons are safe. Tests inject fakes by assigning
    ``tasks._normalizer`` / ``tasks._renderers`` directly.
    """
    global _normalizer, _renderers
    if _normalizer is None:
        from narrare_core.export.normalizer import NarrareNormalizer

        _normalizer = NarrareNormalizer()
    if _renderers is None:
        from narrare.export.renderers.pandoc_epub import PandocEpubRenderer
        from narrare.export.renderers.pandoc_md import PandocMarkdownRenderer
        from narrare.export.renderers.typst import TypstPdfRenderer

        _renderers = {
            ExportFormat.PDF: TypstPdfRenderer(),
            ExportFormat.MARKDOWN: PandocMarkdownRenderer(),
            ExportFormat.EPUB: PandocEpubRenderer(),
        }
    return _normalizer, _renderers


# ── Manuscript assembly (pure — tested directly, no DB) ────────────────────


def build_metadata(source: ManuscriptSource, options: ExportOptions) -> ManuscriptMetadata:
    """Build the Core :class:`ManuscriptMetadata` from a read-only DB snapshot
    plus the per-request option block.

    Coerces ``source.language`` to :class:`Language`; an unknown value raises
    ``ValueError`` (caught by the runner → job FAILED). This is NOT a silent
    fallback — the no-silent-fallback principle (ADR-081) forbids guessing a
    language: a manuscript whose declared language the toolchain can't
    hyphenate surfaces as a typed job failure.

    ISBN/description (IO-001 follow-up): the request is their only v1 source
    (no DB storage), so ``options.epub_options`` — when present — populates
    the Core metadata (request wins over the DB-absent ``None`` defaults).
    Only the EPUB renderer consumes them; PDF/MD ignore them (D7 precedent).
    """
    chapters = [
        ChapterMeta(
            chapter_id=c.chapter_id,
            title=c.title,
            position=c.position,
            volume_id=c.volume_id,
        )
        for c in source.chapters
    ]
    epub = options.epub_options
    return ManuscriptMetadata(
        title=source.title,
        author=source.author,
        language=Language(source.language),
        chapters=chapters,
        isbn=epub.isbn if epub is not None else None,
        description=epub.description if epub is not None else None,
    )


def assemble_raw_html(source: ManuscriptSource) -> str:
    """Assemble one HTML blob from the chapter list (see module docstring).

    Each chapter → ``<h2>{escaped title}</h2>`` + its TipTap content, in
    position order, joined by newlines. Empty-titled chapters contribute no
    heading (their content still flows in order).
    """
    parts: list[str] = []
    for chapter in source.chapters:
        chunk = _chapter_chunk(chapter)
        if chunk:
            parts.append(chunk)
    return "\n".join(parts)


def _chapter_chunk(chapter: ChapterRow) -> str:
    heading = f"<h2>{html.escape(chapter.title)}</h2>" if chapter.title else ""
    body = chapter.content
    return f"{heading}\n{body}" if heading else body


# ── Dispatch (mirrors narrare.series.tasks) ────────────────────────────────


def _on_done(task: asyncio.Task[None]) -> None:
    """Done-callback: GC-guard discard + cancellation → FAILED (RULE-11).

    On cancellation (graceful-shutdown drain) the job is flipped to FAILED with
    ``"cancelled (server shutdown)"`` so a client polling ``get_job`` sees a
    typed failure instead of a job hung in RUNNING. The runner's own
    ``except Exception`` does NOT swallow ``CancelledError`` (a ``BaseException``
    in 3.8+), so cancellation always reaches this callback as
    ``task.cancelled()``.
    """
    _INFLIGHT_TASKS.discard(task)
    if task.cancelled():
        registry.mark_failed(task.get_name(), "cancelled (server shutdown)")
        return
    exc = task.exception()
    if exc is not None:
        # Defensive: the runner swallows its own exceptions, so a surfaced
        # exception here is from outside its try (e.g. mark_running on a
        # half-built task). Log it so it is never silent (RULE-11).
        logger.error(
            "export_background_task_failed",
            job_id=task.get_name(),
            error=str(exc),
            exc_info=exc,
        )


async def enqueue_export(job_id: str, novel_id: UUID, options: ExportOptions) -> None:
    """Production enqueuer: launch the export runner in-process (ADR-080).

    DI-injected into ``ExportServiceImpl`` via the factory
    (:func:`narrare.export.dependencies.get_export_service`). Unit tests
    substitute a recording fake so they can assert dispatch without real
    asyncio scheduling. Fire-and-forget: the caller does not await the result.
    """
    task = asyncio.create_task(
        run_export_inprocess(job_id, novel_id, options),
        name=job_id,
    )
    _INFLIGHT_TASKS.add(task)
    task.add_done_callback(_on_done)
    logger.info(
        "export_dispatched",
        job_id=job_id,
        novel_id=str(novel_id),
        format=options.format.value,
    )


async def run_export_inprocess(job_id: str, novel_id: UUID, options: ExportOptions) -> None:
    """In-process runner: load → normalize → render → register artifact.

    Builds its **own** DB session via ``get_session_factory()`` (never the
    request session) and closes it as soon as the manuscript is loaded — the
    slow render does NOT hold a DB connection (RULE-22 read-only; pool-friendly).
    Every failure path converts to a typed registry state change (RULE-11):
    missing novel, unknown language, missing renderer, or renderer failure all
    become ``FAILED`` with a reason.

    ``CancelledError`` (graceful-shutdown drain) intentionally propagates past
    the ``except Exception`` so ``_on_done`` records it as the canonical
    "cancelled (server shutdown)" failure.
    """
    from narrare._app.database import get_session_factory

    try:
        registry.mark_running(job_id)

        session_factory = get_session_factory()
        async with session_factory() as session:
            source = await ExportRepository(session).get_manuscript_source(
                novel_id, options.volume_id
            )

        if source is None:
            registry.mark_failed(job_id, f"novel {novel_id} not found")
            return

        metadata = build_metadata(source, options)
        raw_html = assemble_raw_html(source)

        normalizer, renderers = _resolve_runner_deps()
        normalized: NormalizedManuscript = await normalizer.normalize(raw_html, metadata)

        renderer = renderers.get(options.format)
        if renderer is None:
            registry.mark_failed(
                job_id, f"no renderer registered for format {options.format.value}"
            )
            return

        artifact = await renderer.render(normalized, options)
        registry.mark_completed(job_id, artifact)
    except Exception as exc:
        # CancelledError is a BaseException (3.8+) → NOT caught here → reaches
        # _on_done, which records the canonical cancellation failure.
        logger.error("export_run_failed", job_id=job_id, error=str(exc), exc_info=exc)
        registry.mark_failed(job_id, f"{type(exc).__name__}: {exc}")
