"""WikiService — orchestration layer for the LLM Wiki subsystem.

Implements WikiServiceProtocol with dependency injection for the agent
and event bus. Graceful degradation on all generation paths (RULE-11).

RULE-12: WikiService is the single public API for the wiki subsystem.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from narrare_core.events.bus import NullEventBus
from narrare_core.events.types import DomainEvent, EventType

if TYPE_CHECKING:
    from narrare_core.events.bus import EventBus
    from narrare_core.wiki.contracts import WikiAgentProtocol
    from narrare_core.wiki.types import (
        WikiEntityOutput,
        WikiGenerationDeps,
        WikiSummaryData,
    )

logger = structlog.get_logger(__name__)

# Maximum tokens for entity narrative_summary before truncation warning
_MAX_SUMMARY_TOKENS = 60


class WikiService:
    """Orchestrates wiki summary generation, retrieval, and refresh.

    Injected with dependencies rather than creating them (DI pattern).
    Graceful degradation: all generation failures return None (RULE-11).

    Usage:
        service = WikiService(agent=wiki_agent, event_bus=event_bus)
        result = await service.generate_entity_summary("entity-1", "novel-1")
    """

    def __init__(
        self,
        agent: WikiAgentProtocol,
        event_bus: EventBus | None = None,
    ) -> None:
        """Initialize the WikiService.

        Args:
            agent: Wiki generation agent (implements WikiAgentProtocol).
            event_bus: Event bus for publishing domain events.
                Defaults to NullEventBus when not provided.
        """
        self._agent = agent
        self._event_bus = event_bus or NullEventBus()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate_entity_summary(
        self,
        entity_id: str,
        novel_id: str,
        deps: WikiGenerationDeps | None = None,
    ) -> WikiEntityOutput | None:
        """Generate a wiki summary for a single KB entity.

        Graceful degradation: returns None if deps are missing or generation
        fails (RULE-11). The caller should fall back to raw KB data.

        Args:
            entity_id: The KB entity to summarize.
            novel_id: The parent novel / project.
            deps: Pre-built generation dependencies. Required for Phase 1.
                In Phase 2, the service will construct deps from available data.

        Returns:
            The generated entity summary, or None on failure.
        """
        if deps is None:
            logger.warning(
                "wiki_generate_skipped_no_deps",
                entity_id=entity_id,
                novel_id=novel_id,
            )
            return None

        try:
            result = await self._agent.generate_entity(deps=deps)
            self._check_token_limit(result, entity_id)
            logger.info(
                "wiki_entity_summary_generated",
                entity_id=entity_id,
                novel_id=novel_id,
                entity_type=deps.entity_type,
            )
            return result
        except Exception:
            logger.exception(
                "wiki_entity_summary_generation_failed",
                entity_id=entity_id,
                novel_id=novel_id,
            )
            return None

    async def get_summaries(
        self,
        entity_ids: list[str],
        novel_id: str,
    ) -> dict[str, WikiSummaryData]:
        """Batch lookup of wiki summaries.

        Phase 1 (core): Stub — returns empty dict. Real lookup via
        WikiRepository happens in the API layer (Phase 2).

        Args:
            entity_ids: The KB entities to look up.
            novel_id: The parent novel / project.

        Returns:
            Empty dict during Phase 1. In Phase 2, returns fresh summaries.
        """
        if not entity_ids:
            return {}

        logger.debug(
            "wiki_get_summaries_stub",
            entity_count=len(entity_ids),
            novel_id=novel_id,
            detail="Core layer stub — API layer WikiRepository handles lookup",
        )
        return {}

    async def refresh_summary(
        self,
        entity_id: str,
        novel_id: str,
    ) -> WikiEntityOutput | None:
        """Force-regenerate a wiki summary regardless of current status.

        Phase 1: Generates only when deps are provided externally (returns
        None otherwise). Phase 2 will fetch entity data automatically.

        Args:
            entity_id: The KB entity to refresh.
            novel_id: The parent novel / project.

        Returns:
            The regenerated entity summary, or None if deps unavailable.
        """
        logger.info(
            "wiki_refresh_summary",
            entity_id=entity_id,
            novel_id=novel_id,
            detail="Deps must be provided externally in Phase 1",
        )
        # Phase 1: caller must provide deps via generate_entity_summary
        # Phase 2: auto-fetch entity data from repository
        return None

    async def mark_all_stale(
        self,
        novel_id: str,
        prompt_version: str | None = None,
    ) -> int:
        """Mark all wiki summaries as stale for a novel.

        Publishes a WIKI_PROMPT_CHANGED event for the API layer to handle.
        The actual DB update (marking summaries as STALE) is done by
        listeners in the API layer.

        Args:
            novel_id: The novel whose summaries to mark stale.
            prompt_version: The new prompt version that caused the change.

        Returns:
            0 during Phase 1 (actual count handled by API layer).
        """
        event = DomainEvent(
            event_type=EventType.WIKI_PROMPT_CHANGED,
            aggregate_id=uuid.uuid4(),
            payload={
                "novel_id": novel_id,
                "prompt_version": prompt_version or "",
            },
        )
        await self._event_bus.publish(event)

        logger.info(
            "wiki_mark_all_stale_event_published",
            novel_id=novel_id,
            prompt_version=prompt_version,
        )
        return 0  # Actual count handled by API layer

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_token_limit(
        self,
        result: WikiEntityOutput,
        entity_id: str,
    ) -> None:
        """Check token limit and log warning if narrative_summary exceeds it.

        Uses word-count approximation (1 token ≈ 1 word) for simplicity.
        """
        # Rough token count: ~1.3 words per token, so 60 tokens ≈ 78 words
        word_count = len(result.narrative_summary.split())
        estimated_tokens = int(word_count / 1.3)
        if estimated_tokens > _MAX_SUMMARY_TOKENS:
            logger.warning(
                "wiki_summary_exceeds_token_limit",
                entity_id=entity_id,
                estimated_tokens=estimated_tokens,
                max_tokens=_MAX_SUMMARY_TOKENS,
                word_count=word_count,
                detail="Summary may exceed token budget — truncation recommended",
            )
