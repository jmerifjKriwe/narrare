"""BandSummaryService — generate / lazy / override (Spec 2, Task 3).

Business logic only (RULE-06): no SQL, no HTTP. Delegates persistence to
``BandSummaryRepository`` and the LLM call to ``BandSummaryAgent`` (agents are
the primary LLM surface — RULE-01b). Prompts come from ``PromptComposer``
(RULE-02/02b: no inline prompt strings); chapter summaries flow as runtime
content in the agent run prompt (RULE-02a category 3 — user channel).

Chapter summaries are sourced from ``Chapter.summary`` (``chapters/models.py``)
via ``list_by_novel``; only non-empty summaries are aggregated. Novel metadata
(title, genre, writing_language) comes from ``NovelRepository.get``.

Testability (ADR-030 — Fake-based): the agent is injectable via
``agent_factory`` (default → real ``BandSummaryAgent``) so unit tests supply a
fake agent whose ``.run()`` returns a controlled ``BandSummaryOutput``, instead
of ``unittest.mock.patch``-ing the class. This mirrors how
``FakeLLMGateway`` makes ``ChapterSummaryService`` testable, but at the agent
boundary because that is the LLM surface here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from narrare_core.agents.band_summary_agent import BandSummaryAgent
from narrare_core.agents.band_summary_types import BandSummaryDeps
from narrare_core.ai_invocation import compose_invocation
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import NotFoundError, ValidationError, WritingError

if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare.series.band_summary_contracts import BandSummaryRepositoryProtocol
    from narrare.series.band_summary_models import BandSummary
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)

#: Intent + governed context_mode for band-summary prompts (registered in
#: route_table by Spec 2 Task 2). The template lives at
#: ``_bundled/analysis/{lang}/band_summary/system.md``.
_BAND_SUMMARY_MODE = "band_summary"


def _default_agent_factory(model: Any, system_prompt: str | None = None) -> BandSummaryAgent:
    """Production agent factory (overridable in tests for Fake injection)."""
    return BandSummaryAgent(model=model, system_prompt=system_prompt)


class BandSummaryService:
    """Generates + manages novel-level band summaries for series history.

    Three operations back the Band Summary API (Task 4) and the auto-trigger
    (Task 5):

    - ``generate`` — fetch chapter summaries → run ``BandSummaryAgent`` → upsert.
    - ``get_or_generate`` — lazy: return existing (if override/full set) else
      generate on demand. Used by ``SeriesHistoryTier`` (Task 6).
    - ``update_override`` — set or clear the user override (precedence over
      generated text at assembly time).

    All dependencies are injected (RULE-07). Ownership/authorisation is
    enforced at the router boundary (Task 4) — this service is keyed by
    ``novel_id`` and is also usable from non-request contexts (in-process
    auto-trigger, Task 5).
    """

    def __init__(
        self,
        *,
        repo: BandSummaryRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        chapter_repo: ChapterRepositoryProtocol,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        composer: PromptComposer,
        agent_factory: Callable[..., BandSummaryAgent] | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        """Initialise the service with all dependencies.

        Args:
            repo: Band-summary persistence (upsert / override).
            novel_repo: Novel metadata (title, genre, writing_language).
            chapter_repo: Chapter summaries (``list_by_novel`` → ``.summary``).
            registry: Model registry for resolving the LLM model instance.
            config: Resolved model config (provider, model, params).
            composer: PromptComposer for the governed band_summary system prompt.
            agent_factory: Callable ``(model, system_prompt) -> BandSummaryAgent``.
                Defaults to the real constructor; tests inject a Fake.
            api_key: Optional per-user API key override.
            base_url: Optional per-user base URL override.
            invocation_pipeline: Optional InvocationPipeline for evidence.
        """
        self._repo = repo
        self._novel_repo = novel_repo
        self._chapter_repo = chapter_repo
        self._registry = registry
        self._config = config
        self._composer = composer
        self._agent_factory = agent_factory or _default_agent_factory
        self._api_key = api_key
        self._base_url = base_url
        self._invocation_pipeline = invocation_pipeline

    async def get(self, novel_id: uuid.UUID) -> BandSummary:
        """Return the existing band summary (no generation).

        Used by the GET endpoint (Task 4) to fetch a previously generated
        summary without triggering an LLM call. Distinct from
        ``get_or_generate`` (lazy) and ``generate`` (forced).

        Raises:
            NotFoundError: If no band summary row exists for ``novel_id``.
        """
        existing = await self._repo.get(novel_id)
        if existing is None:
            raise NotFoundError("BandSummary", identifier=str(novel_id))
        return existing

    async def generate(self, novel_id: uuid.UUID) -> BandSummary:
        """Auto-generate: fetch chapter summaries → agent → upsert.

        Args:
            novel_id: The novel (band) to summarise.

        Returns:
            The upserted ``BandSummary`` row.

        Raises:
            NotFoundError: The novel does not exist.
            ValidationError: The novel has no chapter summaries to aggregate.
            WritingError: The LLM call or persistence failed.
        """
        # 1. Load novel metadata (title, genre, writing_language).
        novel = await self._novel_repo.get(novel_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        # 2. Aggregate non-empty chapter summaries, ordered by position
        #    (ChapterRepository.list_by_novel already orders by position).
        chapters = await self._chapter_repo.list_by_novel(novel_id)
        chapter_summaries = [c.summary for c in chapters if c.summary.strip()]
        if not chapter_summaries:
            # RULE-11: fail fast + explicit. The agent validator requires
            # non-empty output, so aggregating nothing would hallucinate;
            # callers (auto-trigger, lazy tier) catch this to degrade.
            logger.info("band_summary_skipped_no_summaries", novel_id=str(novel_id))
            raise ValidationError(
                "Cannot generate band summary: the novel has no chapter summaries to aggregate"
            )

        # 3. Compose the governed band_summary system prompt (RULE-02/02b).
        #    Mode 1 (composer-driven) with pipeline fallback to direct build.
        language = novel.writing_language or "en"
        system_prompt = await self._compose_system_prompt(
            novel_title=novel.title,
            genre=novel.genre,
            language=language,
            novel_id=novel_id,
        )

        try:
            # 4. Resolve model + instantiate agent (RULE-01b: agents-first).
            model = await self._registry.get_model(
                self._config, api_key=self._api_key, base_url=self._base_url
            )
            agent = self._agent_factory(model, system_prompt)

            # 5. Run the agent. Chapter summaries flow as runtime content in
            #    the user-channel prompt (RULE-02a category 3); BandSummaryDeps
            #    carries the same data for validators/tools.
            deps = BandSummaryDeps(
                novel_title=novel.title,
                genre=novel.genre,
                chapter_summaries=chapter_summaries,
            )
            result = await agent.run(prompt=_format_chapter_summaries(chapter_summaries), deps=deps)

            # 6. Upsert generated summaries (override preserved by the repo).
            band_summary = await self._repo.upsert(
                novel_id,
                full_summary=result.full_summary,
                short_summary=result.short_summary,
            )
            logger.info(
                "band_summary_generated",
                novel_id=str(novel_id),
                chapter_count=len(chapter_summaries),
            )
            return band_summary

        except NotFoundError:
            raise
        except ValidationError:
            raise
        except Exception as exc:
            logger.error(
                "band_summary_generation_failed",
                novel_id=str(novel_id),
                error=str(exc),
                exc_info=True,
            )
            raise WritingError("Band summary generation failed") from exc

    async def get_or_generate(self, novel_id: uuid.UUID) -> BandSummary:
        """Lazy: return existing summary if useful, else generate on demand.

        A row counts as "useful" when it has an override OR a full_summary —
        an empty placeholder row (e.g. created by a lone clear_override) is
        treated as missing and regenerated.
        """
        existing = await self._repo.get(novel_id)
        if existing is not None and (existing.override or existing.full_summary):
            return existing
        return await self.generate(novel_id)

    async def update_override(self, novel_id: uuid.UUID, override: str | None) -> BandSummary:
        """Set or clear the user override.

        An empty/whitespace override is treated as "clear" so no empty
        override is ever persisted.
        """
        if override and override.strip():
            return await self._repo.set_override(novel_id, override)
        return await self._repo.clear_override(novel_id)

    async def _compose_system_prompt(
        self,
        *,
        novel_title: str,
        genre: str,
        language: str,
        novel_id: uuid.UUID,
    ) -> str:
        """Resolve the governed ``band_summary`` system prompt (RULE-02b).

        Uses ``compose_invocation`` (Mode 1, composer-driven) with the
        InvocationPipeline when available, falling back to direct
        ``composer.build`` on any failure — mirroring ``ChapterSummaryService``
        so a pipeline hiccup never blocks generation.
        """
        from narrare._app.invocation_context import build_invocation_context

        context = PromptContext(
            language=language,
            writing_language=language,
            project_title=novel_title,
            genre=genre,
            mode=_BAND_SUMMARY_MODE,
        )
        invocation_context = build_invocation_context(
            feature_id="series_band_summary",
            intent=LLMIntent.SUMMARIZE,
            project_id=novel_id,
            language=language,
        )
        try:
            invocation_result = await compose_invocation(
                invocation_pipeline=self._invocation_pipeline,
                invocation_context=invocation_context,
                composer=self._composer,
                prompt_context=context,
                intent=LLMIntent.SUMMARIZE,
            )
            assert invocation_result.composed_prompt is not None  # Mode 1 always composes
            return invocation_result.composed_prompt.system
        except Exception:
            logger.warning(
                "band_summary_composition_failed",
                feature_id="series_band_summary",
                exc_info=True,
            )
            composed = await self._composer.build(LLMIntent.SUMMARIZE, context)
            return composed.system


def _format_chapter_summaries(chapter_summaries: list[str]) -> str:
    """Format chapter summaries as the agent run prompt (user-channel runtime content).

    Numbered, one per line — mirrors how analysis agents receive their passage.
    Kept module-private (business-logic formatting detail, RULE-06).
    """
    return "\n".join(f"{i}. {s}" for i, s in enumerate(chapter_summaries, start=1))
