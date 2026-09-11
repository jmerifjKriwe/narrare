"""SeriesVoiceDriftService — cross-novel voice drift (Spec 4 Task 3).

Business logic only (RULE-06): no SQL, no HTTP. The series-scope analogue of
:class:`~narrare.analysis.author_voice_drift_service.AuthorVoiceDriftService`
(ANAL-009 Phase 2B). Where the novel-level service compares a band's per-chapter
narrator metrics against the **novel's** stored profile, this service compares
them against the **series voice** (``SeriesSettings.author_voice``, Spec 3 /
ADR-078) — the cross-novel drift signal.

The service REUSES the existing analysis pipeline helpers verbatim:
    :func:`compute_author_voice_per_chapter` — deterministic per-chapter
        narrator metrics (voice + author, ADR-021).
    :func:`analyse_author_voice_drift` — trend + jumps + agent (1 LLM call) +
        result assembly.
    :func:`resolve_author_voice_drift_prompt` — Mode-1 governed
        ``author_voice_drift`` system prompt.
    :func:`load_selected_chapters` — chapter loading + chapter_ids validation.

The ONLY difference from the novel-level service is the SOURCE of the reference
profile + metric group: ``SeriesRepository.get_settings`` →
``SeriesSettings.author_voice`` instead of
``AuthorVoiceRepository.load(novel_id)``. No new agent is created (RULE-01b).

**Regression safety (CRITICAL):** the novel-level
:class:`AuthorVoiceDriftService` is 100% unchanged — this is a separate
series-scoped service behind its own endpoint.

RULE-11 graceful degradation: no stored series voice, a profile missing the
metric blocks, or no chapter with prose yields a graceful ``no_profile``
response (never a crash) — mirroring the novel-level service.

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b)
         → SeriesRepository (RULE-07, no raw column access).

See:
    :mod:`narrare.series.series_voice_drift_contracts` — the Protocol.
    :mod:`narrare.analysis.author_voice_drift_service` — the novel-level parallel.
    ADR-078 — Series Voice Hierarchy (Delta model).
    ADR-074 — Author Voice Storage Contract (the pipeline reused).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.analysis.author_voice_drift_pipeline import (
    analyse_author_voice_drift,
    compute_author_voice_per_chapter,
)
from narrare.analysis.author_voice_drift_prompt import (
    resolve_author_voice_drift_prompt,
)
from narrare.analysis.schemas_author_voice_drift import (
    AuthorVoiceDriftNoProfile,
    AuthorVoiceDriftResponse,
)
from narrare.series.series_voice_profile_reader import read_series_voice_profile
from narrare_core.shared.errors import (
    ConfigurationError,
    ForbiddenError,
    NotFoundError,
)

if TYPE_CHECKING:
    from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftRequest
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series.contracts import SeriesRepositoryProtocol
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
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
        model_config: ResolvedModelConfig | None = None,
        composer: PromptComposer | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialise the service with all dependencies injected (RULE-07).

        Args:
            series_repo: Series + SeriesSettings persistence (ownership +
                ``author_voice`` read).
            novel_repo: Novel lookup (verify membership + resolve metadata).
            chapter_repo: Chapter prose fetch (``list_by_novel``).
            model_registry: Model registry for the AuthorVoiceDriftAgent.
            model_config: Resolved analysis model config (None → NotFoundError
                at check time, mirroring AuthorVoiceDriftService).
            composer: PromptComposer for the governed author_voice_drift prompt
                (None → ConfigurationError at check time).
            invocation_pipeline: Optional InvocationPipeline for evidence.
            api_key: Optional per-user provider API key override (model-routing
                cascade) — forwarded to the drift pipeline's ``get_model``
                call.
            base_url: Optional per-user provider base URL override.
        """
        self._series_repo = series_repo
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = model_registry
        self._config = model_config
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline
        self._api_key = api_key
        self._base_url = base_url

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

        config = self._config
        if config is None:
            raise NotFoundError("Model config", identifier="no_model_config")
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

        # 6. Deterministic per-chapter narrator metrics (ADR-021). No chapter
        #    with prose → graceful no_profile (mirrors the novel-level service).
        per_chapter = compute_author_voice_per_chapter(chapters, language)
        if not per_chapter:
            logger.info(
                "series_voice_drift_no_profile",
                feature_id="series_voice_drift",
                series_id=str(series_id),
                novel_id=str(novel_id),
                reason="no_chapters_with_prose",
            )
            return _no_profile_response(novel_id, "no_chapters_with_prose")

        # 7. Resolve the governed author_voice_drift system prompt (Mode 1,
        #    ADR-054) — one composition per check (only after prose confirmed).
        composed_prompt = await resolve_author_voice_drift_prompt(
            composer,
            self._invocation_pipeline,
            novel=novel,
            language=language,
            novel_id=novel_id,
            user_id=user_id,
        )

        # 8. Trend (signal i) + jumps (signal iii) + agent (1 LLM call) +
        #    result assembly against the SERIES baseline. The descriptive
        #    profile + precomputed trend + jumps + chapter metadata flow as
        #    runtime content (user channel, RULE-02a category 3); metrics never
        #    reach the LLM as raw numbers (ADR-074 binding preserved).
        result = await analyse_author_voice_drift(
            chapters=chapters,
            per_chapter=per_chapter,
            profile=profile,
            profile_voice_metrics=series_voice_metrics,
            profile_author_metrics=series_author_metrics,
            composed_prompt=composed_prompt,
            novel=novel,
            language=language,
            novel_id=novel_id,
            model_registry=self._registry,
            model_config=config,
            api_key=self._api_key,
            base_url=self._base_url,
        )
        logger.info(
            "series_voice_drift_complete",
            feature_id="series_voice_drift",
            series_id=str(series_id),
            novel_id=str(novel_id),
            chapter_count=len(chapters),
        )
        return AuthorVoiceDriftResponse(novel_id=str(novel_id), result=result)

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
