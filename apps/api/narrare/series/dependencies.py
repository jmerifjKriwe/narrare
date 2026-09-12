"""DI factories for the Series module (RULE-06: router → service → repository).

Three factories wire the request-scoped async session into the Series
repositories and services. The join-service factory builds every repository
it needs (series/novel/kb) from the same session so the whole join
transaction commits/rolls back together.

``get_band_summary_service`` (Spec 2 Task 3+4) is async because it resolves the
model routing config per user/novel (mirroring ``writing/get_summary_service``);
all repositories share ``session`` so generation + upsert commit together.
``verify_novel_in_owned_series`` (Task 4) enforces anti-enumeration at the
router boundary: the caller must own the series AND the novel must be in it.
``build_band_summary_service`` (Task 5) is the shared builder used by both the
FastAPI factory and the in-process background task (no request context in the task).
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
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.series.band_summary_repository import BandSummaryRepository
from narrare.series.join_service import SeriesJoinService
from narrare.series.repository import SeriesRepository
from narrare.series.service import SeriesService
from narrare_core.llm.intents import LLMIntent
from narrare_core.shared.errors import ForbiddenError

if TYPE_CHECKING:
    from narrare.series.band_summary_service import BandSummaryService


def get_series_repository(session: SessionDep) -> SeriesRepository:
    """Request-scoped SeriesRepository."""
    return SeriesRepository(session)


def get_series_service(session: SessionDep) -> SeriesService:
    """Request-scoped SeriesService (CRUD + settings + novels-in-series).

    Wires the band-summary auto-trigger enqueuer (Spec 2 Task 5) so that
    ``update_series`` can launch background generation in-process when a
    series transitions to ``completed``. The enqueuer is resolved lazily
    inside the function body to avoid a module-level circular import
    (``series.service`` ← ``series.tasks`` ← ``series.dependencies``).
    """
    from narrare.series.tasks import enqueue_band_summary_generation

    return SeriesService(
        SeriesRepository(session),
        enqueue_band_summary=enqueue_band_summary_generation,
    )


def get_series_join_service(session: SessionDep) -> SeriesJoinService:
    """Request-scoped SeriesJoinService (Policy alpha preview/apply/remove).

    All repositories share ``session`` so membership mutations and KB scope
    promotions commit as one transaction.
    """
    # Local imports keep the module import-light at app startup.
    from narrare.kb.repository import KBRepository

    return SeriesJoinService(
        session=session,
        series_repo=SeriesRepository(session),
        novel_repo=NovelRepository(session),
        kb_repo=KBRepository(session),
    )


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
    """Build a ``BandSummaryService`` with resolved model routing.

    Shared by the FastAPI factory (``get_band_summary_service``) and the
    in-process background task (``generate_band_summary_inprocess``). Resolves
    the SUMMARIZE model config per user/novel, then wires the three
    repositories (band-summary, novel, chapter) from the same session so
    generation + upsert commit together.
    """
    from dataclasses import replace

    from narrare._app.config import get_settings
    from narrare.series.band_summary_service import BandSummaryService
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(LLMIntent.SUMMARIZE, user_id, novel_id)

    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    limits = await token_limits_service.get_resolved_limits(
        user_id=str(user_id),
        project_id=str(novel_id),
    )
    config = replace(
        resolved.config,
        temperature=0.3,
        max_tokens=limits.output_limit,
    )

    # Canonical KB-context provider (ADR-067): single fetch+render source for
    # the kb_characters / kb_locations / kb_factions / kb_relationships
    # prompt variables. Degrades gracefully (RULE-11). Active since the
    # band_summary template's header-demotion activation slice: the
    # Knowledge-Base region renders (no longer below the parse cutoff);
    # degradation → empty bundle (RULE-11).
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
        config=config,
        composer=get_composer(),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
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
