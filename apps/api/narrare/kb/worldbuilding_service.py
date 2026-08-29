"""WorldbuildingService — business logic for worldbuilding analysis.

Orchestrates analysis (delegates to WorldbuildingAnalyzer) and
applies connection suggestions (creates KBRelationship entries).

Both public operations gate on novel ownership at service entry (IDOR
fix S8): the caller must own ``novel_id`` BEFORE any analysis or
relationship write. ``apply_connections`` additionally validates every
referenced entry id against the gated novel in one batch ownership
query BEFORE any write (W2, S10 shape): the client-roundtripped
analysis payload is not trusted, and a single foreign/unknown entry id
rejects the whole batch — no partial writes.

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
from narrare_core.shared.errors import NotFoundError

if TYPE_CHECKING:
    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.kb.worldbuilding_analyzer import WorldbuildingAnalyzer
    from narrare.kb.worldbuilding_cache import WorldbuildingCache
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare_core.ai_invocation.pipeline import InvocationPipeline

logger = structlog.get_logger(__name__)


class WorldbuildingService:
    """Business logic for worldbuilding analysis.

    Delegates LLM orchestration to :class:`WorldbuildingAnalyzer`.
    Handles ``apply_connections`` by creating ``KBRelationship`` entries
    for selected connection suggestions.

    Args:
        analyzer: LLM analysis orchestration (runs post-gate only).
        rel_repo: Relationship repository.
        entry_repo: KB entry repository — batch entry∈novel probe (W2).
        cache: Worldbuilding analysis cache.
        novel_repo: Novel repository — novel ownership gate (IDOR fix S8).
        invocation_pipeline: Optional invocation evidence pipeline.
    """

    def __init__(
        self,
        analyzer: WorldbuildingAnalyzer,
        rel_repo: RelationshipRepositoryProtocol,
        entry_repo: KBRepositoryProtocol,
        cache: WorldbuildingCache,
        novel_repo: NovelRepositoryProtocol,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._analyzer = analyzer
        self._rel_repo = rel_repo
        self._entry_repo = entry_repo
        self._cache = cache
        self._novel_repo = novel_repo
        self._invocation_pipeline = invocation_pipeline

    async def _verify_novel_ownership(self, novel_id: UUID, user_id: UUID) -> None:
        """Raise NotFoundError if the novel is not owned by the caller.

        Foreign and unknown novels are indistinguishable (anti-enumeration);
        a missing novel is a 404, never a 403 (which stays reserved for the
        series module).
        """
        novel = await self._novel_repo.get_by_id(novel_id, user_id)
        if novel is None:
            raise NotFoundError("Novel", identifier=str(novel_id))

    async def analyze(
        self,
        *,
        novel_id: UUID,
        request: WorldbuildingAnalysisRequest,
        user_id: UUID,
    ) -> WorldbuildingAnalysisResponse:
        """Analyze the project's worldbuilding health.

        Ownership gate runs FIRST: the caller must own ``novel_id`` before
        any analyzer/LLM work or cache read.

        Args:
            novel_id: The project to analyze.
            request: Analysis options and filters.
            user_id: The caller — must own the novel (ownership gate).

        Returns:
            Complete analysis with all requested finding types.
        """
        await self._verify_novel_ownership(novel_id, user_id)

        logger.info("worldbuilding_analyze_start", novel_id=str(novel_id))

        # Evidence recording has moved to WorldbuildingAnalyzer (ADR-048 Mode 1).
        # The analyzer records per-phase evidence closer to the actual LLM calls.
        return await self._analyzer.analyze(novel_id, request)

    async def _verify_entries_in_novel(
        self,
        novel_id: UUID,
        suggestions: list[ConnectionSuggestion],
        finding_indices: list[int],
    ) -> None:
        """Raise NotFoundError if a referenced entry is not in ``novel_id``.

        Batch data-integrity check (W2, S10 error shape): every entry id
        the apply batch is about to write must belong to the gated novel —
        the client-roundtripped analysis payload is not trusted. One batch
        ownership query runs BEFORE any duplicate check or write; a single
        foreign/unknown id rejects the whole batch (no partial writes).
        Foreign ≡ unknown (anti-enumeration): both are ``NotFoundError``.
        Malformed uuid strings are skipped here — they keep their per-item
        error in the apply loop below.
        """
        referenced: list[UUID] = []
        seen: set[UUID] = set()
        for idx in finding_indices:
            suggestion = _find_suggestion(suggestions, idx)
            if suggestion is None:
                continue
            for raw_id in (suggestion.source_entity_id, suggestion.target_entity_id):
                try:
                    entry_id = UUID(raw_id)
                except ValueError:
                    continue
                if entry_id not in seen:
                    seen.add(entry_id)
                    referenced.append(entry_id)

        if not referenced:
            return

        owned = await self._entry_repo.filter_ids_in_novel(novel_id, seen)
        for entry_id in referenced:
            if entry_id not in owned:
                raise NotFoundError("KBEntry", identifier=str(entry_id))

    async def apply_connections(
        self,
        *,
        novel_id: UUID,
        user_id: UUID,
        request: WorldbuildingApplyRequest,
        analysis: WorldbuildingAnalysisResponse,
    ) -> WorldbuildingApplyResponse:
        """Apply selected connection suggestions as KB relationships.

        Ownership gate runs FIRST: the caller must own ``novel_id`` before
        any duplicate check or relationship write. Entry∈novel validation
        (W2) runs second, batched over the whole selection: a single
        foreign/unknown entry id rejects the whole request — no partial
        writes.

        Looks up each ``finding_index`` in the analysis connection
        suggestions, checks for duplicates, and creates a
        ``KBRelationship`` entry.

        Args:
            novel_id: The project containing the entities.
            user_id: The caller — must own the novel (ownership gate).
            request: Which connection indices to apply.
            analysis: The analysis response containing the suggestions.

        Returns:
            Result with counts of created/failed relationships.

        Raises:
            NotFoundError: Novel unknown/foreign (gate), or a referenced
                entry not found or not in the novel (batch probe).
        """
        await self._verify_novel_ownership(novel_id, user_id)
        await self._verify_entries_in_novel(
            novel_id,
            analysis.connection_suggestions,
            request.finding_indices,
        )

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
