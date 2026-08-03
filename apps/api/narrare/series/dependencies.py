"""DI factories for the Series module (RULE-06: router → service → repository).

Three factories wire the request-scoped async session into the Series
repositories and services. The join-service factory builds every repository
it needs (series/novel/kb) from the same session so the whole join
transaction commits/rolls back together.

``get_band_summary_service`` (Spec 2 Task 3) is async because it resolves the
model routing config per user/novel (mirroring ``writing/get_summary_service``);
all repositories share ``session`` so generation + upsert commit together.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.series.band_summary_service import BandSummaryService


def get_series_repository(session: SessionDep) -> SeriesRepository:
    """Request-scoped SeriesRepository."""
    return SeriesRepository(session)


def get_series_service(session: SessionDep) -> SeriesService:
    """Request-scoped SeriesService (CRUD + settings + novels-in-series)."""
    return SeriesService(SeriesRepository(session))


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


async def get_band_summary_service(
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
    novel_id: UUID | None = None,
) -> BandSummaryService:
    """Request-scoped BandSummaryService (generate / lazy / override).

    Mirrors ``writing/get_summary_service``: resolves the SUMMARIZE model
    config per user/novel, then wires the three repositories (band-summary,
    novel, chapter) from the same session so generation + upsert commit
    together. The router (Task 4) supplies ``novel_id`` from the path.
    """
    from dataclasses import replace
    from uuid import UUID as _UUID

    from narrare._app.config import get_settings
    from narrare.series.band_summary_service import BandSummaryService
    from narrare.settings.token_limits.repository import (
        ProjectTokenLimitsRepository,
        UserTokenLimitsRepository,
    )
    from narrare.settings.token_limits.service import TokenLimitsService

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(
        LLMIntent.SUMMARIZE,
        _UUID(user_id),
        novel_id,
    )

    token_limits_service = TokenLimitsService(
        user_repo=UserTokenLimitsRepository(session),
        project_repo=ProjectTokenLimitsRepository(session),
        config=get_settings(),
    )
    limits = await token_limits_service.get_resolved_limits(
        user_id=user_id,
        project_id=str(novel_id) if novel_id else None,
    )
    config = replace(
        resolved.config,
        temperature=0.3,
        max_tokens=limits.output_limit,
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
    )
