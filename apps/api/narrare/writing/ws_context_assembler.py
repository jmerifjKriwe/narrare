"""WS writing-turn context assembler — data-fetching production wiring.

FO-4: ``WritingTurnService`` (2d7b822a) accepts an optional
``WritingContextAssembler`` but production DI wired ``None`` — every
WebSocket turn composed KB-blind. The core
:class:`~narrare_core.writing.context_assembler.WritingContextAssembler`
is a *pure data transformation* (no I/O — the API layer supplies all
data), so a bare core instance would still assemble an empty context.
This subclass supplies the data: it fetches the turn's chapter, novel
metadata, recent-chapter context, structured KB entities (ADR-067
canonical provider + mapper), and rendered relationships per turn, then
delegates tier organization and token budgeting to the core transformer.

Session handling follows the WS-handshake precedent
(``ws_session_config``): a short-lived session is acquired per assemble
call — a WebSocket connection has no request-scoped session.

RULE-11 graceful: missing chapter/novel rows degrade to empty tier-1 /
empty metadata (the handshake ownership gate already ran); the KB
provider never raises; a relationship-fetch failure degrades to an
empty block; repository-level failures propagate to the turn service's
``ws_turn_context_assembly_failed`` KB-blind fallback (never raised
from *wiring* — construction needs no session or app state).

See: ADR-067, CONSTRAINTS.md RULE-04/06/07/11.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import RecentChapter

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.chapters.models import Chapter
    from narrare.kb.relationship_repository import RelationshipEdgeRow
    from narrare.novels.models import Novel
    from narrare_core.writing.context_models import KBEntity
    from narrare_core.writing.models import WritingContext

logger = structlog.get_logger(__name__)

#: Recent chapters fed into Tier 2 (mirrors the analysis assembler's
#: ``max_previous_chapters=3`` precedent).
_MAX_RECENT_CHAPTERS = 3


class WsWritingContextAssembler(WritingContextAssembler):
    """Data-fetching assembler for WebSocket writing turns.

    Subclasses the core pure transformer so it satisfies the
    ``WritingTurnService`` ``context_assembler`` annotation unchanged
    (RULE-03: no contract change). ``assemble`` fetches the turn-scoped
    data and delegates budgeting/organization to :meth:`super`.

    Args:
        tier_overrides: Optional per-tier percentage overrides forwarded
            to the core :class:`TokenBudgetManager`. ``None`` (default)
            keeps the mode-specific allocations. Production wiring
            sources this from the handshake's resolved
            ``TokenLimitsService.get_resolved_limits().tier_percentages``
            (FIND-012, threaded by ``ws_factory`` — item E).
        total_budget: Optional total input-context budget (ADR-082).
            ``None`` (default) keeps the Core default. Production wiring
            passes the model-capped ``writing_tier_base`` resolved at
            handler build via ``resolve_context_budgets`` (threaded by
            ``ws_factory`` — item E).
    """

    def __init__(
        self,
        *,
        tier_overrides: dict[str, float] | None = None,
        total_budget: int | None = None,
    ) -> None:
        if total_budget is None:
            super().__init__(tier_overrides=tier_overrides)
        else:
            super().__init__(total_budget=total_budget, tier_overrides=tier_overrides)

    async def assemble(
        self,
        *,
        chapter_id: UUID,
        project_id: UUID | None = None,
        mode: str | None = None,
        **kwargs: Any,
    ) -> WritingContext:
        """Fetch the turn's data and assemble the WritingContext.

        Args:
            chapter_id: The chapter the session is writing (supplied by
                ``WritingTurnService._assemble_writing_context``).
            project_id: The novel/project scope. ``None`` (base-contract
                default, never passed by the turn service) skips the
                project-scoped fetches — tier-1 only (RULE-11).
            mode: Prompt mode (``interactive_session`` / ``interview``)
                — forwarded so budget allocation can prioritise
                immediate context.
            **kwargs: Forwarded verbatim to the core assembler.

        Returns:
            The assembled :class:`WritingContext` for the turn.
        """
        from narrare._app.database import get_async_session
        from narrare.chapters.repository import ChapterRepository
        from narrare.kb._context_provider import (
            KBContextProvider,
            kb_entry_to_kb_entity,
        )
        from narrare.kb.relationship_repository import RelationshipRepository
        from narrare.kb.repository import KBRepository
        from narrare.novels.repository import NovelRepository
        from narrare_core.writing._relationship_format import format_relationships

        session_gen = get_async_session()
        session = await session_gen.__anext__()
        try:
            chapter = await ChapterRepository(session).get(chapter_id)
            chapters: list[Chapter] = []
            novel: Novel | None = None
            kb_entities: list[KBEntity] = []
            edges: list[RelationshipEdgeRow] = []
            if project_id is not None:
                chapter_repo = ChapterRepository(session)
                chapters = await chapter_repo.list_by_novel(project_id)
                novel = await NovelRepository(session).get(project_id)
                relationship_repo = RelationshipRepository(session)
                provider = KBContextProvider(
                    kb_repo=KBRepository(session),
                    relationship_repo=relationship_repo,
                )
                kb_entities = [
                    kb_entry_to_kb_entity(entry)
                    for entry in await provider.fetch_entities(project_id)
                ]
                try:
                    edges = await relationship_repo.get_relationships_with_names(
                        novel_id=project_id,
                    )
                except Exception:
                    logger.warning("ws_turn_relationships_fetch_failed", exc_info=True)
                    edges = []
        finally:
            await session_gen.aclose()

        return await super().assemble(
            chapter_content=chapter.content if chapter is not None else "",
            timeline_position=chapter.timeline_position if chapter is not None else "",
            recent_chapters=self._recent_chapters(chapters, current=chapter),
            kb_entities=kb_entities,
            kb_relationships=format_relationships(edges).text,
            project_title=novel.title if novel is not None else "",
            genre=novel.genre if novel is not None else "",
            writing_language=novel.writing_language if novel is not None else "",
            tone=novel.tone if novel is not None and novel.tone else "balanced",
            story_structure=novel.story_structure if novel is not None else "",
            series_id=novel.series_id if novel is not None else None,
            project_id=project_id,
            mode=mode,
            **kwargs,
        )

    @staticmethod
    def _recent_chapters(
        chapters: list[Chapter],
        *,
        current: Chapter | None,
    ) -> list[RecentChapter]:
        """Build the Tier-2 recent list: chapters *before* the current one.

        Future chapters (higher position) are excluded so a mid-novel
        session never leaks not-yet-written prose. A missing current
        chapter yields an empty list (RULE-11 graceful).
        """
        if current is None:
            return []
        previous = [c for c in chapters if c.position < current.position]
        previous.sort(key=lambda c: c.position, reverse=True)
        return [
            RecentChapter(
                chapter_id=c.id,
                title=c.title,
                full_text=c.content,
                summary=c.summary,
                position=c.position,
            )
            for c in previous[:_MAX_RECENT_CHAPTERS]
        ]
