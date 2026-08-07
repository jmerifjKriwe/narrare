"""DI factory for the Series Consistency sub-module (Spec 4 Task 2).

Split out of ``dependencies.py`` (RULE-04: modularize, don't compress). The
consistency check is logically separable from the series CRUD / join / voice
factories and lives behind its own router (``router_consistency.py``), so it
gets its own dependency module — one responsibility per file (RULE-06).

``get_series_consistency_service`` wires the SAME infrastructure the analysis
siblings use (ModelRegistry + ANALYSIS system default config + PromptComposer +
InvocationPipeline) so the existing ``SeriesConsistencyAgent`` (Task 1) runs
unchanged. Canon fetch goes through :class:`KBRepository` (which inherits
``find_canon_for_series`` from :class:`KBScopeRepository`, Spec 1). Ownership is
verified inside the service (mirrors ``SeriesVoiceService``).
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
from narrare.kb.repository import KBRepository
from narrare.novels.repository import NovelRepository
from narrare.series.repository import SeriesRepository

if TYPE_CHECKING:
    from narrare.series.series_consistency_service import SeriesConsistencyService


def get_series_consistency_service(session: SessionDep) -> SeriesConsistencyService:
    """Request-scoped SeriesConsistencyService (canon-contradiction check).

    Wires the series-consistency service with the SAME infrastructure the
    analysis siblings use (ModelRegistry + ANALYSIS system default config +
    PromptComposer + InvocationPipeline) so the existing
    ``SeriesConsistencyAgent`` (Task 1) runs unchanged. Canon fetch goes
    through :class:`KBRepository` (which inherits ``find_canon_for_series``
    from :class:`KBScopeRepository`, Spec 1). Ownership + novel-membership are
    verified inside the service (mirrors ``SeriesVoiceService``).
    """
    from narrare._app.dependencies_services import (
        SystemModelCategory,
        build_system_default_config,
    )
    from narrare.series.series_consistency_service import SeriesConsistencyService

    return SeriesConsistencyService(
        series_repo=SeriesRepository(session),
        novel_repo=NovelRepository(session),
        chapter_repo=ChapterRepository(session),
        kb_repo=KBRepository(session),
        registry=get_model_registry(),
        config=build_system_default_config(SystemModelCategory.ANALYSIS),
        composer=get_composer(),
        invocation_pipeline=get_invocation_pipeline(),
    )
