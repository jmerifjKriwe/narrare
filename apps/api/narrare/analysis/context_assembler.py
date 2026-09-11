"""Context assembly for beta-reader analysis.

Gathers chapter text, previous chapter summaries, KB context (rendered through
the canonical :class:`~narrare.kb.context_contracts.KBContextProvider`), and
novel metadata into :class:`BetaReaderDeps` for the agent.

This module was migrated in W4b off the ad-hoc ``_fetch_kb_context`` dict path
onto the ADR-067 provider + ADR-050 envelope so provenance flows (FIND-017) and
the beta-reader sits on the unified render path. Decision β (boundary-rendered
text): the provider renders the envelope here at the service boundary and the
``.text`` slots are carried on ``BetaReaderDeps`` as ``str`` — the agent
consumes KB context as prompt text, never structurally.

Dependencies are injected: ``ChapterRepositoryProtocol``,
``KBContextProviderProtocol``, ``NovelRepositoryProtocol``. No direct DB access
here.

Ownership (IDOR remediation S12a): ``build_context`` requires the caller's
``user_id`` and gates novel ownership in Step 0 — a single user-scoped
``get_by_id`` lookup both authorizes the request AND supplies the genre/language
metadata, BEFORE any chapter or KB load. Foreign and unknown novels are
indistinguishable (``NotFoundError`` → 404); lookup failures propagate — the
previous degrade-to-defaults path silently masked foreign access (RULE-11).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare_core.agents.beta_reader_types import BetaReaderDeps
from narrare_core.context._render_options import RenderOptions
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.contracts import ChapterRepositoryProtocol
    from narrare.chapters.models import Chapter
    from narrare.kb.context_contracts import KBContextProviderProtocol
    from narrare.novels.contracts import NovelRepositoryProtocol

logger = structlog.get_logger(__name__)

#: Per-entity-type filter the beta reader reasons over. Wider slots
#: (factions/relationships) are not consumed by the current prompt; the
#: provider renders every requested type through the same envelope.
_BETA_READER_ENTITY_TYPES: list[str] = ["character", "location"]


class ContextAssembler:
    """Assembles context for beta reader analysis.

    Gathers chapter text, previous chapter summaries, KB context (characters
    and locations, rendered through the canonical KB-context provider) and
    novel genre into ``BetaReaderDeps``.

    Args:
        chapter_repo: Chapter repository for text retrieval.
        kb_context_provider: Canonical KB-context provider (ADR-067) — the
            single fetch+render source for the ``kb_characters`` /
            ``kb_locations`` slots, rendered through the ADR-050 envelope with
            ``RenderOptions(annotate_provenance=True)`` so provenance flows
            (FIND-017). When ``None`` or when the KB is empty, both slots
            degrade to empty strings (RULE-11) — the analysis still runs.
        novel_repo: Novel repository — the Step 0 user-scoped ownership
            gate AND the genre/language metadata source (IDOR S12a).
        max_previous_chapters: Maximum previous chapters to include summaries for.
        kb_summary_truncation: Maximum characters for the chapter-content
            fallback summary (used when a previous chapter has no stored
            summary).
    """

    def __init__(
        self,
        chapter_repo: ChapterRepositoryProtocol,
        kb_context_provider: KBContextProviderProtocol | None,
        novel_repo: NovelRepositoryProtocol,
        *,
        max_previous_chapters: int = 3,
        kb_summary_truncation: int = 200,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._kb_context_provider = kb_context_provider
        self._novel_repo = novel_repo
        self._max_previous_chapters = max_previous_chapters
        self._kb_summary_truncation = kb_summary_truncation

    async def build_context(
        self,
        novel_id: UUID,
        chapter_ids: list[UUID],
        user_id: UUID,
    ) -> BetaReaderDeps:
        """Assemble BetaReaderDeps from database.

        Steps:
          0. Ownership gate: user-scoped novel lookup (also the metadata
             source) — BEFORE any chapter/KB load (IDOR S12a)
          1. Fetch all chapters for the novel
          2. Identify target chapters (by IDs) and validate
          3. Fetch previous chapter summaries (up to 3)
          4. Fetch + render KB context through the canonical provider
          5. Build and return BetaReaderDeps

        Args:
            novel_id: The novel containing the chapters.
            chapter_ids: Specific chapters to analyze.
            user_id: The caller's identity — REQUIRED ownership gate input.

        Returns:
            Fully populated BetaReaderDeps ready for the agent.

        Raises:
            NotFoundError: The novel is unknown or owned by another user —
                both cases are indistinguishable by design (→ 404).
            ChapterNotFoundError: If any chapter_id is not found.
        """
        from narrare.analysis.errors import ChapterNotFoundError

        # Step 0: Ownership gate + metadata in ONE user-scoped lookup. This
        # replaces the former try/except-degrade in ``_fetch_novel_metadata``
        # (RULE-11: graceful degradation may never carry an authorization
        # decision) and runs BEFORE chapters or KB entities are loaded.
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))
        genre = novel.genre or ""
        language = novel.writing_language or "en"

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

        # Step 4: Fetch + render KB context through the canonical provider
        # (ADR-067). The provider never raises — an unavailable repository or
        # empty KB degrades to empty renderings (RULE-11).
        kb_characters, kb_locations = await self._fetch_kb_context(novel_id)

        # Step 5: Build BetaReaderDeps
        chapter_text = "\n\n---\n\n".join(c.content for c in target_chapters)
        chapter_titles = [c.title for c in target_chapters]
        word_count = sum(c.word_count for c in target_chapters)

        deps = BetaReaderDeps(
            language=language,
            chapter_text=chapter_text,
            chapter_titles=chapter_titles,
            word_count=word_count,
            previous_chapter_summaries=summaries,
            kb_characters=kb_characters,
            kb_locations=kb_locations,
            genre=genre,
        )

        logger.debug(
            "context_assembled",
            novel_id=str(novel_id),
            chapter_count=len(target_chapters),
            word_count=word_count,
            kb_characters_chars=len(kb_characters),
            kb_locations_chars=len(kb_locations),
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
    ) -> tuple[str, str]:
        """Fetch + render character and location context through the provider.

        Routes through :class:`KBContextProviderProtocol.fetch_context`
        (ADR-067) with ``RenderOptions(annotate_provenance=True)`` so
        provenance flows (FIND-017). The returned ``.text`` slots carry the
        rendered, provenance-honest prompt text. When no provider is wired or
        the KB is empty, both slots degrade to empty strings (RULE-11) — the
        provider never raises.

        Args:
            novel_id: The novel to fetch KB context for.

        Returns:
            Tuple of (characters_text, locations_text) — the rendered envelope
            ``.text`` for each slot.
        """
        from narrare.kb.context_contracts import KBContextBundle

        options = RenderOptions(annotate_provenance=True)
        if self._kb_context_provider is None:
            bundle = KBContextBundle.empty(options)
        else:
            bundle = await self._kb_context_provider.fetch_context(
                novel_id,
                entity_types=_BETA_READER_ENTITY_TYPES,
                options=options,
            )
        return bundle.characters.text, bundle.locations.text
