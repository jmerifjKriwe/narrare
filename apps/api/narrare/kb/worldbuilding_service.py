"""WorldbuildingService — business logic for worldbuilding analysis.

Orchestrates analysis (delegates to WorldbuildingAnalyzer) and
applies connection suggestions (creates KBRelationship entries).

See:
    :class:`narrare.kb.worldbuilding_contracts.WorldbuildingProtocol`
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

import structlog

from narrare.kb.models import KBRelationship
from narrare.kb.worldbuilding_contracts import (
    ConnectionSuggestion,
    WorldbuildingAnalysisRequest,
    WorldbuildingAnalysisResponse,
    WorldbuildingApplyRequest,
    WorldbuildingApplyResponse,
)

if TYPE_CHECKING:
    from narrare.kb.contracts import RelationshipRepositoryProtocol
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
    from narrare.kb.worldbuilding_cache import WorldbuildingCache

logger = structlog.get_logger(__name__)


class WorldbuildingService:
    """Business logic for worldbuilding analysis.

    Delegates LLM orchestration to :class:`WorldbuildingAnalyzer`.
    Handles ``apply_connections`` by creating ``KBRelationship`` entries
    for selected connection suggestions.
    """

    def __init__(
        self,
        analyzer: WorldbuildingAnalyzer,
        rel_repo: RelationshipRepositoryProtocol,
        cache: WorldbuildingCache,
    ) -> None:
        self._analyzer = analyzer
        self._rel_repo = rel_repo
        self._cache = cache

    async def analyze(
        self,
        *,
        novel_id: UUID,
        request: WorldbuildingAnalysisRequest,
    ) -> WorldbuildingAnalysisResponse:
        """Analyze the project's worldbuilding health.

        Delegates to :class:`WorldbuildingAnalyzer` which handles
        caching, deps assembly, and LLM orchestration.

        Args:
            novel_id: The project to analyze.
            request: Analysis options and filters.

        Returns:
            Complete analysis with all requested finding types.
        """
        logger.info("worldbuilding_analyze_start", novel_id=str(novel_id))
        return await self._analyzer.analyze(novel_id, request)

    async def apply_connections(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        request: WorldbuildingApplyRequest,
        analysis: WorldbuildingAnalysisResponse,
    ) -> WorldbuildingApplyResponse:
        """Apply selected connection suggestions as KB relationships.

        Looks up each ``finding_index`` in the analysis connection
        suggestions, checks for duplicates, and creates a
        ``KBRelationship`` entry.

        Args:
            novel_id: The project containing the entities.
            user_id: The user performing the action.
            request: Which connection indices to apply.
            analysis: The analysis response containing the suggestions.

        Returns:
            Result with counts of created/failed relationships.
        """
        created = 0
        failed = 0
        errors: list[str] = []

        for idx in request.finding_indices:
            suggestion = _find_suggestion(analysis.connection_suggestions, idx)
            if suggestion is None:
                failed += 1
                errors.append(f"Finding index {idx} not found or not a connection suggestion")
                continue

            try:
                source_id = UUID(suggestion.source_entity_id)
                target_id = UUID(suggestion.target_entity_id)

                # Check for duplicate
                exists = await self._rel_repo.exists(
                    source_id,
                    target_id,
                    suggestion.suggested_rel_type,
                )
                if exists:
                    failed += 1
                    errors.append(
                        f"Relationship already exists: "
                        f"{suggestion.source_entity_name} → {suggestion.target_entity_name}"
                    )
                    continue

                # Create the relationship
                rel = KBRelationship(
                    source_id=source_id,
                    target_id=target_id,
                    rel_type=suggestion.suggested_rel_type,
                    direction="directed",
                )
                await self._rel_repo.create(rel)
                created += 1
                logger.info(
                    "connection_applied",
                    idx=idx,
                    source=suggestion.source_entity_name,
                    target=suggestion.target_entity_name,
                    rel_type=suggestion.suggested_rel_type,
                )
            except Exception as exc:
                logger.error("apply_connection_failed", idx=idx, error=str(exc), exc_info=True)
                failed += 1
                errors.append(f"Failed to create relationship for index {idx}: {exc}")

        # Invalidate cache after successful applies
        if created > 0:
            await self._cache.delete_all(str(novel_id))

        return WorldbuildingApplyResponse(
            success=failed == 0,
            created_count=created,
            failed_count=failed,
            errors=errors,
        )


def _find_suggestion(
    suggestions: list[ConnectionSuggestion],
    idx: int,
) -> ConnectionSuggestion | None:
    """Find a connection suggestion by its ``finding_index``.

    Args:
        suggestions: The full list of connection suggestions.
        idx: The finding index to look up.

    Returns:
        The matching suggestion, or ``None`` if not found.
    """
    for s in suggestions:
        if s.finding_index == idx:
            return s
    return None
