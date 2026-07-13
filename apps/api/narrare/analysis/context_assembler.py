"""Context assembly for analysis features.

Gathers chapter text, previous chapter summaries, KB entries, and novel
metadata into BetaReaderDeps for the agent.

Dependencies are injected: ChapterRepositoryProtocol, KBRepositoryProtocol,
NovelRepositoryProtocol. No direct DB access here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.agents.beta_reader_types import BetaReaderDeps

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.chapters.models import Chapter
    from narrare.kb.contracts import KBRepositoryProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol

logger = structlog.get_logger(__name__)


class ContextAssembler:
    """Assembles context for beta reader analysis.

    Gathers chapter text, previous chapter summaries, KB entries
    (characters and locations), and novel genre into BetaReaderDeps.

    Args:
        chapter_repo: Chapter repository for text retrieval.
        kb_repo: KB repository for character/location lookup.
        novel_repo: Novel repository for genre metadata.
        max_previous_chapters: Maximum previous chapters to include summaries for.
        kb_summary_truncation: Maximum characters for the chapter-content
            fallback summary (used when a previous chapter has no stored
            summary). KB entity bodies are passed through in full for
            downstream token-budget truncation.
    """

    def __init__(
        self,
        chapter_repo: ChapterRepositoryProtocol,
        kb_repo: KBRepositoryProtocol,
        novel_repo: NovelRepositoryProtocol,
        *,
        max_previous_chapters: int = 3,
        kb_summary_truncation: int = 200,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._kb_repo = kb_repo
        self._novel_repo = novel_repo
        self._max_previous_chapters = max_previous_chapters
        self._kb_summary_truncation = kb_summary_truncation

    async def build_context(
        self,
        novel_id: UUID,
        chapter_ids: list[UUID],
        user_id: UUID | None = None,
    ) -> BetaReaderDeps:
        """Assemble BetaReaderDeps from database.

        Steps:
          1. Fetch all chapters for the novel
          2. Identify target chapters (by IDs) and validate
          3. Fetch previous chapter summaries (up to 3)
          4. Fetch KB entries (characters, locations)
          5. Fetch novel metadata (genre + language)
          6. Build and return BetaReaderDeps

        Args:
            novel_id: The novel containing the chapters.
            chapter_ids: Specific chapters to analyze.
            user_id: Optional user ID for authorization checks.

        Returns:
            Fully populated BetaReaderDeps ready for the agent.

        Raises:
            ChapterNotFoundError: If any chapter_id is not found.
        """
        from narrare.analysis.errors import ChapterNotFoundError

        # Step 1: Fetch all chapters for the novel
        all_chapters = await self._chapter_repo.list_by_novel(novel_id)

        # Step 2: Identify target chapters
        chapter_map: dict[UUID, Chapter] = {c.id: c for c in all_chapters}
        target_chapters: list[Chapter] = []
        for cid in chapter_ids:
            chapter = chapter_map.get(cid)
            if chapter is None:
                raise ChapterNotFoundError(f"Chapter {cid} not found in novel {novel_id}")
            target_chapters.append(chapter)

        # Step 3: Fetch previous chapter summaries
        summaries = self._extract_previous_summaries(all_chapters, target_chapters)

        # Step 4: Fetch KB context
        characters, locations = await self._fetch_kb_context(novel_id)

        # Step 5: Fetch novel metadata (genre + language)
        genre, language = await self._fetch_novel_metadata(novel_id, user_id)

        # Step 6: Build BetaReaderDeps
        chapter_text = "\n\n---\n\n".join(c.content for c in target_chapters)
        chapter_titles = [c.title for c in target_chapters]
        word_count = sum(c.word_count for c in target_chapters)

        deps = BetaReaderDeps(
            language=language,
            chapter_text=chapter_text,
            chapter_titles=chapter_titles,
            word_count=word_count,
            previous_chapter_summaries=summaries,
            kb_characters=characters,
            kb_locations=locations,
            genre=genre,
        )

        logger.debug(
            "context_assembled",
            novel_id=str(novel_id),
            chapter_count=len(target_chapters),
            word_count=word_count,
            kb_characters=len(characters),
            kb_locations=len(locations),
        )

        return deps

    def _extract_previous_summaries(
        self,
        all_chapters: list[Chapter],
        target_chapters: list[Chapter],
    ) -> list[str]:
        """Get summaries of up to 3 chapters before the targets.

        Args:
            all_chapters: All chapters in the novel.
            target_chapters: The chapters being analyzed.

        Returns:
            List of summary strings from previous chapters.
        """
        if not target_chapters or not all_chapters:
            return []

        # Find minimum position of target chapters
        min_position = min(c.position for c in target_chapters)

        # Get chapters with lower position
        previous = [c for c in all_chapters if c.position < min_position]

        # Sort by position descending, take up to 3 most recent
        previous.sort(key=lambda c: c.position, reverse=True)
        previous = previous[: self._max_previous_chapters]

        summaries: list[str] = []
        for c in previous:
            summary = c.summary or ""
            if not summary:
                # Fall back to first 200 chars of content
                content = c.content or ""
                summary = content[: self._kb_summary_truncation]
            if summary:
                summaries.append(summary)

        return summaries

    async def _fetch_kb_context(
        self,
        novel_id: UUID,
    ) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
        """Fetch character and location entries from KB.

        Args:
            novel_id: The novel to fetch KB entries for.

        Returns:
            Tuple of (characters, locations) as short dicts with
            name, type, and summary fields.
        """
        try:
            entries, _ = await self._kb_repo.list_entries(
                novel_id,
                page_size=200,  # Fetch all relevant entries
            )
        except Exception:
            logger.warning("kb_context_fetch_failed", novel_id=str(novel_id))
            return [], []

        characters: list[dict[str, str]] = []
        locations: list[dict[str, str]] = []

        for entry in entries:
            entity_type = entry.entity_type
            name = entry.name
            body = entry.body or ""
            # Pass full body to the budget assembler — it makes the token-aware
            # truncation decision downstream (AnalysisContextAssembler in
            # build_budgeted_prompt). Pre-truncating here would starve the
            # budget system of data it could otherwise fit.
            summary = body

            item: dict[str, str] = {
                "name": name,
                "type": entity_type,
                "summary": summary,
            }

            if entity_type == "character":
                characters.append(item)
            elif entity_type == "location":
                locations.append(item)

        return characters, locations

    async def _fetch_novel_metadata(
        self, novel_id: UUID, user_id: UUID | None = None
    ) -> tuple[str, str]:
        """Fetch genre and language from novel metadata.

        Returns both fields in a single DB call to avoid fetching the novel
        twice for different metadata attributes.

        Args:
            novel_id: The novel to look up.
            user_id: Optional user ID for authorization.

        Returns:
            Tuple of (genre, language). Either defaults to empty string / "en"
            if the novel is not found or an error occurs.
        """
        try:
            if user_id is not None:
                novel = await self._novel_repo.get_by_id(novel_id, user_id)
            else:
                # Fallback: system-level access without ownership check
                novel = await self._novel_repo.get(novel_id)
            if novel is not None:
                genre = novel.genre or ""
                language = getattr(novel, "writing_language", "en") or "en"
                return genre, language
        except Exception:
            logger.warning("novel_metadata_fetch_failed", novel_id=str(novel_id))
        return "", "en"
