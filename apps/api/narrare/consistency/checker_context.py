"""Context collection for consistency checking — data gathering helper.

Extracted from ``checker_service.py`` for RULE-04 compliance (400-line limit).
Collects chapter content, KB summaries, timeline events, and builds
ConsistencyDeps for both staged and legacy paths.

See:
    :mod:`narrare.consistency.checker_service` — Service that calls this helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.consistency.checker_helpers import fetch_chapters, fetch_kb_summaries
from narrare.consistency.timeline_fetch import (
    fetch_timeline_event_envelopes,
    fetch_timeline_events,
)
from narrare_core.agents.consistency_types import ConsistencyCheckType, ConsistencyDeps
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    import uuid

    from narrare.chapters.repository import ChapterRepository
    from narrare.consistency.schemas import ConsistencyRequest
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.novels.repository import NovelRepository
    from narrare.planning.timeline_repository import TimelineEventRepository
    from narrare.settings.token_limits.contracts import TokenLimitsServiceProtocol
    from narrare_core.agents.consistency_types import ConsistencyIssue
    from narrare_core.agents.fact_extractor_types import TimelineEventEnvelope


class CheckContext:
    """Data bag holding collected context for a consistency check.

    Attributes:
        deps: ConsistencyDeps with chapter texts and configuration.
        kb_summaries: KB entity summaries for context.
        timeline_envelopes: Enriched timeline events with provenance.
        resolved_ids: Resolved chapter IDs from the fetch.
        language: Output language from novel settings.
        max_chapter_tokens: Token budget per chapter.
        rule_issues: Pre-computed rule-based issues.
    """

    __slots__ = (
        "deps",
        "kb_summaries",
        "language",
        "max_chapter_tokens",
        "resolved_ids",
        "rule_issues",
        "timeline_envelopes",
    )

    def __init__(
        self,
        *,
        deps: ConsistencyDeps,
        kb_summaries: list[dict[str, object]],
        timeline_envelopes: list[TimelineEventEnvelope],
        resolved_ids: list[uuid.UUID],
        language: str,
        max_chapter_tokens: int,
        rule_issues: list[ConsistencyIssue],
    ) -> None:
        self.deps = deps
        self.kb_summaries = kb_summaries
        self.timeline_envelopes = timeline_envelopes
        self.resolved_ids = resolved_ids
        self.language = language
        self.max_chapter_tokens = max_chapter_tokens
        self.rule_issues = rule_issues


async def collect_check_context(
    novel_id: uuid.UUID,
    user_id: uuid.UUID,
    request: ConsistencyRequest,
    *,
    chapter_repo: ChapterRepository,
    novel_repo: NovelRepository,
    kb_repo: KBRepository,
    relationship_repo: RelationshipRepository | None = None,
    timeline_repo: TimelineEventRepository,
    token_limits_service: TokenLimitsServiceProtocol | None = None,
    include_timeline_envelopes: bool = False,
) -> CheckContext:
    """Collect all data needed for a consistency check.

    Shared between staged and legacy paths. Validates access,
    fetches chapters, KB summaries, KB relationships, timeline data,
    and enriches timeline events with KB entity status.

    Args:
        novel_id: The novel to analyze.
        user_id: The user requesting analysis.
        request: Check parameters.
        chapter_repo: Chapter persistence layer.
        novel_repo: Novel persistence layer.
        kb_repo: KB persistence layer.
        relationship_repo: Optional relationship persistence layer. When
            provided and ``include_kb`` is set, KB relationships are
            fetched and formatted for relationship-aware consistency
            checking (FIND-001). When ``None``, relationships degrade
            gracefully to an empty string.
        timeline_repo: Timeline event persistence layer.
        token_limits_service: Optional TokenLimitsService.
        include_timeline_envelopes: Whether to fetch ADR-044 enriched envelopes.

    Returns:
        Collected context including deps, summaries, envelopes.

    Raises:
        NotFoundError: If novel or chapters don't exist.
    """
    from narrare.consistency.rule_helpers import rule_based_check

    # 1. Resolve token limits (with fallback to defaults)
    max_chapter_tokens = 2000
    max_kb_entries = 100
    if token_limits_service is not None:
        resolved = await token_limits_service.get_resolved_limits(
            str(user_id),
            str(novel_id),
        )
        max_chapter_tokens = resolved.max_chapter_tokens
        max_kb_entries = resolved.max_kb_entries

    # 2. Validate novel access
    novel = await novel_repo.get_by_id(novel_id, user_id)
    if novel is None:
        raise NotFoundError("Novel", identifier=str(novel_id))

    # 3. Fetch chapter content
    chapter_texts, resolved_ids = await fetch_chapters(
        chapter_repo,
        novel_id,
        request.chapter_ids,
    )
    if not chapter_texts:
        raise NotFoundError("Chapters", identifier=f"novel {novel_id}")

    # 4. Fetch KB entity summaries if requested
    kb_summaries: list[dict[str, object]] = []
    if request.include_kb:
        kb_summaries = await fetch_kb_summaries(
            kb_repo,
            novel_id,
            max_kb_entries=max_kb_entries,
        )

    # 4a. Fetch KB relationships for relationship-aware consistency (FIND-001).
    # Reuses the writing-pipeline helper; degrades to "" when no repo is wired
    # (graceful degradation) or when include_kb is False.
    kb_relationships_text = ""
    if request.include_kb and relationship_repo is not None:
        from narrare.writing._relationship_helpers import (
            fetch_formatted_relationships,
        )

        rel_context = await fetch_formatted_relationships(relationship_repo, novel_id)
        kb_relationships_text = rel_context.text

    # 4b. Fetch timeline events for temporal consistency context
    timeline_events = await fetch_timeline_events(timeline_repo, novel_id)

    # 4c. Build enriched timeline envelopes (ADR-044, FIND-009)
    timeline_envelopes: list[TimelineEventEnvelope] = []
    if include_timeline_envelopes:
        timeline_envelopes = await fetch_timeline_event_envelopes(
            timeline_repo,
            kb_repo,
            novel_id,
        )

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
        kb_relationships=kb_relationships_text,
    )

    return CheckContext(
        deps=deps,
        kb_summaries=kb_summaries,
        timeline_envelopes=timeline_envelopes,
        resolved_ids=resolved_ids,
        language=language,
        max_chapter_tokens=max_chapter_tokens,
        rule_issues=rule_issues,
    )
