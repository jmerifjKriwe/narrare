"""Service for chapter summarization using ChapterSummaryAgent.

Orchestrates: get chapter content → instantiate agent → run → persist.
Dependencies are injected via __init__ (DI pattern, RULE-07).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.writing.summary_contracts import SummaryResult
from narrare_core.agents.summary_agent import ChapterSummaryAgent, SummaryDeps
from narrare_core.shared.errors import NotFoundError, WritingError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.repository import ChapterRepository
    from narrare_core.llm.gateway import ModelRegistry
    from narrare_core.llm.intents import ResolvedModelConfig

logger = structlog.get_logger(__name__)


class ChapterSummaryService:
    """Generates chapter summaries using ChapterSummaryAgent.

    Orchestrates loading chapter content from the repository,
    running the LLM-based summary agent, and persisting the result.

    Attributes:
        _registry: Model registry for getting configured LLM model instances.
        _config: Resolved model configuration (provider, model, params).
        _chapter_repo: Repository for chapter persistence.
        _api_key: Optional per-user API key override.
        _base_url: Optional per-user base URL override.
    """

    def __init__(
        self,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        chapter_repo: ChapterRepository,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        """Initialize ChapterSummaryService with all dependencies.

        Args:
            registry: Model registry for LLM model instances.
            config: Resolved model config (provider, model, params).
            chapter_repo: Repository for loading/saving chapters.
            api_key: Optional per-user API key override.
            base_url: Optional per-user base URL override.
        """
        self._registry = registry
        self._config = config
        self._chapter_repo = chapter_repo
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

        # 2. Run the summary agent
        try:
            model = await self._registry.get_model(
                self._config,
                api_key=self._api_key,
                base_url=self._base_url,
            )
            agent = ChapterSummaryAgent(model=model)

            deps = SummaryDeps(
                language=language,
                genre="",  # Genre would come from novel — future enhancement
                chapter_title=chapter.title,
                max_sentences=max_sentences,
            )

            # Build a concise prompt from the chapter content
            prompt = self._build_prompt(chapter.title, content, language)

            # narrare: allow-agent reason="ChapterSummaryAgent orchestrates lifecycle"
            result = await agent.run(prompt=prompt, deps=deps)

            # 3. Persist summary to chapter
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

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(title: str, content: str, language: str) -> str:
        """Build a summary prompt from chapter content.

        Args:
            title: The chapter title.
            content: The chapter content (will be truncated to 3000 chars).
            language: Output language code.

        Returns:
            A formatted prompt string.
        """
        truncated = content[:3000]
        return (
            f'Summarize the chapter titled "{title}".\n'
            f"Language: {language}\n\n"
            f"Content:\n{truncated}"
        )
