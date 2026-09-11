"""Author-voice-drift analysis service — orchestrates ANAL-009 Phase 2B (ADR-074).

The author-voice analogue of Phase 1's
:class:`~narrare.analysis.voice_drift_service.CharacterVoiceDriftService`.
For a novel with a stored :class:`AuthorVoiceProfile` whose metric group
(``voice_analysis.voice_metrics`` + ``author_metrics``) is present, the
service loads the novel's chapters, computes the deterministic per-chapter
narrator trend (signal i, voice + author deltas merged) + jumps (signal iii),
runs the governed ``author_voice_drift`` agent — **one LLM call per run**
(ADR-073 Decision 5 cardinality, applied to ADR-074) — and streams the
result. The per-narrator pipeline is split across focused helpers (RULE-04):
prompt resolution in :mod:`author_voice_drift_prompt`; the narrator metrics +
trend + jumps + agent + result assembly in :mod:`author_voice_drift_pipeline`;
agent invocation in :mod:`author_voice_drift_agent_runner`; runtime-content
formatting in :mod:`author_voice_drift_runtime_content`; result assembly in
:mod:`author_voice_drift_results`.

RULE-11 graceful degradation: a novel with no stored profile, a profile
missing the metric blocks, or no chapter with prose yields a graceful
``no_profile`` event (never a crash). A novel with no chapters yields an
empty ``"progress"`` + ``"done"`` (no LLM call).

The service is **read-only** (ADR-073 Decision 5): it never writes to
``ProjectSettings.author_voice``. The stored profile is read via
:class:`AuthorVoiceRepository` (ADR-074 no-direct-column binding).

Prompt resolution is Mode 1 (composer-driven, ADR-054): the governed
``author_voice_drift`` system prompt is resolved ONCE per run and bound to the
agent constructor. No inline f-string feature prompt is assembled (RULE-02 /
RULE-02b). The precomputed trend + jumps + stored descriptive profile +
chapter metadata flow as runtime data in the agent run prompt (user channel,
RULE-02a category 3).

RULE-13 (ADR-065): ``run()`` returns the aggregated response;
``run_stream()`` yields SSE events. The router uses ``run_stream()``.

See:
    :mod:`narrare.analysis.contracts_author_voice_drift` — the Protocol.
    ADR-074 — Author Voice Storage Contract.
    ADR-073 — Character Voice Drift (the Phase 1 parallel mirrored here).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.analysis.author_voice_drift_pipeline import (
    analyse_author_voice_drift,
    compute_author_voice_per_chapter,
    make_author_voice_drift_no_profile_event,
)
from narrare.analysis.author_voice_drift_prompt import (
    resolve_author_voice_drift_prompt,
)
from narrare.analysis.schemas_author_voice_drift import (
    AuthorVoiceDriftEvent,
    AuthorVoiceDriftNoProfile,
    AuthorVoiceDriftRequest,
    AuthorVoiceDriftResponse,
    AuthorVoiceDriftResult,
)
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from narrare.analysis.author_voice_repository import AuthorVoiceRepository
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class AuthorVoiceDriftService:
    """Service for longitudinal author-voice drift analysis (ANAL-009 Phase 2B).

    The drift analysis is read-only: it never writes to
    ``ProjectSettings.author_voice`` (ADR-073 Decision 5). The stored profile
    is read via :class:`AuthorVoiceRepository` only, preserving ADR-074's
    no-direct-column boundary (no SSOT bypass).

    Args:
        novel_repo: Repository for novel access-control + metadata.
        chapter_repo: Repository used to load the novel's chapters.
        author_voice_repo: Repository for the stored author-voice profile
            (ADR-074 — read via ``load(novel_id)``, never a raw column access).
        model_registry: Shared LLM model registry.
        model_config: Resolved model configuration for the agent call.
        composer: PromptComposer for governed Mode-1 prompt resolution.
        invocation_pipeline: Optional invocation governance pipeline.
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        chapter_repo: ChapterRepository,
        author_voice_repo: AuthorVoiceRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None = None,
        composer: PromptComposer | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._author_voice_repo = author_voice_repo
        self._registry = model_registry
        self._config = model_config
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline
        self._api_key = api_key
        self._base_url = base_url

    async def run(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: AuthorVoiceDriftRequest,
    ) -> AuthorVoiceDriftResponse:
        """Non-streaming aggregate of :meth:`run_stream`.

        Collects the single ``"result"`` event (or the graceful
        ``"no_profile"`` event) into an :class:`AuthorVoiceDriftResponse`.
        """
        result: AuthorVoiceDriftResult | None = None
        no_profile: AuthorVoiceDriftNoProfile | None = None
        async for event in self.run_stream(novel_id, user_id, request):
            if event.event == "result" and event.result is not None:
                result = event.result
            elif event.event == "no_profile" and event.no_profile is not None:
                no_profile = event.no_profile
        return AuthorVoiceDriftResponse(
            novel_id=str(novel_id),
            result=result,
            no_profile=no_profile,
        )

    async def run_stream(
        self,
        novel_id: UUID,
        user_id: UUID,
        request: AuthorVoiceDriftRequest,
    ) -> AsyncIterator[AuthorVoiceDriftEvent]:
        """Analyse longitudinal author-voice drift, streaming SSE events.

        Yields a ``"progress"`` event, then EITHER one ``"result"`` event
        (carrying the narrator trend + jumps + overall score/band + the agent
        classification) OR one ``"no_profile"`` event (RULE-11 graceful), then
        a terminal ``"done"`` event.

        Full contract (Args/Yields/Raises) lives on
        :class:`narrare.analysis.contracts_author_voice_drift.AuthorVoiceDriftServiceProtocol`
        (RULE-03 SSOT).
        """
        # 1. Resolve novel (access control + metadata).
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        config = self._config
        if config is None:
            raise NotFoundError("Model config", identifier="no_model_config")

        composer = self._composer
        if composer is None:
            raise ConfigurationError(
                "PromptComposer is not configured for author-voice-drift analysis.",
                code="NO_COMPOSER",
            )

        language = novel.writing_language or "en"

        # 2. Read the stored profile via the repository (ADR-074 — no direct
        #    column access). No profile → graceful no_profile, no LLM call.
        profile = await self._author_voice_repo.load(novel_id)
        if profile is None:
            logger.info(
                "author_voice_drift_no_profile",
                feature_id="analysis_author_voice_drift",
                novel_id=str(novel_id),
                reason="no_stored_profile",
            )
            yield make_author_voice_drift_no_profile_event("no_stored_profile")
            yield AuthorVoiceDriftEvent(event="done", is_final=True)
            return

        # 3. Extract the metric blocks the trend comparison needs. A profile
        #    missing voice_metrics or author_metrics cannot be trend-compared
        #    → graceful no_profile (mirrors Phase 1's no_voice_metrics).
        voice_analysis = profile.voice_analysis
        profile_voice_metrics = voice_analysis.voice_metrics if voice_analysis is not None else None
        profile_author_metrics = profile.author_metrics
        if profile_voice_metrics is None or profile_author_metrics is None:
            logger.info(
                "author_voice_drift_no_profile",
                feature_id="analysis_author_voice_drift",
                novel_id=str(novel_id),
                reason="no_profile_metrics",
            )
            yield make_author_voice_drift_no_profile_event("no_profile_metrics")
            yield AuthorVoiceDriftEvent(event="done", is_final=True)
            return

        # 4. Load chapters (specific ids or all chapters in the novel). Reuses
        #    the established chapter-loading helper (validates chapter_ids
        #    belong to the novel — not author-voice-specific).
        from narrare.analysis.character_voice_kb_writer import load_selected_chapters

        chapter_ids = [UUID(cid) for cid in request.chapter_ids] if request.chapter_ids else None
        chapters = await load_selected_chapters(self._chapter_repo, novel_id, chapter_ids)

        if not chapters:
            logger.info(
                "author_voice_drift_no_chapters",
                feature_id="analysis_author_voice_drift",
                novel_id=str(novel_id),
            )
            yield AuthorVoiceDriftEvent(
                event="progress",
                progress="No chapters found in the novel.",
            )
            yield AuthorVoiceDriftEvent(event="done", is_final=True)
            return

        yield AuthorVoiceDriftEvent(
            event="progress",
            progress=f"Analysing author-voice drift across {len(chapters)} chapter(s).",
        )

        # 5. Deterministic per-chapter narrator metrics (ADR-021). No chapter
        #    with prose → graceful no_profile (mirrors Phase 1's silent-
        #    character skip) rather than call the LLM on nothing.
        per_chapter = compute_author_voice_per_chapter(chapters, language)
        if not per_chapter:
            logger.info(
                "author_voice_drift_no_profile",
                feature_id="analysis_author_voice_drift",
                novel_id=str(novel_id),
                reason="no_chapters_with_prose",
            )
            yield make_author_voice_drift_no_profile_event("no_chapters_with_prose")
            yield AuthorVoiceDriftEvent(event="done", is_final=True)
            return

        # 6. Resolve the governed author_voice_drift system prompt (Mode 1,
        #    ADR-054) — one composition per run (only after prose confirmed).
        composed_prompt = await resolve_author_voice_drift_prompt(
            composer,
            self._invocation_pipeline,
            novel=novel,
            language=language,
            novel_id=novel_id,
            user_id=user_id,
        )

        # 7. Trend (signal i) + jumps (signal iii) + agent (1 LLM call) +
        #    result assembly for the single narrator. The stored descriptive
        #    profile + precomputed trend + jumps + chapter metadata flow as
        #    runtime content (user channel, RULE-02a category 3); metrics
        #    never reach the LLM as raw numbers (ADR-074 binding preserved).
        result = await analyse_author_voice_drift(
            chapters=chapters,
            per_chapter=per_chapter,
            profile=profile,
            profile_voice_metrics=profile_voice_metrics,
            profile_author_metrics=profile_author_metrics,
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
            "author_voice_drift_complete",
            feature_id="analysis_author_voice_drift",
            novel_id=str(novel_id),
            chapter_count=len(chapters),
        )
        yield AuthorVoiceDriftEvent(event="result", result=result)
        yield AuthorVoiceDriftEvent(event="done", is_final=True)
