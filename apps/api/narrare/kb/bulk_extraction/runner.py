"""Bulk extraction runner — in-process dispatch + the per-chapter loop (ADR-092 §5).

Mirrors :mod:`narrare.export.tasks` (ADR-080 in-process pattern):

- ``_INFLIGHT_TASKS`` — the GC-guard set of strong references to in-flight
  bulk coroutines (``asyncio.create_task`` results would otherwise be
  garbage-collected mid-flight). Entries auto-remove via ``_on_done``.
  Registered in ``narrare._app.inflight._DRAIN_SOURCES``, so graceful
  shutdown cancels bulk tasks before the engine is disposed.
- ``dispatch(job_id, novel_id, owner_id)`` — the production enqueuer the
  service DI-injects; launches the runner fire-and-forget, task named
  ``job_id``.
- ``run_bulk_extraction(...)`` — the §5 loop: ``mark_job_running``, then
  per pending chapter (position-order snapshot): cooperative cancel check
  BETWEEN chapters → one pacer acquire → ``mark_chapter_running`` → OWN
  DB session (``get_session_factory()``, never a request session) → the
  REAL ``ExtractionService`` → record done/failed. Ends
  ``mark_job_completed``.
- ``_on_done`` — done-callback: GC discard; a cancelled task (shutdown
  drain) flips the job to ``cancelled ("cancelled (server shutdown)")``
  so a poller sees a terminal state, never a hang (RULE-11).

Failure semantics: ``ConfigurationError`` fast-fails the whole job (no
point burning N-1 more calls on an unconfigured provider) — the in-flight
chapter is recorded FAILED first, so a terminal job never strands a
RUNNING row; any other chapter failure is isolated (chapter → failed, job
continues); an infrastructure failure outside the per-chapter handling
fails the job instead of leaving it RUNNING. ``CancelledError`` is a
``BaseException`` and propagates past every ``except Exception``.

Test seams (module attributes, monkeypatch style of ``export/tasks.py``):
``_service_factory`` (defaults to the real wiring below) and
``_pacer_acquire`` (lazily binds the shared-budget pacer from
``pacer.py`` — kept lazy so tests can inject the seam directly).

F3 post-pass (spec §6.2, D15a): after ``mark_job_completed``, a ``corpus``
job fires ONE deterministic ADR-085 duplicate analysis —
``_maybe_run_post_pass_dedup`` (kind gate + RULE-11 failure handling) →
``_run_post_pass_analysis`` (own session via ``get_session_factory``,
module attribute so tests fake it) → ``_analyzer_factory`` (lazily binds
``_build_post_pass_analyzer``, which calls ``get_resolution_analyzer``
ITSELF over the canonical kb factories — the exact request-path wiring,
zero drift by construction; NO adjudicator, zero LLM calls). Explicit
jobs never trigger; a drain cancellation skips it; a failure is visible
(``corpus_post_pass_dedup_failed`` warning) and never fails the job.
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, cast

import structlog

from narrare.kb.bulk_extraction import registry
from narrare_core.shared.errors import ConfigurationError

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from narrare.kb.entity_resolution.analysis_service import ResolutionAnalysisService
    from narrare.kb.extraction_service import ExtractionService

logger = structlog.get_logger(__name__)

#: Signature of the per-chapter service factory seam: (own session,
#: novel owner, novel) → the real ExtractionService (no request context
#: exists; the owner is passed IN — the service gated it before dispatch).
_ServiceFactory = Callable[["AsyncSession", "UUID", "UUID"], "ExtractionService"]

#: Signature of the post-pass analyzer factory seam: (own session) → the
#: DETERMINISTIC ``ResolutionAnalysisService`` (ADR-085 non-adjudicated
#: wiring — the auto-trigger never spends LLM tokens, spec §6.2).
_AnalyzerFactory = Callable[["AsyncSession"], "ResolutionAnalysisService"]

#: Strong references to in-flight bulk coroutines (ADR-080 GC guard).
_INFLIGHT_TASKS: set[asyncio.Task[None]] = set()

_service_factory: _ServiceFactory | None = None
_pacer_acquire: Callable[[], Awaitable[None]] | None = None
_analyzer_factory: _AnalyzerFactory | None = None


def _resolve_service_factory() -> _ServiceFactory:
    """Bind the default (real) service factory on first use."""
    global _service_factory
    if _service_factory is None:
        _service_factory = _build_extraction_service
    return _service_factory


def _resolve_pacer_acquire() -> Callable[[], Awaitable[None]]:
    """Bind the shared-budget pacer on first use (``pacer.py``, ADR-092 D7a).

    Resolved via ``importlib`` + ``getattr`` — the same dynamic-module
    pattern as ``narrare._app.inflight._snapshot_tasks`` — binding
    :func:`narrare.kb.bulk_extraction.pacer.acquire_analysis_pacer_slot`
    (one shared analysis-budget slot per chapter, spec §7). The indirection
    keeps the runner importable without the pacer's import-time settings/
    limiter wiring and lets tests inject the ``_pacer_acquire`` seam
    directly instead of going through the resolver.
    """
    global _pacer_acquire
    if _pacer_acquire is None:
        module = importlib.import_module("narrare.kb.bulk_extraction.pacer")
        _pacer_acquire = cast(
            "Callable[[], Awaitable[None]]",
            module.acquire_analysis_pacer_slot,
        )
    return _pacer_acquire


def _resolve_analyzer_factory() -> _AnalyzerFactory:
    """Bind the default (real) post-pass analyzer factory on first use."""
    global _analyzer_factory
    if _analyzer_factory is None:
        _analyzer_factory = _build_post_pass_analyzer
    return _analyzer_factory


def _build_post_pass_analyzer(session: AsyncSession) -> ResolutionAnalysisService:
    """The REAL deterministic ADR-085 analyzer over a runner-owned session.

    Calls ``get_resolution_analyzer`` ITSELF over the canonical kb factories
    — the exact wiring the request-path DI performs, so the post-pass cannot
    drift from it (plan T3 pins this as an interface dependency): KBRepository
    + RelationshipRepository + the dismissal ledger, assembled inside that
    factory by the shared builder (snapshot builder + pure engine + the
    shared analysis-cache singleton). NO adjudicator → zero LLM calls
    (spec §6.2: the auto-trigger never spends tokens silently).
    """
    from narrare.kb.dependencies_core import get_kb_repository, get_rel_repository
    from narrare.kb.entity_resolution.dependencies import (
        get_resolution_analyzer,
        get_resolution_dismissal_store,
    )

    kb_repo = get_kb_repository(session)
    rel_repo = get_rel_repository(session)
    dismissed = get_resolution_dismissal_store(session)
    return get_resolution_analyzer(kb_repo, rel_repo, dismissed)


def _build_extraction_service(
    session: AsyncSession, owner_id: UUID, novel_id: UUID
) -> ExtractionService:
    """The REAL ExtractionService wiring for a runner-owned session.

    Mirrors ``kb/dependencies_extraction.py`` exactly minus the apply-only
    deps (KBService/RelationshipRepository/request session — apply stays a
    request-path concern, spec §5). Model routing stays lazy (ADR-086):
    the ``LLMIntent.KB_EXTRACT`` cascade resolves on the service's first
    use per chapter; ``ConfigurationError`` then fast-fails the job.
    No ``pydantic_ai`` / LLM-gateway imports here (RULE-01b) — the
    service owns the agent boundary.
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare._app.dependencies_services import (
        LazyModelResolution,
        get_model_routing_resolver,
    )
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.extraction_service import ExtractionService
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.llm.intents import LLMIntent
    from narrare_core.llm.run_limits import DefaultRunLimitResolver

    resolver = get_model_routing_resolver(session)
    return ExtractionService(
        registry=get_model_registry(),
        model_resolution=LazyModelResolution(
            lambda: resolver.resolve(LLMIntent.KB_EXTRACT, owner_id, novel_id)
        ),
        chapter_repo=ChapterRepository(session),
        kb_repo=KBRepository(session),
        composer=get_composer(),
        novel_repo=NovelRepository(session),
        invocation_pipeline=get_invocation_pipeline(),
        run_limit_resolver=DefaultRunLimitResolver(),
    )


async def _run_post_pass_analysis(novel_id: UUID, owner_id: UUID) -> tuple[bool, int | None]:
    """ONE deterministic ADR-085 analysis over the novel's KB roster (F3 §6.2).

    Own session via the session factory (a request session does not exist in
    background context); ``refresh=True`` forces a recompute so the analysis
    reflects the pass's just-recorded KB state instead of a stale cache read.
    Returns ``(analyzed, suggestion_count)`` — module attribute so tests
    monkeypatch it (``test_post_pass_dedup.py``).
    """
    from narrare._app.database import get_session_factory

    session_factory = get_session_factory()
    async with session_factory() as session:
        analyzer = _resolve_analyzer_factory()(session)
        response = await analyzer.analyze(novel_id, owner_id, refresh=True)
        return (True, len(response.suggestions))


async def _maybe_run_post_pass_dedup(job_id: str, novel_id: UUID, owner_id: UUID) -> None:
    """Kind-gated post-completion dedup trigger (F3 §6.2, D15a).

    ``corpus`` jobs only — explicit jobs never trigger. Failure is VISIBLE
    and NON-FATAL (RULE-11): the warning is logged, the job's dedup block
    degrades to ``analyzed: false``, and the job itself stays completed —
    the pass succeeded, only the duplicate check is out. A 0-word chapter
    that failed deterministically ("chapter is empty") needs no special
    casing here: it is an isolated failed row; the job still completes and
    the analysis runs over whatever roster state exists.
    """
    if registry.kind_of(job_id) != "corpus":
        return
    try:
        analyzed, suggestion_count = await _run_post_pass_analysis(novel_id, owner_id)
    except Exception as exc:
        logger.warning(
            "corpus_post_pass_dedup_failed",
            job_id=job_id,
            error=str(exc),
            exc_info=exc,
        )
        registry.mark_dedup_unavailable(job_id)
        return
    if analyzed and suggestion_count is not None:
        registry.mark_dedup(job_id, suggestion_count)
    else:
        # Degraded outcome without an exception — still unavailable, and
        # mark_dedup_unavailable logs its own warning (never silent).
        registry.mark_dedup_unavailable(job_id)


def _on_done(task: asyncio.Task[None]) -> None:
    """Done-callback: GC-guard discard + cancellation → CANCELLED (RULE-11).

    On cancellation (graceful-shutdown drain) the job is flipped to
    CANCELLED with the canonical reason so a client polling status sees a
    terminal state instead of a job hung in RUNNING. The runner's own
    ``except Exception`` blocks do NOT swallow ``CancelledError``, so a
    drain cancellation always reaches this callback as ``task.cancelled()``.
    """
    _INFLIGHT_TASKS.discard(task)
    if task.cancelled():
        registry.mark_cancelled(task.get_name(), "cancelled (server shutdown)")
        return
    exc = task.exception()
    if exc is not None:
        # Defensive: the runner converts its own failures to registry state,
        # so a surfaced exception comes from outside its guards (e.g. the
        # dispatch bookkeeping). Logged so it is never silent (RULE-11).
        logger.error(
            "bulk_background_task_failed",
            job_id=task.get_name(),
            error=str(exc),
            exc_info=exc,
        )


async def dispatch(job_id: str, novel_id: UUID, owner_id: UUID) -> None:
    """Production enqueuer: launch the bulk runner in-process (ADR-080).

    Fire-and-forget — the caller does not await the runner's outcome; the
    done-callback keeps the GC guard and the drain story intact.
    """
    task = asyncio.create_task(run_bulk_extraction(job_id, novel_id, owner_id), name=job_id)
    _INFLIGHT_TASKS.add(task)
    task.add_done_callback(_on_done)
    logger.info("bulk_extraction_dispatched", job_id=job_id, novel_id=str(novel_id))


async def run_bulk_extraction(job_id: str, novel_id: UUID, owner_id: UUID) -> None:
    """The §5 loop over the job's pending chapters, in position order.

    Session hygiene: the session FACTORY is resolved once per job, but one
    OWN session is opened and closed PER CHAPTER (a chapter's agent call
    must not hold the previous chapter's connection). Cancel is honored
    only BETWEEN chapters — the in-flight agent call always finishes and
    its output is recorded (spec §4.4/§5).
    """
    from narrare._app.database import get_session_factory

    try:
        registry.mark_job_running(job_id)
        session_factory = get_session_factory()
        pacer_acquire = _resolve_pacer_acquire()
        service_factory = _resolve_service_factory()

        for chapter_id in registry.pending_chapter_ids(job_id):
            if registry.cancel_requested(job_id):
                registry.mark_cancelled(job_id, "cancelled by user")
                return
            await pacer_acquire()  # shared analysis budget, one slot per agent call
            registry.mark_chapter_running(job_id, chapter_id)
            async with session_factory() as session:
                service = service_factory(session, owner_id, novel_id)
                try:
                    output = await service.extract_from_chapter(novel_id, chapter_id, owner_id)
                except ConfigurationError as exc:
                    logger.error(
                        "bulk_configuration_fast_fail",
                        job_id=job_id,
                        chapter_id=str(chapter_id),
                        error=str(exc),
                        exc_info=exc,
                    )
                    # Heal the in-flight row BEFORE failing the job: it was
                    # marked RUNNING above, and a job-level FAILURE alone
                    # would strand a RUNNING chapter inside a terminal job
                    # forever (T3-review rider — reset_for_resume re-pends
                    # it, but a terminal job must not carry RUNNING rows).
                    registry.mark_chapter_failed(job_id, chapter_id, str(exc))
                    registry.mark_job_failed(job_id, str(exc))
                    return
                except Exception as exc:
                    # Per-chapter isolation (spec §5): record + continue.
                    logger.warning(
                        "bulk_chapter_extraction_failed",
                        job_id=job_id,
                        chapter_id=str(chapter_id),
                        error=str(exc),
                        exc_info=exc,
                    )
                    registry.mark_chapter_failed(job_id, chapter_id, str(exc))
                    continue
            registry.mark_chapter_done(job_id, chapter_id, output)

        registry.mark_job_completed(job_id)
    except Exception as exc:
        # CancelledError is a BaseException (3.8+) → NOT caught here → it
        # reaches _on_done, which records the canonical shutdown cancellation.
        # Any other infrastructure failure (pacer, session factory, registry)
        # fails the JOB — a hung RUNNING job is never acceptable (RULE-11).
        logger.error("bulk_run_failed", job_id=job_id, error=str(exc), exc_info=exc)
        registry.mark_job_failed(job_id, f"{type(exc).__name__}: {exc}")
        return
    # F3 §6.2 — the corpus post-pass dedup trigger. Deliberately AFTER the
    # infrastructure guard: a dedup failure must never clobber a COMPLETED
    # job. The cooperative-cancel and fast-fail returns above skip it, and a
    # drain cancellation propagates before this line — only a job that truly
    # reached completed arms the trigger (dedup stays {analyzed: false} else).
    await _maybe_run_post_pass_dedup(job_id, novel_id, owner_id)
