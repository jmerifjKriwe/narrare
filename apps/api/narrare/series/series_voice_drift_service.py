"""SeriesVoiceDriftService — cross-novel voice drift (Spec 4 Task 3).

Business logic only (RULE-06): no SQL, no HTTP. The series-scope analogue of
:class:`~narrare.analysis.author_voice_drift_service.AuthorVoiceDriftService`
(ANAL-009 Phase 2B). Where the novel-level service compares a band's per-chapter
narrator metrics against the **novel's** stored profile, this service compares
them against the **series voice** (``SeriesSettings.author_voice``, Spec 3 /
ADR-078) — the cross-novel drift signal.

The service REUSES the existing analysis pipeline helpers via the invocation
assembly in :mod:`narrare.series._series_voice_drift_invocation`
(compute → prompt → agent → aggregate; RULE-04/RULE-06; extracted for the size
limit the ADR-086 ``ensure_resolved`` addition crossed) and loads chapters via
the established :func:`load_selected_chapters` helper (chapter_ids validation).

The ONLY difference from the novel-level service is the SOURCE of the reference
profile + metric group: ``SeriesRepository.get_settings`` →
``SeriesSettings.author_voice`` instead of
``AuthorVoiceRepository.load(novel_id)``. No new agent is created (RULE-01b).

**Regression safety (CRITICAL):** the novel-level
:class:`AuthorVoiceDriftService` is 100% unchanged — this is a separate
series-scoped service behind its own endpoint.

Model acquisition (ADR-086 L29): the per-user routing cascade is injected
as a ``ModelResolution`` and resolved on first use inside :meth:`check` —
after the ownership gates, before the graceful early exits — never at
construction (422-before-400 ordering for invalid request bodies).

RULE-11 graceful degradation: no stored series voice, a profile missing the
metric blocks, or no chapter with prose yields a graceful ``no_profile``
response (never a crash) — mirroring the novel-level service.

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b)
         → SeriesRepository (RULE-07, no raw column access).

See:
    :mod:`narrare.series.series_voice_drift_contracts` — the Protocol.
    :mod:`narrare.series._series_voice_drift_invocation` — invocation assembly.
    :mod:`narrare.analysis.author_voice_drift_service` — the novel-level parallel.
    ADR-078 — Series Voice Hierarchy (Delta model).
    ADR-074 — Author Voice Storage Contract (the pipeline reused).
    ADR-086 — lazy model resolution (this slice: L29).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.analysis.schemas_author_voice_drift import (
    AuthorVoiceDriftNoProfile,
    AuthorVoiceDriftResponse,
)
from narrare.series._series_voice_drift_invocation import run_series_voice_drift_invocation
from narrare.series.series_voice_profile_reader import read_series_voice_profile
from narrare_core.shared.errors import (
    ConfigurationError,
    ForbiddenError,
)

if TYPE_CHECKING:
    from narrare._app.dependencies_services import ModelResolution
    from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftRequest
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.model_routing import ResolvedModel
    from narrare_core.prompts.composer import PromptComposer
    from narrare_core.series.schemas import Series

logger = structlog.get_logger(__name__)


class SeriesVoiceDriftService:
    """Cross-novel author-voice drift against the series voice baseline.

    Takes a series + a member novel (the band), loads the series voice profile
    from ``SeriesSettings.author_voice``, computes the per-chapter narrator
    trend + jumps against the SERIES metric group, runs the governed
    ``author_voice_drift`` agent (1 LLM call), and returns the aggregate
    response. Read-only — nothing is persisted.

    Constructor args are documented on :meth:`__init__`; the full method
    contract lives on
    :class:`narrare.series.series_voice_drift_contracts.SeriesVoiceDriftServiceProtocol`
    (RULE-03 SSOT).
    """

    def __init__(
        self,
        series_repo: SeriesRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        chapter_repo: ChapterRepository,
        model_registry: ModelRegistry,
        model_resolution: ModelResolution,
        composer: PromptComposer | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        """Initialise the service with all dependencies injected (RULE-07).

        Args:
            series_repo: Series + SeriesSettings persistence (ownership +
                ``author_voice`` read).
            novel_repo: Novel lookup (verify membership + resolve metadata).
            chapter_repo: Chapter prose fetch (``list_by_novel``).
            model_registry: Model registry for the AuthorVoiceDriftAgent.
            model_resolution: Lazy per-user model resolution (ADR-086) —
                the routing cascade (VOICE, ``project_id=None``) resolves
                on first use, never at construction.
            composer: PromptComposer for the governed author_voice_drift prompt
                (None → ConfigurationError at check time).
            invocation_pipeline: Optional InvocationPipeline for evidence.
        """
        self._series_repo = series_repo
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = model_registry
        self._model_resolution = model_resolution
        self._resolved: ResolvedModel | None = None
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline

    async def ensure_resolved(self) -> ResolvedModel:
        """Resolve the per-user model routing once; idempotent (ADR-086).

        First call resolves via the injected ``ModelResolution`` and
        caches the triple; repeat calls return the cached value without
        re-running the cascade. Errors propagate loudly and are never
        cached (RULE-11): ``ConfigurationError`` (``NO_AI_PROVIDER``)
        surfaces as a 400 on this AI-mandatory endpoint.
        """
        if self._resolved is None:
            self._resolved = await self._model_resolution.resolve()
        return self._resolved

    async def check(
        self,
        series_id: UUID,
        novel_id: UUID,
        user_id: UUID,
        request: AuthorVoiceDriftRequest,
    ) -> AuthorVoiceDriftResponse:
        """Analyse a band's narrator drift against the series voice baseline.

        Full contract on :meth:`SeriesVoiceDriftServiceProtocol.check`.
        """
        # 1-2. Verify series ownership + novel membership (anti-enumeration).
        series = await self._verify_series_ownership(series_id, user_id)
        novel = await self._novel_repo.get(novel_id)
        if novel is None or novel.series_id != series_id:
            raise ForbiddenError("You do not have access to this series")

        # ADR-086 L29: first-use lazy resolve — the ownership gates above
        # stay ahead of resolution (eager-world precedence), and resolution
        # precedes the profile read / graceful no_profile early exits, so an
        # unconfigured provider stays a loud 400 even on the degradation
        # path. The resolved triple flows into the invocation assembly
        # exactly as the eager factory passed it (timing-only migration:
        # WHAT unchanged — the eager resolve applied no sampling overrides —
        # only WHEN). The eager world's dead ``config=None → NotFoundError``
        # branch is gone with the ctor swap: the required ``ModelResolution``
        # makes an unresolvable cascade a loud ``ConfigurationError`` at
        # this line instead.
        resolved_model = await self.ensure_resolved()

        composer = self._composer
        if composer is None:
            raise ConfigurationError(
                "PromptComposer is not configured for series-voice-drift analysis.",
                code="NO_COMPOSER",
            )

        language = novel.writing_language or series.writing_language or "en"

        # 3. Load the SERIES voice profile (Spec 3 storage target). None →
        #    graceful no_profile, no LLM call. Reading goes through the
        #    extracted reader (RULE-04: series_voice_profile_reader.py).
        profile = await read_series_voice_profile(self._series_repo, series_id)
        if profile is None:
            logger.info(
                "series_voice_drift_no_profile",
                feature_id="series_voice_drift",
                series_id=str(series_id),
                novel_id=str(novel_id),
                reason="no_stored_series_voice",
            )
            return _no_profile_response(novel_id, "no_stored_series_voice")

        # 4. Extract the metric blocks the trend comparison needs. A profile
        #    missing voice_metrics or author_metrics cannot be trend-compared
        #    → graceful no_profile (mirrors the novel-level service).
        voice_analysis = profile.voice_analysis
        series_voice_metrics = voice_analysis.voice_metrics if voice_analysis is not None else None
        series_author_metrics = profile.author_metrics
        if series_voice_metrics is None or series_author_metrics is None:
            logger.info(
                "series_voice_drift_no_profile",
                feature_id="series_voice_drift",
                series_id=str(series_id),
                novel_id=str(novel_id),
                reason="no_series_voice_metrics",
            )
            return _no_profile_response(novel_id, "no_series_voice_metrics")

        # 5. Load chapters (specific ids or all chapters in the novel). Reuses
        #    the established chapter-loading helper (validates chapter_ids
        #    belong to the novel — not series-voice-drift-specific).
        from narrare.analysis.character_voice_kb_writer import load_selected_chapters

        chapter_ids = [UUID(cid) for cid in request.chapter_ids] if request.chapter_ids else None
        chapters = await load_selected_chapters(self._chapter_repo, novel_id, chapter_ids)

        if not chapters:
            logger.info(
                "series_voice_drift_no_chapters",
                feature_id="series_voice_drift",
                novel_id=str(novel_id),
            )
            return AuthorVoiceDriftResponse(novel_id=str(novel_id))

        # 6-8. Per-chapter metrics → prose guard → governed prompt → agent
        #    (1 LLM call) → aggregate assembly against the SERIES baseline —
        #    the invocation assembly lives in the dedicated module (RULE-04/
        #    RULE-06; moved for the size limit the ADR-086 ensure_resolved
        #    addition crossed).
        return await run_series_voice_drift_invocation(
            registry=self._registry,
            composer=composer,
            invocation_pipeline=self._invocation_pipeline,
            resolved_model=resolved_model,
            chapters=chapters,
            profile=profile,
            profile_voice_metrics=series_voice_metrics,
            profile_author_metrics=series_author_metrics,
            novel=novel,
            language=language,
            novel_id=novel_id,
            user_id=user_id,
        )

    # ------------------------------------------------------------------
    # Ownership + series-voice helpers
    # ------------------------------------------------------------------

    async def _verify_series_ownership(self, series_id: UUID, user_id: UUID) -> Series:
        """Load a series and verify the caller owns it (anti-enumeration).

        A *missing* series and a *not-owned* series both surface as
        ``ForbiddenError`` (HTTP 403) — never ``NotFoundError`` (404) — so
        series ids are not enumerable (C1 / IDOR fix). Mirrors
        :meth:`SeriesVoiceService._verify_series_ownership`.
        """
        series = await self._series_repo.get(series_id)
        if series is None or series.user_id != user_id:
            raise ForbiddenError("You do not have access to this series")
        return series


def _no_profile_response(novel_id: UUID, reason: str) -> AuthorVoiceDriftResponse:
    """Build a graceful ``no_profile`` aggregate response (RULE-11)."""
    return AuthorVoiceDriftResponse(
        novel_id=str(novel_id),
        no_profile=AuthorVoiceDriftNoProfile(reason=reason),
    )
