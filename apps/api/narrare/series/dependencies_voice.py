"""DI factories for the Series Voice sub-module (Spec 3).

Split out of ``dependencies.py`` (RULE-04: modularize, don't compress). Voice
wiring is logically separable from the series CRUD / join / band-summary
factories and lives behind its own router (``router_voice.py``), so it gets
its own dependency module — one responsibility per file (RULE-06).

``get_series_voice_service`` wires the SAME infrastructure the novel-level
:class:`AuthorVoiceService` uses (ModelRegistry + ANALYSIS system default
config + PromptComposer + InvocationPipeline) so the existing
``AuthorVoiceAgent`` pipeline runs unchanged. Storage goes through
:class:`SeriesRepository` (``SeriesSettings.author_voice``), NOT
:class:`AuthorVoiceRepository` (which writes the novel-level column).
Ownership is verified inside the service (mirrors ``SeriesService``).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare._app.dependencies import (
    SessionDep,
    get_composer,
    get_invocation_pipeline,
    get_model_registry,
)
from narrare.chapters.repository import ChapterRepository
from narrare.novels.repository import NovelRepository
from narrare.series.repository import SeriesRepository

if TYPE_CHECKING:
    from narrare.series.series_voice_service import SeriesVoiceService


def get_series_voice_service(session: SessionDep) -> SeriesVoiceService:
    """Request-scoped SeriesVoiceService (profile / get / override).

    Wires the series-voice service with the SAME infrastructure the novel-level
    :class:`AuthorVoiceService` uses (ModelRegistry + ANALYSIS system default
    config + PromptComposer + InvocationPipeline) so the existing
    ``AuthorVoiceAgent`` pipeline runs unchanged. Storage goes through
    :class:`SeriesRepository` (``SeriesSettings.author_voice``), NOT
    :class:`AuthorVoiceRepository` (which writes the novel-level column).
    Ownership is verified inside the service (mirrors ``SeriesService``).
    """
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare.series.series_voice_service import SeriesVoiceService

    return SeriesVoiceService(
        series_repo=SeriesRepository(session),
        novel_repo=NovelRepository(session),
        chapter_repo=ChapterRepository(session),
        model_registry=get_model_registry(),
        model_config=build_system_default_config(SystemModelCategory.ANALYSIS),
        composer=get_composer(),
        invocation_pipeline=get_invocation_pipeline(),
    )
