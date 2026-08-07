"""DI factory for the Series Voice Drift sub-module (Spec 4 Task 3).

Split out of ``dependencies.py`` (RULE-04: modularize, don't compress). The
series-voice-drift check is logically separable from the other series factories
and lives behind its own router (``router_voice_drift.py``), so it gets its own
dependency module — one responsibility per file (RULE-06).

``get_series_voice_drift_service`` wires the SAME infrastructure the novel-level
:class:`AuthorVoiceDriftService` uses (ModelRegistry + ANALYSIS system default
config + PromptComposer + InvocationPipeline) so the existing
``AuthorVoiceDriftAgent`` pipeline runs unchanged. The series voice profile is
read through :class:`SeriesRepository` (``SeriesSettings.author_voice``), NOT
:class:`AuthorVoiceRepository` (which reads the novel-level column). Ownership
is verified inside the service (mirrors ``SeriesVoiceService``).
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
    from narrare.series.series_voice_drift_service import SeriesVoiceDriftService


def get_series_voice_drift_service(session: SessionDep) -> SeriesVoiceDriftService:
    """Request-scoped SeriesVoiceDriftService (cross-novel voice drift).

    Wires the series-voice-drift service with the SAME infrastructure the
    novel-level :class:`AuthorVoiceDriftService` uses (ModelRegistry + ANALYSIS
    system default config + PromptComposer + InvocationPipeline) so the existing
    ``AuthorVoiceDriftAgent`` pipeline runs unchanged. The series voice profile
    is read through :class:`SeriesRepository` (``SeriesSettings.author_voice``),
    NOT :class:`AuthorVoiceRepository` (the novel-level column). Ownership +
    novel-membership are verified inside the service (mirrors
    ``SeriesVoiceService``).
    """
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare.series.series_voice_drift_service import SeriesVoiceDriftService

    return SeriesVoiceDriftService(
        series_repo=SeriesRepository(session),
        novel_repo=NovelRepository(session),
        chapter_repo=ChapterRepository(session),
        model_registry=get_model_registry(),
        model_config=build_system_default_config(SystemModelCategory.ANALYSIS),
        composer=get_composer(),
        invocation_pipeline=get_invocation_pipeline(),
    )
