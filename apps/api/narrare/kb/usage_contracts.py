"""Context usage tracking contract — Protocol definition.

Extracted from contracts.py per RULE-04 (file size limit).
Contracts are written before implementation (RULE-03).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    import uuid


@runtime_checkable
class ContextUsageProtocol(Protocol):
    """Protocol for tracking context suggestion usage.

    Records accept/dismiss events and maintains usage counters
    on KB entries for hybrid search scoring.
    """

    async def record_accept(
        self,
        novel_id: uuid.UUID,
        entry_id: uuid.UUID,
        chapter_id: uuid.UUID | None,
        source: str,
    ) -> None:
        """Record a suggestion acceptance and update usage counters."""
        ...

    async def record_dismiss(
        self,
        novel_id: uuid.UUID,
        entry_id: uuid.UUID,
        chapter_id: uuid.UUID | None,
        source: str,
    ) -> None:
        """Record a suggestion dismissal (no usage counter update)."""
        ...

    async def get_usage_stats(self, entry_id: uuid.UUID) -> dict[str, int]:
        """Return accept/dismiss counts for an entry."""
        ...
