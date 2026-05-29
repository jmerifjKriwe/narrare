"""Wiki module protocol definitions. RULE-03: Contract before implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from narrare_core.wiki.types import (
        WikiChapterOutput,
        WikiEntityOutput,
        WikiGenerationDeps,
        WikiSummaryData,
    )


@runtime_checkable
class WikiServiceProtocol(Protocol):
    """Protocol for wiki orchestration. Single public API (RULE-12)."""

    async def generate_entity_summary(
        self,
        entity_id: str,
        novel_id: str,
        deps: WikiGenerationDeps | None = None,
    ) -> WikiEntityOutput | None:
        """Generate wiki summary for a KB entity. Graceful: returns None on failure."""
        ...

    async def get_summaries(
        self,
        entity_ids: list[str],
        novel_id: str,
    ) -> dict[str, WikiSummaryData]:
        """Batch lookup of fresh wiki summaries. Empty dict for stale/pending."""
        ...

    async def refresh_summary(
        self,
        entity_id: str,
        novel_id: str,
    ) -> WikiEntityOutput | None:
        """Force-regenerate regardless of current status."""
        ...

    async def mark_all_stale(
        self,
        novel_id: str,
        prompt_version: str | None = None,
    ) -> int:
        """Mark all novel's summaries stale. Published via EventBus."""
        ...


@runtime_checkable
class WikiAgentProtocol(Protocol):
    """Protocol for the wiki generation agent. Supports streaming (RULE-13)."""

    async def generate_entity(
        self,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
    ) -> WikiEntityOutput:
        """Generate entity wiki summary."""
        ...

    async def generate_chapter(
        self,
        deps: WikiGenerationDeps,
        *,
        stream: bool = False,
    ) -> WikiChapterOutput:
        """Generate chapter wiki summary."""
        ...
