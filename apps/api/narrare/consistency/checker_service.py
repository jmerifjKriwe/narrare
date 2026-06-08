"""Consistency checker service — orchestrates consistency analysis.

Orchestrates: validate → collect content + KB + timeline → compose prompt
→ run ConsistencyAgent → map to API response. Follows BetaReaderService pattern.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from narrare.consistency.checker_helpers import fetch_chapters, fetch_kb_summaries
from narrare.consistency.prompt_builder import (
    compose_consistency_prompt,
)
from narrare.consistency.rule_helpers import deduplicate_issues, rule_based_check
from narrare.consistency.schemas import ConsistencyRequest, ConsistencyResponse
from narrare.consistency.timeline_fetch import fetch_timeline_events
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
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare_core.llm import ModelRegistry, ResolvedModelConfig
    from narrare_core.prompts import PromptComposer

logger = structlog.get_logger(__name__)


class ConsistencyCheckerService:
    """Implements ConsistencyCheckerProtocol.

    Orchestrates: validate → collect chapters + KB + timeline → build deps
    → run agent → map response.

    Args:
        chapter_repo: Chapter persistence (fetch chapter content).
        novel_repo: Novel persistence (access control + language).
        kb_repo: KB persistence (fetch entity summaries for context).
        timeline_repo: Timeline event persistence (temporal context).
        registry: ModelRegistry for LLM model resolution.
        config: Default ResolvedModelConfig for CONSISTENCY intent.
        composer: PromptComposer for system prompt assembly.
        token_limits_service: Optional TokenLimitsService for dynamic limit resolution.
    """

    def __init__(
        self,
        chapter_repo: ChapterRepository,
        novel_repo: NovelRepository,
        kb_repo: KBRepository,
        timeline_repo: TimelineEventRepository,
        registry: ModelRegistry,
        config: ResolvedModelConfig,
        composer: PromptComposer,
        token_limits_service: Any = None,
    ) -> None:
        self._chapter_repo = chapter_repo
        self._novel_repo = novel_repo
        self._kb_repo = kb_repo
        self._timeline_repo = timeline_repo
        self._registry = registry
        self._config = config
        self._composer = composer
        self._token_limits_service = token_limits_service

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

        # 1. Resolve token limits (with fallback to defaults)
        max_chapter_tokens = 2000
        max_kb_entries = 100
        if self._token_limits_service is not None:
            resolved = await self._token_limits_service.get_resolved_limits(
                str(user_id),
                str(novel_id),
            )
            max_chapter_tokens = resolved.max_chapter_tokens
            max_kb_entries = resolved.max_kb_entries

        # 2. Validate novel access
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

        # 3. Fetch chapter content
        chapter_texts, resolved_ids = await fetch_chapters(
            self._chapter_repo,
            novel_id,
            request.chapter_ids,
        )
        if not chapter_texts:
            raise NotFoundError("Chapters", identifier=f"novel {novel_id}")

        # 4. Fetch KB entity summaries if requested
        kb_summaries: list[dict[str, object]] = []
        if request.include_kb:
            kb_summaries = await fetch_kb_summaries(
                self._kb_repo,
                novel_id,
                max_kb_entries=max_kb_entries,
            )

        # 4b. Fetch timeline events for temporal consistency context
        timeline_events = await fetch_timeline_events(self._timeline_repo, novel_id)

        # 5. Rule-based pre-check (deterministic, no LLM needed)
        rule_issues = rule_based_check(kb_summaries)

        # 6. Resolve language and check types
        language = novel.writing_language or "en"
        check_types = request.check_types or list(ConsistencyCheckType)

        # 7. Build ConsistencyDeps
        deps = ConsistencyDeps(
            language=language,
            novel_id=str(novel_id),
            chapter_texts=chapter_texts,
            kb_entity_summaries=kb_summaries,
            timeline_events=timeline_events,
            check_types=check_types,
            existing_issue_count=len(rule_issues),
        )

        # 8. Compose prompt through PromptComposer.
        system_prompt, user_prompt = await compose_consistency_prompt(
            self._composer,
            language,
            deps,
            check_types,
            max_chapter_tokens=max_chapter_tokens,
        )

        # 9. Run ConsistencyAgent
        model = await self._registry.get_model(self._config)
        agent = ConsistencyAgent(model=model, system_prompt=system_prompt)
        result = await agent.run(prompt=user_prompt, deps=deps)

        # 10. Combine rule-based (confidence=1.0) + LLM issues, then deduplicate
        all_issues = rule_issues + result.issues
        deduped_issues = deduplicate_issues(all_issues)

        # 11. Map to response (severity counts auto-computed via model_post_init)
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

    async def _resolve_system_prompt(self, language: str) -> str:
        """Resolve the system prompt for the consistency agent.

        Uses the bundled prompt cascade. Locale fallback to English is handled
        by PromptRegistry — no production inline fallback needed.
        """
        from narrare_core.llm.intents import LLMIntent
        from narrare_core.prompts.context import PromptContext

        ctx = PromptContext(
            language=language,
            mode="consistency",
            project_title="",
        )
        composed = await self._composer.build(LLMIntent.CONSISTENCY, ctx)
        return composed.system
