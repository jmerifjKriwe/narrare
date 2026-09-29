"""Service for chapter summarization using ChapterSummaryAgent.

Orchestrates: get chapter content → resolve runtime at first use (ADR-086)
→ run the summary invocation → persist. Dependencies are injected via
__init__ (DI pattern, RULE-07). All prompts come from PromptComposer (RULE-02).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.writing._summary_invocation import run_summary_invocation
from narrare.writing.summary_contracts import SummaryResult
from narrare_core.llm.run_limits import DefaultRunLimitResolver
from narrare_core.shared.errors import NotFoundError, WritingError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare.novels.repository import NovelRepository
    from narrare.writing._summary_invocation import SummaryModelRuntime
    from narrare_core.ai_invocation.pipeline import InvocationPipeline
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.prompts.composer import PromptComposer

logger = structlog.get_logger(__name__)


class ChapterSummaryService:
    """Generates chapter summaries using ChapterSummaryAgent.

    Orchestrates loading chapter content from the repository, composing
    prompts via PromptComposer, resolving the model runtime at first use
    (ADR-086), running the summary agent, and persisting the result.

    Attributes:
        _registry: Model registry for getting configured LLM model instances.
        _runtime_factory: Deferred first-use composition (ADR-086 L38) —
            awaits BOTH cascades (routing + token limits) and freezes the
            effective ``SummaryModelRuntime``.
        _runtime: Cached first-use runtime (``None`` until
            :meth:`ensure_resolved` composes it).
        _chapter_repo: Repository for chapter persistence.
        _novel_repo: Repository for the novel ownership gate.
        _composer: PromptComposer for building system and user prompts.
        _invocation_pipeline: Optional InvocationPipeline for evidence recording.
        _kb_context_provider: Optional canonical KB-context provider (ADR-067)
            supplying the kb_characters / kb_locations / kb_factions /
            kb_relationships prompt variables.
        _run_limit_resolver: ADR-045 run-limit resolver over the frozen
            runtime config.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        runtime_factory: Callable[[], Awaitable[SummaryModelRuntime]],
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        composer: PromptComposer,
        *,
        invocation_pipeline: InvocationPipeline | None = None,
        kb_context_provider: KBContextProviderProtocol | None = None,
        run_limit_resolver: DefaultRunLimitResolver | None = None,
    ) -> None:
        """Initialize ChapterSummaryService with all dependencies.

        Args:
            registry: Model registry for LLM model instances.
            runtime_factory: Deferred composition (ADR-086 L38) returning
                the frozen first-use runtime — the effective model config
                (the SUMMARIZE routing cascade with the factory's sampling
                overlay) plus the verbatim per-user credentials. Invoked
                exactly once by :meth:`ensure_resolved`.
            chapter_repo: Repository for loading/saving chapters.
            novel_repo: Repository for the chapter→novel ownership gate.
            composer: PromptComposer for building prompts (RULE-02).
            invocation_pipeline: Optional InvocationPipeline for evidence recording.
            kb_context_provider: Optional canonical KB-context provider
                (ADR-067) for the kb_characters / kb_locations / kb_factions /
                kb_relationships prompt variables. ``None`` degrades to an
                empty bundle (RULE-11).
            run_limit_resolver: Optional ADR-045 run-limit resolver; defaults to
                ``DefaultRunLimitResolver`` (Task 3 wiring).
        """
        self._registry = registry
        self._runtime_factory = runtime_factory
        self._runtime: SummaryModelRuntime | None = None
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._composer = composer
        self._invocation_pipeline = invocation_pipeline
        self._kb_context_provider = kb_context_provider
        self._run_limit_resolver = run_limit_resolver or DefaultRunLimitResolver()

    async def ensure_resolved(self) -> SummaryModelRuntime:
        """Compose the effective summary runtime at first use; idempotent.

        Invokes the factory's deferred composition — the SUMMARIZE routing
        cascade AND the token-limits cascade (RULE-18/18b: sources
        unchanged, only timing moves) — exactly once; the frozen result is
        cached for the service's lifetime. Errors propagate uncached
        (RULE-11): ``ConfigurationError`` (``NO_AI_PROVIDER``) surfaces as
        a loud 400 on this REST endpoint.
        """
        if self._runtime is None:
            self._runtime = await self._runtime_factory()
        return self._runtime

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
        unknown, anti-enumeration). The ADR-086 first-use resolution runs
        directly after that gate (gate-before-resolution) and before the
        empty-content early return.

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
            ConfigurationError: If no AI provider is configured (resolved
                at first use, after the ownership gate — loud 400).
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

        # 3. First-use resolution (ADR-086 L38): BOTH cascades (routing +
        #    token limits) resolve here — after the ownership gate
        #    (gate-before-resolution) but BEFORE the empty-content early
        #    return and the generation try-wrapper, so an unconfigured
        #    provider stays a loud 400 even on the degradation path and is
        #    never wrapped into the 500-class WritingError (RULE-11).
        runtime = await self.ensure_resolved()

        content = chapter.content
        if not content:
            logger.info("summary_skipped_empty", chapter_id=str(chapter_id))
            return SummaryResult(summary="", word_count=0)

        try:
            output = await run_summary_invocation(
                run_limit_resolver=self._run_limit_resolver,
                runtime=runtime,
                registry=self._registry,
                composer=self._composer,
                invocation_pipeline=self._invocation_pipeline,
                kb_context_provider=self._kb_context_provider,
                chapter=chapter,
                max_sentences=max_sentences,
                language=language,
            )

            # 4. Persist summary to chapter
            await self._chapter_repo.update_summary(chapter, output.summary)

            logger.info(
                "summary_generated",
                chapter_id=str(chapter_id),
                word_count=len(output.summary.split()),
            )

            return SummaryResult(
                summary=output.summary,
                word_count=output.word_count or len(output.summary.split()),
                key_points=output.key_points,
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
