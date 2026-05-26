"""Service for chapter summarization using ChapterSummaryAgent.

Orchestrates: get chapter content → compose prompt → instantiate agent → run → persist.
Dependencies are injected via __init__ (DI pattern, RULE-07).
All prompts come from PromptComposer (RULE-02).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.writing.summary_contracts import SummaryResult
from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps
from narrare_core.llm.intents import LLMIntent
from narrare_core.prompts.context import PromptContext
from narrare_core.shared.errors import NotFoundError, WritingError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.repository import ChapterRepository
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import ResolvedModelConfig
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
        _composer: PromptComposer for building system and user prompts.
        _api_key: Optional per-user API key override.
        _base_url: Optional per-user base URL override.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        chapter_repo: ChapterRepository,
        composer: PromptComposer,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize ChapterSummaryService with all dependencies.

        Args:
            registry: Model registry for LLM model instances.
            config: Resolved model config (provider, model, params).
            chapter_repo: Repository for loading/saving chapters.
            composer: PromptComposer for building prompts (RULE-02).
            api_key: Optional per-user API key override.
            base_url: Optional per-user base URL override.
        """
        self._registry = registry
        self._config = config
        self._chapter_repo = chapter_repo
        self._composer = composer
        self._api_key = api_key
        self._base_url = base_url

    async def summarize(
        self,
        chapter_id: UUID,
        max_sentences: int = 4,
        language: str = "en",
    ) -> SummaryResult:
        """Generate a summary for the given chapter and persist it.

        Args:
            chapter_id: The UUID of the chapter to summarize.
            max_sentences: Maximum number of sentences in the summary.
            language: Output language code.

        Returns:
            SummaryResult with summary text, word count, and key points.

        Raises:
            NotFoundError: If the chapter does not exist.
            WritingError: If the LLM call or persistence fails.
        """
        # 1. Load chapter
        chapter = await self._chapter_repo.get(chapter_id)
        if chapter is None:
            raise NotFoundError("Chapter", identifier=str(chapter_id))

        content = chapter.content
        if not content:
            logger.info("summary_skipped_empty", chapter_id=str(chapter_id))
            return SummaryResult(summary="", word_count=0)

        # 2. Compose prompt via PromptComposer (RULE-02)
        try:
            context = PromptContext(
                language=language,
                genre="",
                chapter_title=chapter.title,
                mode="summarize",
                extra={"max_sentences": str(max_sentences)},
            )
            composed = await self._composer.build(
                LLMIntent.SUMMARIZE,
                context,
                user_prompt=content[:3000],
            )

            # 3. Run the summary agent
            model = await self._registry.get_model(
                self._config,
                api_key=self._api_key,
                base_url=self._base_url,
            )
            agent = ChapterSummaryAgent(model=model, system_prompt=composed.system)

            deps = SummaryDeps(
                language=language,
                genre="",
                chapter_title=chapter.title,
                max_sentences=max_sentences,
            )

            result = await agent.run(prompt=composed.user, deps=deps)

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
