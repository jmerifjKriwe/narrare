"""Generation analytics sub-service.

Handles ``get_stats`` aggregation.  Extracted from ``service.py``
for RULE-04 compliance (max 300 lines per file).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.writing.schemas import GenerationStatsResponse

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.writing.repository import GenerationRepository

logger = structlog.get_logger(__name__)


class StatsService:
    """Generation analytics logic.

    Dependencies are injected via constructor (DI pattern).
    """

    def __init__(self, repo: GenerationRepository) -> None:
        self._repo = repo

    async def get_stats(self, novel_id: UUID) -> GenerationStatsResponse:
        """Aggregate generation statistics for a novel.

        Delegates to the repository for raw aggregation and maps
        the result dict to a typed response schema.
        """
        stats = await self._repo.get_stats_for_novel(novel_id)

        return GenerationStatsResponse(
            total_generations=int(stats["total_generations"]),
            success_rate=float(stats["success_rate"]),
            avg_tokens=float(stats["avg_tokens"]),
            avg_word_count=float(stats["avg_word_count"]),
            most_used_model=stats.get("most_used_model"),
        )
