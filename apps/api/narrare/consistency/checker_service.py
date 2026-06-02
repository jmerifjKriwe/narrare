"""Consistency checker service — orchestrates consistency analysis.

Orchestrates: validate → collect chapter content + KB data → compose prompt
→ run ConsistencyAgent → map to API response.

Follows the same pattern as BetaReaderService.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import structlog

from narrare.consistency.prompt_builder import (
    MAX_KB_ENTRIES,
    build_user_prompt,
    get_system_prompt,
)
from narrare.consistency.rule_helpers import deduplicate_issues, rule_based_check
from narrare.consistency.schemas import ConsistencyRequest, ConsistencyResponse
from narrare_core.agents.consistency_agent import ConsistencyAgent
from narrare_core.agents.consistency_types import (
    ConsistencyCheckType,
    ConsistencyDeps,
)
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.repository import ChapterRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.prompts import PromptComposer

logger = structlog.get_logger(__name__)


class ConsistencyCheckerService:
    """Implements ConsistencyCheckerProtocol.

    Orchestrates the consistency checking pipeline:
      validate → collect chapters + KB → build deps → run agent → map response.

    Args:
        chapter_repo: Chapter persistence (fetch chapter content).
        novel_repo: Novel persistence (access control + language).
        kb_repo: KB persistence (fetch entity summaries for context).
        registry: ModelRegistry for LLM model resolution.
        config: Default ResolvedModelConfig for CONSISTENCY intent.
        composer: PromptComposer for system prompt assembly.
    """

    def __init__(
        self,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        kb_repo: KBRepository,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        composer: PromptComposer,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._kb_repo = kb_repo
        self._registry = registry
        self._config = config
        self._composer = composer

    async def check(
        self,
        *,
        novel_id: uuid.UUID,
        user_id: uuid.UUID,
        request: ConsistencyRequest,
    ) -> ConsistencyResponse:
        """Run consistency check on the requested scope.

        Cross-chapter and cross-entity consistency analysis. Compares facts
        extracted from chapter prose against KB entity data and across
        chapters. Returns issues grouped by severity and type.

        Args:
            novel_id: The novel to analyze.
            user_id: The user requesting analysis (for access control).
            request: Check parameters (check types, chapter scope, KB inclusion).

        Returns:
            Consistency response with issues grouped by severity and type,
            including error/warning/info counts and overall assessment.

        Raises:
            NotFoundError: If novel does not exist or user lacks access.
        """
        logger.info(
            "consistency_check_start",
            novel_id=str(novel_id),
            chapter_count=len(request.chapter_ids),
            include_kb=request.include_kb,
        )

        # 1. Validate novel access
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        # 2. Fetch chapter content
        chapter_texts, resolved_ids = await self._fetch_chapters(
            novel_id,
            request.chapter_ids,
        )
        if not chapter_texts:
            raise NotFoundError("Chapters", identifier=f"novel {novel_id}")

        # 3. Fetch KB entity summaries if requested
        kb_summaries: list[dict[str, object]] = []
        if request.include_kb:
            kb_summaries = await self._fetch_kb_summaries(novel_id)

        # 4. Rule-based pre-check (deterministic, no LLM needed)
        rule_issues = rule_based_check(kb_summaries)

        # 5. Resolve language and check types
        language = novel.writing_language or "en"
        check_types = request.check_types or list(ConsistencyCheckType)

        # 6. Build ConsistencyDeps
        deps = ConsistencyDeps(
            language=language,
            novel_id=str(novel_id),
            chapter_texts=chapter_texts,
            kb_entity_summaries=kb_summaries,
            check_types=check_types,
            existing_issue_count=len(rule_issues),
        )

        # 7. Compose system prompt (PromptComposer with inline fallback)
        system_prompt = await self._resolve_system_prompt(language)

        # 8. Run ConsistencyAgent
        model = await self._registry.get_model(self._config)
        agent = ConsistencyAgent(model=model, system_prompt=system_prompt)
        user_prompt = build_user_prompt(deps, check_types)
        result = await agent.run(prompt=user_prompt, deps=deps)

        # 9. Combine rule-based (confidence=1.0) + LLM issues, then deduplicate
        all_issues = rule_issues + result.issues
        deduped_issues = deduplicate_issues(all_issues)

        # 10. Map to response (severity counts auto-computed via model_post_init)
        now = datetime.now(tz=UTC).isoformat()
        response = ConsistencyResponse(
            novel_id=novel_id,
            chapter_ids=resolved_ids,
            check_types=result.checked_types,
            issues=deduped_issues,
            overall_assessment=result.overall_assessment,
            analyzed_at=now,
        )

        logger.info(
            "consistency_check_complete",
            novel_id=str(novel_id),
            issue_count=response.total_issues,
            error_count=response.error_count,
            warning_count=response.warning_count,
        )

        return response

    async def check_chapter(
        self,
        *,
        novel_id: uuid.UUID,
        chapter_id: uuid.UUID,
        user_id: uuid.UUID,
        request: ConsistencyRequest,
    ) -> ConsistencyResponse:
        """Run consistency check focused on a single chapter.

        Delegates to ``check()`` with the chapter_id injected into a
        scoped request. Useful for targeted checking after a writing session.

        Args:
            novel_id: The novel containing the chapter.
            chapter_id: The chapter to analyze.
            user_id: The user requesting analysis (for access control).
            request: Check parameters (check types, KB inclusion).

        Returns:
            Consistency response scoped to the single chapter.

        Raises:
            NotFoundError: If novel or chapter does not exist.
        """
        scoped_request = ConsistencyRequest(
            chapter_ids=[chapter_id],
            check_types=request.check_types,
            include_kb=request.include_kb,
        )
        return await self.check(
            novel_id=novel_id,
            user_id=user_id,
            request=scoped_request,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_chapters(
        self,
        novel_id: uuid.UUID,
        chapter_ids: list[uuid.UUID],
    ) -> tuple[dict[str, str], list[uuid.UUID]]:
        """Fetch chapter content from repository.

        If *chapter_ids* is empty, fetches ALL chapters for the novel
        (all-chapters fallback for comprehensive checking).

        Returns:
            Tuple of (chapter_texts mapping, resolved chapter ID list).
            Returns empty dict and empty list if no chapters found.

        Raises:
            NotFoundError: If any specifically requested chapter_id is missing.
        """
        if not chapter_ids:
            chapters = await self._chapter_repo.list_by_novel(novel_id)
            if not chapters:
                return {}, []
            texts = {str(ch.id): ch.content or "" for ch in chapters}
            ids = [ch.id for ch in chapters]
            return texts, ids

        texts: dict[str, str] = {}
        ids: list[uuid.UUID] = []
        for cid in chapter_ids:
            chapter = await self._chapter_repo.get_by_id(cid, novel_id)
            if chapter is None:
                raise NotFoundError("Chapter", identifier=str(cid))
            texts[str(cid)] = chapter.content or ""
            ids.append(cid)
        return texts, ids

    async def _fetch_kb_summaries(
        self,
        novel_id: uuid.UUID,
    ) -> list[dict[str, object]]:
        """Build simplified KB entity summaries for agent context.

        Returns:
            List of dicts with ``entity_type``, ``name``, and ``fields`` keys.
            Empty list if no KB entries exist.
        """
        entries, _total = await self._kb_repo.list_entries(
            novel_id,
            page_size=MAX_KB_ENTRIES,
        )
        summaries: list[dict[str, object]] = []
        for entry in entries:
            summaries.append(
                {
                    "entity_type": entry.entity_type,
                    "name": entry.name,
                    "fields": entry.metadata_ or {},
                }
            )
        return summaries

    async def _resolve_system_prompt(self, language: str) -> str:
        """Resolve the system prompt for the consistency agent.

        Attempts PromptComposer first (production path). Falls back to
        the inline prompt if no bundled prompt exists for this intent yet.
        """
        try:
            from narrare_core.llm.intents import LLMIntent
            from narrare_core.prompts.context import PromptContext

            ctx = PromptContext(
                language=language,
                mode="consistency",
                project_title="",
            )
            composed = await self._composer.build(LLMIntent.CONSISTENCY, ctx)
            return composed.system
        except Exception:
            logger.debug(
                "consistency_using_inline_prompt",
                language=language,
            )
            return get_system_prompt()
