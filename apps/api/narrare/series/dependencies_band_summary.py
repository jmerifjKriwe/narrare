"""Band-summary DI factories for the Series module (RULE-04 split).

Extracted from ``dependencies.py`` for the 200-line dependency-module limit
the ADR-086 lazy seam crossed (``dependencies_context_preview.py`` /
``dependencies_voice_drift.py`` precedent). Contains ALL band-summary wiring:
the anti-enumeration guard, the shared service builder, and the request
factory.

``verify_novel_in_owned_series`` enforces anti-enumeration at the router
boundary: the caller must own the series AND the novel must be in it.

``build_band_summary_service`` is the shared builder used by both the FastAPI
factory and the in-process background task (no request context in the task).
Model acquisition follows the per-user model-routing cascade with LAZY
first-use resolution (ADR-086 L25, M-budget / S4b shape): the builder wires a
``LazyModelResolution`` around the SUMMARIZE routing cascade and a deferred
runtime composition awaiting BOTH cascades (routing + token limits,
RULE-18/18b — sources unchanged, only timing moves). No resolution happens
at construction: for requests, construction happens pre-body-validation and
an eager cascade would preempt legitimate 422s with 400/404/500s; the
composition runs once at the service's first use
(``BandSummaryService.ensure_resolved``, the top of ``generate``). For the
background task, the closure captures THIS call's session-bound resolver and
token-limits service, so first use happens at task runtime while the task's
session is still open (pinned by
``tests/unit/api/series/test_band_summary_lazy_resolution.py``).

See:
    ADR-082 — token budgets (``get_resolved_limits`` cascade source)
    ADR-086 — lazy model resolution (timing-only deferral)
    CONSTRAINTS.md RULE-04/06/07/11/18/18b
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends

from narrare._app.dependencies import (
    SessionDep,
    get_composer,
    get_current_user_id,
    get_invocation_pipeline,
    get_model_registry,
)
from narrare._app.dependencies_services import (
    LazyModelResolution,
    get_model_routing_resolver,
)
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.series.band_summary_repository import BandSummaryRepository
from narrare.series.repository import SeriesRepository
from narrare_core.llm.intents import LLMIntent
from narrare_core.shared.errors import ForbiddenError

if TYPE_CHECKING:
    from narrare.series._band_summary_support import BandSummaryModelRuntime
    from narrare.series.band_summary_service import BandSummaryService


async def verify_novel_in_owned_series(
    series_id: UUID,
    novel_id: UUID,
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> None:
    """Anti-enumeration guard: caller owns the series AND novel is in it.

    Loads the series (403 if missing or not owned — never 404, so series ids
    are not enumerable, mirroring ``SeriesService._verify_series_ownership``)
    and the novel (403 if missing or ``novel.series_id != series_id``).

    Used as a FastAPI dependency by every band-summary route so the
    ``BandSummaryService`` (keyed by ``novel_id`` only, usable from non-request
    contexts like the in-process auto-trigger) never needs to repeat the check.
    """
    series = await SeriesRepository(session).get(series_id)
    if series is None or series.user_id != UUID(user_id):
        raise ForbiddenError("You do not have access to this series")

    novel = await NovelRepository(session).get(novel_id)
    # Anti-enumeration: a missing novel and a mismatched novel both surface as
    # 403 (never reveal whether the novel exists).
    if novel is None or novel.series_id != series_id:
        raise ForbiddenError("You do not have access to this series")


async def build_band_summary_service(
    session: SessionDep, user_id: UUID, novel_id: UUID
) -> BandSummaryService:
    """Build a ``BandSummaryService`` with lazily-wired model routing.

    Shared by the FastAPI factory (``get_band_summary_service``) and the
    in-process background task (``generate_band_summary_inprocess``). Wires
    the three repositories (band-summary, novel, chapter) from the same
    session so generation + upsert commit together, plus the deferred
    composition below — resolving nothing here (ADR-086).

    The deferred composition reproduces the eager factory's verbatim cascade
    order and sampling overlay (``temperature=0.3``,
    ``max_tokens=limits.output_limit``) exactly once at the service's first
    use.
    """
    from dataclasses import replace

    from narrare._app.config import get_settings
    from narrare.series._band_summary_support import BandSummaryModelRuntime
    from narrare.series.band_summary_service import BandSummaryService
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService

    resolver = get_model_routing_resolver(session)
    model_resolution = LazyModelResolution(
        lambda: resolver.resolve(LLMIntent.SUMMARIZE, user_id, novel_id)
    )

    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )

    async def compose_model_runtime() -> BandSummaryModelRuntime:
        """Resolve both cascades and freeze the runtime at first use.

        Awaits the (cached) SUMMARIZE routing resolution and the
        token-limits cascade, then applies the eager factory's verbatim
        sampling overlay. The closure captures this build call's
        session-bound resolver + token-limits service (background-task
        invariant: first use at task runtime, session still open).
        """
        resolved = await model_resolution.resolve()
        limits = await token_limits_service.get_resolved_limits(
            user_id=str(user_id),
            project_id=str(novel_id),
        )
        return BandSummaryModelRuntime(
            config=replace(
                resolved.config,
                temperature=0.3,
                max_tokens=limits.output_limit,
            ),
            api_key=resolved.api_key,
            base_url=resolved.base_url,
        )

    # Canonical KB-context provider (ADR-067): single fetch+render source for
    # the kb_characters / kb_locations / kb_factions / kb_relationships
    # prompt variables. Degrades gracefully (RULE-11). Active since the
    # band_summary template's header-demotion activation slice: the
    # Knowledge-Base region renders (no longer below the parse cutoff);
    # degradation → empty bundle (RULE-11). No cascade dependency — wired
    # eagerly.
    from narrare.kb._context_provider import KBContextProvider
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository

    kb_context_provider = KBContextProvider(
        kb_repo=KBRepository(session),
        relationship_repo=RelationshipRepository(session),
    )

    return BandSummaryService(
        repo=BandSummaryRepository(session),
        novel_repo=NovelRepository(session),
        chapter_repo=ChapterRepository(session),
        registry=get_model_registry(),
        model_runtime_factory=compose_model_runtime,
        composer=get_composer(),
        invocation_pipeline=get_invocation_pipeline(),
        kb_context_provider=kb_context_provider,
    )


async def get_band_summary_service(
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
    novel_id: UUID | None = None,
) -> BandSummaryService:
    """Request-scoped BandSummaryService (generate / get / override).

    Delegates to ``build_band_summary_service`` (shared with the in-process
    background task). The router supplies ``novel_id`` from the path; FastAPI
    resolves path params into sub-dependency parameters by name.
    """
    if novel_id is None:
        # Every band-summary route declares {novel_id} in the path, so FastAPI
        # always resolves it. This guard is defence-in-depth for direct calls.
        raise ForbiddenError("novel_id path parameter is required")

    return await build_band_summary_service(session, UUID(user_id), novel_id)
