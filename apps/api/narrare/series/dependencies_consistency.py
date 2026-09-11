"""DI factory for the Series Consistency sub-module (Spec 4 Task 2).

Split out of ``dependencies.py`` (RULE-04: modularize, don't compress). The
consistency check is logically separable from the series CRUD / join / voice
factories and lives behind its own router (``router_consistency.py``), so it
gets its own dependency module — one responsibility per file (RULE-06).

``get_series_consistency_service`` wires the SAME infrastructure the analysis
siblings use (ModelRegistry + PromptComposer + InvocationPipeline) so the
existing ``SeriesConsistencyAgent`` (Task 1) runs unchanged. Model acquisition
follows the per-user model-routing cascade: the factory resolves
``LLMIntent.ANALYSE`` (the intent ``series_consistency_prompt`` composes with,
``context_mode="series_consistency"``) for the authenticated user and passes
the resolved config + credentials into the service. Canon fetch goes through
:class:`KBRepository` (which inherits ``find_canon_for_series`` from
:class:`KBScopeRepository`, Spec 1). Ownership is verified inside the service
(mirrors ``SeriesVoiceService``).

See:
    ADR-075 — Series Foundation (Canon KB scope).
    CONSTRAINTS.md RULE-04/06/07/11
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import Depends

from narrare._app.dependencies import (
    SessionDep,
    get_current_user_id,
)
from narrare._app.dependencies_services import get_model_routing_resolver
from narrare.chapters.repository import ChapterRepository
from narrare.kb.repository import KBRepository
from narrare.novels.repository import NovelRepository
from narrare.series.repository import SeriesRepository
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.series.series_consistency_service import SeriesConsistencyService


async def get_series_consistency_service(
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> SeriesConsistencyService:
    """Request-scoped SeriesConsistencyService (canon-contradiction check).

    Wires the series-consistency service with the SAME infrastructure the
    analysis siblings use so the existing ``SeriesConsistencyAgent`` (Task 1)
    runs unchanged. Canon fetch goes through :class:`KBRepository` (which
    inherits ``find_canon_for_series`` from :class:`KBScopeRepository`,
    Spec 1). Ownership + novel-membership are verified inside the service
    (mirrors ``SeriesVoiceService``).

    The model is resolved through the per-user cascade (user intent → user
    category → user default) with ``project_id=None``: the novel id — the
    cascade's project-tier key — arrives only in the request BODY of the
    check endpoint, so it is never available at dependency-wiring time (the
    SERIES id is NOT a project id — passing it would query the project-routing
    table with a foreign UUID). Same documented caveat as
    ``dependencies_context_preview.py`` (SERIES-002). ``ConfigurationError``
    propagates when the user has no provider configured (series routers are
    auth-mandatory).
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.series.series_consistency_service import SeriesConsistencyService

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(LLMIntent.ANALYSE, UUID(user_id), None)

    return SeriesConsistencyService(
        series_repo=SeriesRepository(session),
        novel_repo=NovelRepository(session),
        chapter_repo=ChapterRepository(session),
        kb_repo=KBRepository(session),
        registry=get_model_registry(),
        config=resolved.config,
        composer=get_composer(),
        invocation_pipeline=get_invocation_pipeline(),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )
