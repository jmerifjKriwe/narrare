"""Service for chapter summarization using ChapterSummaryAgent.

Orchestrates: get chapter content → compose prompt → instantiate agent → run → persist.
Dependencies are injected via __init__ (DI pattern, RULE-07).
All prompts come from PromptComposer (RULE-02).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import structlog

from narrare.writing.summary_contracts import SummaryResult
from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps
from narrare_core.ai_invocation import compose_invocation
from narrare_core.llm.intents import LLMIntent
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import NotFoundError, WritingError

if TYPE_CHECKING:
    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare.novels.repository import NovelRepository
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm import ResolvedModelConfig
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class ChapterSummaryService:
    """Generates chapter summaries using ChapterSummaryAgent.

    Orchestrates loading chapter content from the repository,
    composing prompts via PromptComposer, running the summary agent,
    and persisting the result.

    Attributes:
        _registry: Model registry for getting configured LLM model instances.
        _config: Resolved model configuration (provider, model, params).
        _chapter_repo: Repository for chapter persistence.
        _novel_repo: Repository for the novel ownership gate.
        _composer: PromptComposer for building system and user prompts.
        _api_key: Optional per-user API key override.
        _base_url: Optional per-user base URL override.
        _invocation_pipeline: Optional InvocationPipeline for evidence recording.
        _kb_context_provider: Optional canonical KB-context provider (ADR-067)
            supplying the kb_characters / kb_locations / kb_factions /
            kb_relationships prompt variables.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        composer: PromptComposer,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        invocation_pipeline: InvocationPipeline | None = None,
        kb_context_provider: KBContextProviderProtocol | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        """Initialize ChapterSummaryService with all dependencies.

        Args:
            registry: Model registry for LLM model instances.
            config: Resolved model config (provider, model, params).
            chapter_repo: Repository for loading/saving chapters.
            novel_repo: Repository for the chapter→novel ownership gate.
            composer: PromptComposer for building prompts (RULE-02).
            api_key: Optional per-user API key override.
            base_url: Optional per-user base URL override.
            invocation_pipeline: Optional InvocationPipeline for evidence recording.
            kb_context_provider: Optional canonical KB-context provider
                (ADR-067) for the kb_characters / kb_locations / kb_factions /
                kb_relationships prompt variables. ``None`` degrades to an
                empty bundle (RULE-11).
            run_limit_resolver: Optional ADR-045 run-limit resolver; defaults to
                ``DefaultRunLimitResolver`` (Task 3 wiring).
        """
        self._registry = registry
        self._config = config
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._composer = composer
        self._api_key = api_key
        self._base_url = base_url
        self._invocation_pipeline = invocation_pipeline
        self._kb_context_provider = kb_context_provider
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    async def summarize(
        self,
        chapter_id: UUID,
        max_sentences: int = 4,
        language: str = "en",
        *,
        user_id: str,
    ) -> SummaryResult:
        """Generate a summary for the given chapter and persist it.

        Ownership gate (IDOR remediation S4, Pattern B): directly after
        the chapter None-check — BEFORE the content load, the LLM call,
        and the ``update_summary`` write — the chapter's novel must
        belong to ``user_id``; otherwise ``NotFoundError`` (foreign ≡
        unknown, anti-enumeration).

        Args:
            chapter_id: The UUID of the chapter to summarize.
            max_sentences: Maximum number of sentences in the summary.
            language: Output language code.
            user_id: Authenticated user identifier (ownership check).

        Returns:
            SummaryResult with summary text, word count, and key points.

        Raises:
            NotFoundError: If the chapter does not exist or its novel
                belongs to another user.
            WritingError: If the LLM call or persistence fails.
        """
        # 1. Load chapter
        chapter = await self._chapter_repo.get(chapter_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        # 2. Ownership gate: the chapter's novel must belong to the caller
        #    BEFORE any content is read, the LLM is invoked, or the summary
        #    is written (IDOR remediation S4).
        novel = await self._novel_repo.get_by_id(chapter.novel_id, UUID(user_id))
        if novel is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        content = chapter.content
        if not content:
            logger.info("summary_skipped_empty", chapter_id=str(chapter_id))
            return SummaryResult(summary="", word_count=0)

        # 2. Compose prompt via compose_invocation (Mode 1 — composer-driven,
        #    ADR-048). Enrichment flows through the composer into the system
        #    prompt; chapter content is passed as the user prompt at agent.run.
        try:
            from narrare._app.invocation_context import build_invocation_context

            # Canonical KB context (ADR-067): the kb_characters /
            # kb_locations / kb_factions / kb_relationships slots are
            # fetched+rendered through the reusable provider (mirrors
            # coreference_service). Degrades to an empty bundle when no
            # provider is wired or the KB is empty (RULE-11) — the provider
            # never raises. Spreading ``to_prompt_variables()`` — not a
            # literal ``""`` assignment — keeps every slot fed from real KB
            # context (architectural-discipline §7). Inert today: the
            # governed summarize template's Knowledge-Base region sits below
            # the extract_section parse cutoff, so these extra variables do
            # not alter the composed render (inert pre-activation for the
            # template re-enablement slice).
            from narrare_core.context._render_options import RenderOptions

            if self._kb_context_provider is None:
                from narrare.kb.context_contracts import KBContextBundle

                kb_bundle = KBContextBundle.empty(RenderOptions(annotate_provenance=True))
            else:
                kb_bundle = await self._kb_context_provider.fetch_context(
                    chapter.novel_id,
                    entity_types=["character", "location", "faction"],
                    options=RenderOptions(annotate_provenance=True),
                )
            kb_vars = kb_bundle.to_prompt_variables()

            context = PromptContext(
                language=language,
                genre="",
                chapter_title=chapter.title,
                mode="summarize",
                extra={
                    "max_sentences": str(max_sentences),
                    **(kb_vars or {}),
                },
            )
            invocation_context = build_invocation_context(
                feature_id="writing_summary",
                intent=LLMIntent.SUMMARIZE,
                project_id=chapter.novel_id,
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
                system_prompt = invocation_result.composed_prompt.system
            except Exception:
                logger.warning(
                    "invocation_composition_failed",
                    feature_id="writing_summary",
                    exc_info=True,
                )
                composed = await self._composer.build(LLMIntent.SUMMARIZE, context)
                system_prompt = composed.system

            # 3. Run the summary agent — single assembly point (Task 6c —
            #    Task 4/5 pattern): model + intent-aware runtime settings +
            #    usage limits as one coherent triple.
            resolved = self._run_limit_resolver.resolve(
                config=self._config, budget=None, invocation_id=uuid4()
            )
            prepared = await self._registry.prepare(
                self._config,
                intent=LLMIntent.SUMMARIZE,
                usage_limits=resolved.usage_limits,
                api_key=self._api_key,
                base_url=self._base_url,
            )
            agent = ChapterSummaryAgent(model=prepared.model, system_prompt=system_prompt)

            deps = SummaryDeps(
                language=language,
                genre="",
                chapter_title=chapter.title,
                max_sentences=max_sentences,
            )

            result = await agent.run(
                prompt=content[:3000],
                deps=deps,
                model_settings=prepared.model_settings,
                usage_limits=prepared.usage_limits,
            )

            # 4. Persist summary to chapter
            await self._chapter_repo.update_summary(chapter, result.summary)

            logger.info(
                "summary_generated",
                chapter_id=str(chapter_id),
                word_count=len(result.summary.split()),
            )

            return SummaryResult(
                summary=result.summary,
                word_count=result.word_count or len(result.summary.split()),
                key_points=result.key_points,
            )

        except NotFoundError:
            raise
        except Exception as exc:
            logger.error(
                "summary_generation_failed",
                chapter_id=str(chapter_id),
                error=str(exc),
                exc_info=True,
            )
            raise WritingError("Chapter summarization failed") from exc
