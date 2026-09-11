"""DI factory for the Series Voice Drift sub-module (Spec 4 Task 3).

Split out of ``dependencies.py`` (RULE-04: modularize, don't compress). The
series-voice-drift check is logically separable from the other series factories
and lives behind its own router (``router_voice_drift.py``), so it gets its own
dependency module — one responsibility per file (RULE-06).

``get_series_voice_drift_service`` wires the SAME infrastructure the novel-level
:class:`AuthorVoiceDriftService` uses (ModelRegistry + PromptComposer +
InvocationPipeline) so the existing ``AuthorVoiceDriftAgent`` pipeline runs
unchanged. Model acquisition follows the per-user model-routing cascade: the
factory resolves ``LLMIntent.VOICE`` (the intent ``author_voice_drift_prompt``
composes with, ``context_mode="author_voice_drift"``) for the authenticated
user and passes the resolved config + credentials into the service. The series
voice profile is read through :class:`SeriesRepository`
(``SeriesSettings.author_voice``), NOT :class:`AuthorVoiceRepository` (which
reads the novel-level column). Ownership is verified inside the service
(mirrors ``SeriesVoiceService``).

See:
    ADR-078 — Series Voice Hierarchy (Delta model).
    ADR-074 — Author Voice Storage Contract (the pipeline reused).
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
from narrare.novels.repository import NovelRepository
from narrare.series.repository import SeriesRepository
from narrare_core.llm.intents import LLMIntent

if TYPE_CHECKING:
    from narrare.series.series_voice_drift_service import SeriesVoiceDriftService


async def get_series_voice_drift_service(
    session: SessionDep,
    user_id: str = Depends(get_current_user_id),
) -> SeriesVoiceDriftService:
    """Request-scoped SeriesVoiceDriftService (cross-novel voice drift).

    Wires the series-voice-drift service with the SAME infrastructure the
    novel-level :class:`AuthorVoiceDriftService` uses so the existing
    ``AuthorVoiceDriftAgent`` pipeline runs unchanged. The series voice profile
    is read through :class:`SeriesRepository` (``SeriesSettings.author_voice``),
    NOT :class:`AuthorVoiceRepository` (the novel-level column). Ownership +
    novel-membership are verified inside the service (mirrors
    ``SeriesVoiceService``).

    The model is resolved through the per-user cascade (user intent → user
    category → user default) with ``project_id=None``: the novel id — the
    cascade's project-tier key — arrives only in the request BODY of the check
    endpoint, so it is never available at dependency-wiring time (the SERIES id
    is NOT a project id — passing it would query the project-routing table
    with a foreign UUID). Same documented caveat as
    ``dependencies_context_preview.py`` (SERIES-002). ``ConfigurationError``
    propagates when the user has no provider configured (series routers are
    auth-mandatory).
    """
    from narrare._app.dependencies import (
        get_composer,
        get_invocation_pipeline,
        get_model_registry,
    )
    from narrare.series.series_voice_drift_service import SeriesVoiceDriftService

    resolver = get_model_routing_resolver(session)
    resolved = await resolver.resolve(LLMIntent.VOICE, UUID(user_id), None)

    return SeriesVoiceDriftService(
        series_repo=SeriesRepository(session),
        novel_repo=NovelRepository(session),
        chapter_repo=ChapterRepository(session),
        model_registry=get_model_registry(),
        model_config=resolved.config,
        composer=get_composer(),
        invocation_pipeline=get_invocation_pipeline(),
        api_key=resolved.api_key,
        base_url=resolved.base_url,
    )
