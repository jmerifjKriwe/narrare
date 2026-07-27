"""Author Voice analysis service — calls AuthorVoiceAgent (ANAL-007 / ADR-074).

Orchestrates the ADR-074 hybrid pipeline over a novel's selected chapters:
load chapters → ``VoiceMetricsAnalyzer.analyze_text`` (voice-generic metrics)
→ ``AuthorMetricsAnalyzer.analyze`` (author-specific metrics) → resolve the
governed ``author_voice`` system prompt via Mode 1 → :class:`AuthorVoiceAgent`
(one LLM call, descriptive-only) → assemble :class:`AuthorVoiceProfile` →
persist via :class:`AuthorVoiceRepository`.

Author-voice difference from character voice: the input is the narrator's
FULL chapter prose (narration + dialogue together), not per-utterance
dialogue (the measurement vocabulary is voice-generic, ADR-074 type-reuse).

Prompt resolution is Mode 1 (composer-driven, ADR-054). The chapter prose +
precomputed metrics flow as runtime data in the agent run prompt (user
channel, RULE-02a category 3). No inline f-string feature prompt is
assembled in the service (RULE-02 / RULE-02a).

RULE-11 graceful degradation: no chapters / empty selection → terminal
``"done"`` with a progress message (no LLM call, no crash). Below the
3-chapter minimum → a soft ``"progress"`` warning (does not block).

Pattern: Service → PromptComposer (RULE-02) → Core Agent (RULE-01b)
         → AuthorVoiceRepository (RULE-07, ADR-074 no-raw-column-access).

See:
    :mod:`narrare.analysis.contracts_author_voice` — the Protocol.
    :mod:`narrare.analysis.author_voice_repository` — storage (ADR-074).
    :mod:`narrare.analysis.author_voice_prompt` — Mode-1 prompt resolver.
    :mod:`narrare.analysis.author_voice_agent_runner` — agent invocation.
    :mod:`narrare.analysis.author_voice_profile_assembler` — profile builder.
    ADR-074 — Author Voice Storage Contract.
    ADR-054 — Mode 1 (composer-driven) prompt resolution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.analysis.author_voice_agent_runner import run_author_voice_agent
from narrare.analysis.author_voice_profile_assembler import assemble_author_voice_profile
from narrare.analysis.author_voice_prompt import resolve_author_voice_prompt
from narrare.analysis.schemas_author_voice import (
    AuthorVoiceResult,
    AuthorVoiceStreamEvent,
)
from narrare_core.shared.errors import ConfigurationError, NotFoundError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from narrare.analysis.author_voice_repository import AuthorVoiceRepository
    from narrare.chapters.repository import ChapterRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.analysis.author_metrics import AuthorMetricsAnalyzer
    from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.profiles.author_voice import AuthorVoiceProfile
    from narrare_core.prompts.composer import PromptComposer

#: Minimum chapter count for a meaningful profile (spec: "Select 3+ chapters").
#: Below this the service surfaces a soft warning but does NOT block — the
#: panel may also enforce the threshold client-side.
MIN_CHAPTERS_FOR_PROFILE: int = 3

logger = structlog.get_logger(__name__)


class AuthorVoiceService:
    """Service for author-voice profiling analysis (ANAL-007 / ADR-074).

    Takes a novel + chapter selection, runs the ADR-074 hybrid pipeline
    (deterministic metrics + LLM qualitative profile over the narrator's full
    prose), assembles an :class:`AuthorVoiceProfile`, persists it to
    ``ProjectSettings.author_voice`` via :class:`AuthorVoiceRepository`
    (no raw column access — ADR-074 binding), and streams the result as SSE
    events.

    The ``author_voice`` prompt is resolved through :class:`PromptComposer`
    in Mode 1 (ADR-054 D1): the governed
    ``_bundled/analysis/{locale}/author_voice/system.md`` template carries
    the task framing and project metadata variables. No inline f-string
    feature prompt is assembled in the service (RULE-02 / RULE-02a).

    Constructor args are documented on :meth:`__init__`; the full method
    contracts (Args/Yields/Raises) live on
    :class:`narrare.analysis.contracts_author_voice.AuthorVoiceServiceProtocol`
    (RULE-03 SSOT).
    """

    def __init__(
        self,
        novel_repo: NovelRepository,
        chapter_repo: ChapterRepository,
        repository: AuthorVoiceRepository,
        model_registry: ModelRegistry,
        model_config: ResolvedModelConfig | None = None,
        composer: PromptComposer | None = None,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._repository = repository
        self._registry = model_registry
        self._config = model_config
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline

    async def analyze(
        self,
        novel_id: UUID,
        chapter_ids: list[UUID] | None,
        user_id: UUID,
    ) -> AsyncIterator[AuthorVoiceStreamEvent]:
        """Profile the author voice across selected chapters, streaming SSE.

        Runs the ADR-074 hybrid pipeline, assembles the profile, persists it
        via :class:`AuthorVoiceRepository`, and yields a ``"progress"`` event,
        one ``"result"`` event carrying the profile, then a terminal
        ``"done"`` event. Full contract (Args/Yields/Raises) lives on
        :class:`AuthorVoiceServiceProtocol` (RULE-03 SSOT).
        """
        # 1. Resolve novel (access control + metadata).
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        if self._config is None:
            raise NotFoundError("Model config", identifier="no_model_config")

        if self._composer is None:
            raise ConfigurationError(
                "PromptComposer is not configured for author-voice analysis.",
                code="NO_COMPOSER",
            )

        language = novel.writing_language or "en"

        # 2. Load selected chapters' prose (specific ids or all chapters).
        #    Reuses the established chapter-loading helper (it validates
        #    chapter_ids belong to the novel — not character-voice-specific).
        from narrare.analysis.character_voice_kb_writer import load_selected_chapters

        chapters = await load_selected_chapters(self._chapter_repo, novel_id, chapter_ids)

        # RULE-11 graceful degradation: no chapters → terminal done, no LLM
        # call (saves cost; the agent has nothing to profile).
        if not chapters:
            logger.info(
                "author_voice_no_chapters",
                feature_id="analysis_author_voice",
                novel_id=str(novel_id),
            )
            yield AuthorVoiceStreamEvent(
                event="progress",
                progress="No chapters found in the novel.",
            )
            yield AuthorVoiceStreamEvent(event="done", is_final=True)
            return

        # Soft warning below the recommended minimum (does NOT block — the
        # spec surfaces a warning, the user may proceed).
        if len(chapters) < MIN_CHAPTERS_FOR_PROFILE:
            yield AuthorVoiceStreamEvent(
                event="progress",
                progress=(
                    f"Warning: analysing {len(chapters)} chapter(s); "
                    f"{MIN_CHAPTERS_FOR_PROFILE}+ recommended for a meaningful profile."
                ),
            )

        yield AuthorVoiceStreamEvent(
            event="progress",
            progress=f"Analysing author voice across {len(chapters)} chapter(s).",
        )

        # 3. Extract prose — full chapter text (narration + dialogue together).
        #    This is the author-voice difference from character voice: the
        #    narrator's full prose, not per-utterance dialogue.
        chapter_prose = [(c.content or "") for c in chapters]
        combined_prose = "\n\n".join(chapter_prose)

        # 4-5. Compute deterministic metrics over the full prose.
        voice_analyzer = self._make_voice_metrics_analyzer(language)
        author_analyzer = self._make_author_metrics_analyzer()
        voice_metrics = voice_analyzer.analyze_text(chapter_prose)
        author_metrics = author_analyzer.analyze(chapter_prose)

        # 6. Resolve the governed author_voice system prompt via PromptComposer
        #    (RULE-02 / ADR-054 D1). The template
        #    ``_bundled/analysis/{locale}/author_voice/system.md`` carries
        #    the task framing and project metadata variables.
        composed_prompt = await resolve_author_voice_prompt(
            self._composer,
            self._invocation_pipeline,
            novel=novel,
            language=language,
            novel_id=novel_id,
            user_id=user_id,
        )

        # 7. Run the agent — one LLM call. The chapter prose excerpt +
        #    precomputed metrics flow as runtime content in the run prompt
        #    (user channel, RULE-02a category 3).
        output = await run_author_voice_agent(
            chapter_prose=combined_prose,
            voice_metrics=voice_metrics,
            author_metrics=author_metrics,
            novel_title=novel.title,
            novel_genre=novel.genre or "",
            novel_id=novel_id,
            language=language,
            model_registry=self._registry,
            model_config=self._config,
            composed_prompt=composed_prompt,
        )

        # 8. Assemble + persist the profile (descriptive + metric groups).
        profile = assemble_author_voice_profile(
            descriptive=output,
            voice_metrics=voice_metrics,
            author_metrics=author_metrics,
        )
        await self._repository.save(novel_id, profile)

        logger.info(
            "author_voice_analysis_complete",
            feature_id="analysis_author_voice",
            novel_id=str(novel_id),
            chapter_count=len(chapters),
        )

        # 9. Stream the result event (single profile per novel).
        yield AuthorVoiceStreamEvent(
            event="result",
            result=AuthorVoiceResult(novel_id=str(novel_id), profile=profile),
        )
        yield AuthorVoiceStreamEvent(event="done", is_final=True)

    async def get_profile(
        self,
        novel_id: UUID,
        user_id: UUID,
    ) -> AuthorVoiceProfile | None:
        """Load the stored author-voice profile for a novel.

        Reads via :class:`AuthorVoiceRepository` (no raw column access,
        ADR-074 binding). Validates novel access first.
        """
        await self._require_novel_access(novel_id, user_id)
        return await self._repository.load(novel_id)

    async def clear_profile(self, novel_id: UUID, user_id: UUID) -> None:
        """Clear the stored author-voice profile for a novel.

        Delegates to :meth:`AuthorVoiceRepository.clear` (NULLs the column).
        Validates novel access first.
        """
        await self._require_novel_access(novel_id, user_id)
        await self._repository.clear(novel_id)

    # ------------------------------------------------------------------
    # Access-control helper
    # ------------------------------------------------------------------

    async def _require_novel_access(self, novel_id: UUID, user_id: UUID) -> None:
        """Raise NotFoundError when the novel is missing/inaccessible."""
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

    # ------------------------------------------------------------------
    # Analyzer construction (overridable for tests)
    # ------------------------------------------------------------------

    def _make_voice_metrics_analyzer(self, language: str) -> VoiceMetricsAnalyzer:
        from narrare_core.analysis.voice_metrics import VoiceMetricsAnalyzer

        return VoiceMetricsAnalyzer(language=language)  # type: ignore[arg-type]

    def _make_author_metrics_analyzer(self) -> AuthorMetricsAnalyzer:
        from narrare_core.analysis.author_metrics import AuthorMetricsAnalyzer

        return AuthorMetricsAnalyzer()
