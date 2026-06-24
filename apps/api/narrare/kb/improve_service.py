"""KB Improve Service — orchestrates entry improvement with apply logic.

Coordinates KBImproveAnalyzer for LLM analysis and handles the apply
operation (field updates + relationship connections).  The analyzer is
extracted into ``improve_analyzer.py`` for RULE-04 compliance.
"""

from __future__ import annotations

import uuid as _uuid
from typing import TYPE_CHECKING

import structlog

from .improve_contracts import KBImproveAnalysisResponse, KBImproveApplyResponse

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.improve_analyzer import KBImproveAnalyzer
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService
    from narrare_core.ai_invocation.pipeline import InvocationPipeline

logger = structlog.get_logger(__name__)


class KBImproveService:
    """Orchestrates KBImproveAnalyzer for analyzing and improving KB entries.

    Delegates LLM analysis to :class:`KBImproveAnalyzer` and handles the
    apply operation (field updates + relationship connections) directly.
    """

    def __init__(
        self,
        analyzer: KBImproveAnalyzer,
        kb_repo: KBRepository,
        kb_service: KBService,
        rel_repo: RelationshipRepository,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._analyzer = analyzer
        self._kb_repo = kb_repo
        self._kb_service = kb_service
        self._rel_repo = rel_repo
        self._invocation_pipeline = invocation_pipeline

    async def analyze(
        self,
        *,
        novel_id: UUID,
        entry_id: UUID,
    ) -> KBImproveAnalysisResponse:
        """Analyze an existing KB entry and return improvement suggestions.

        Delegates to :class:`KBImproveAnalyzer` which handles caching,
        deps building, prompt composition, and agent execution.
        Evidence recording happens in the analyzer (ADR-048 Mode 1).
        """
        return await self._analyzer.analyze(novel_id=novel_id, entry_id=entry_id)

    async def apply(
        self,
        *,
        novel_id: UUID,
        entry_id: UUID,
        suggestion_ids: list[int],
    ) -> KBImproveApplyResponse:
        """Apply selected improvement suggestions.

        Uses the cached analysis when available (avoids re-running the LLM).
        On success, invalidates the cache so that subsequent analyses are fresh.
        Operates directly on repositories (internal tool).
        """
        # Try to get analysis from cache first — avoids re-running the LLM
        analysis = await self._analyzer.get_cached_analysis(entry_id)

        # Fall back to running analysis (legacy path)
        if analysis is None:
            analysis = await self._analyzer.analyze(novel_id=novel_id, entry_id=entry_id)

        selected = [s for s in analysis.suggestions if s.suggestion_id in suggestion_ids]

        if not selected:
            return KBImproveApplyResponse(
                success=False,
                entry_id=str(entry_id),
                applied_count=0,
                message="No valid suggestions selected.",
            )

        entry = await self._kb_repo.get_by_id(entry_id)
        if entry is None:
            from narrare_core.shared.errors import NotFoundError

            raise NotFoundError("KBEntry", identifier=str(entry_id))

        # Apply field changes (add_field, expand, reorganize)
        metadata_updates: dict[str, object] = {}
        for suggestion in selected:
            if (
                suggestion.type in ("add_field", "expand", "reorganize")
                and suggestion.proposed_content is not None
            ):
                metadata_updates[suggestion.target] = suggestion.proposed_content

        update_data: dict[str, object] = {}
        if metadata_updates:
            current_metadata = dict(entry.metadata_ or {})
            current_metadata.update(metadata_updates)
            update_data["metadata_"] = current_metadata

        if update_data:
            await self._kb_repo.update(entry, update_data)

        # Apply relationship connections (connect suggestions)
        connect_count = 0
        for suggestion in selected:
            if suggestion.type == "connect" and suggestion.related_entity_id:
                try:
                    from narrare.kb.models import KBRelationship

                    target_id = _uuid.UUID(suggestion.related_entity_id)
                    rel = KBRelationship(
                        source_id=entry_id,
                        target_id=target_id,
                        rel_type="related_to",
                        direction="directed",
                    )
                    await self._rel_repo.create(rel)
                    connect_count += 1
                except Exception:
                    logger.warning(
                        "relationship_creation_failed",
                        entry_id=str(entry_id),
                        related_id=suggestion.related_entity_id,
                        exc_info=True,
                    )

        total_applied = len(selected)

        # On success, invalidate cached analysis so next call is fresh
        await self._analyzer.invalidate_cache(entry_id)

        return KBImproveApplyResponse(
            success=True,
            entry_id=str(entry_id),
            applied_count=total_applied,
            message=str(total_applied)
            + " improvement(s) applied ("
            + str(connect_count)
            + " new connection(s)).",
        )
