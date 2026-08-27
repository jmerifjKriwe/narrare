"""KB Improve Service — orchestrates entry improvement with apply logic.

Coordinates KBImproveAnalyzer for LLM analysis and handles the apply
operation (field updates + relationship connections).  The analyzer is
extracted into ``improve_analyzer.py`` for RULE-04 compliance.

Both public operations gate on novel ownership at service entry (IDOR
fix S8): the caller must own ``novel_id`` and the entry must belong to
that novel BEFORE any cache lookup, LLM analysis, or write. The analyzer
itself stays gate-free (it runs post-gate only).
"""

from __future__ import annotations

import uuid as _uuid
from typing import TYPE_CHECKING

import structlog

from narrare_core.shared.errors import NotFoundError

from .improve_contracts import KBImproveAnalysisResponse, KBImproveApplyResponse

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.improve_analyzer import KBImproveAnalyzer
    from narrare.kb.models import KBEntry
    from narrare.kb.relationship_repository import RelationshipRepository
    from narrare.kb.repository import KBRepository
    from narrare.kb.service import KBService
    from narrare.novels.contracts import NovelRepositoryProtocol
    from narrare_core.ai_invocation.pipeline import InvocationPipeline

logger = structlog.get_logger(__name__)


class KBImproveService:
    """Orchestrates KBImproveAnalyzer for analyzing and improving KB entries.

    Delegates LLM analysis to :class:`KBImproveAnalyzer` and handles the
    apply operation (field updates + relationship connections) directly.

    Args:
        analyzer: LLM analysis orchestration (runs post-gate only).
        kb_repo: KB entry repository.
        kb_service: KB entry service (legacy wiring).
        rel_repo: Relationship repository.
        novel_repo: Novel repository — novel ownership gate (IDOR fix S8).
        invocation_pipeline: Optional invocation evidence pipeline.
    """

    def __init__(
        self,
        analyzer: KBImproveAnalyzer,
        kb_repo: KBRepository,
        kb_service: KBService,
        rel_repo: RelationshipRepository,
        novel_repo: NovelRepositoryProtocol,
        invocation_pipeline: InvocationPipeline | None = None,
    ) -> None:
        self._analyzer = analyzer
        self._kb_repo = kb_repo
        self._kb_service = kb_service
        self._rel_repo = rel_repo
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

    async def _get_owned_entry(self, novel_id: UUID, entry_id: UUID) -> KBEntry:
        """Load an entry and assert it belongs to the given novel.

        A foreign entry (belonging to another novel) and an unknown entry
        are indistinguishable — both raise ``NotFoundError``.
        """
        entry = await self._kb_repo.get_by_id(entry_id)
        if entry is None or entry.novel_id != novel_id:
            raise NotFoundError("KBEntry", identifier=str(entry_id))
        return entry

    async def analyze(
        self,
        *,
        novel_id: UUID,
        entry_id: UUID,
        user_id: UUID,
    ) -> KBImproveAnalysisResponse:
        """Analyze an existing KB entry and return improvement suggestions.

        Ownership gates run FIRST: the caller must own ``novel_id`` and the
        entry must belong to that novel — BEFORE any analyzer/LLM work, so
        a foreign entry's body never reaches the LLM.

        Delegates to :class:`KBImproveAnalyzer` which handles caching,
        deps building, prompt composition, and agent execution.
        Evidence recording happens in the analyzer (ADR-048 Mode 1).
        """
        await self._verify_novel_ownership(novel_id, user_id)
        await self._get_owned_entry(novel_id, entry_id)
        return await self._analyzer.analyze(novel_id=novel_id, entry_id=entry_id)

    async def apply(
        self,
        *,
        novel_id: UUID,
        entry_id: UUID,
        suggestion_ids: list[int],
        user_id: UUID,
    ) -> KBImproveApplyResponse:
        """Apply selected improvement suggestions.

        Ownership gates run FIRST — before the cache lookup (so a foreign
        caller cannot even probe the analysis cache), before any LLM
        fallback, and before any write.

        Uses the cached analysis when available (avoids re-running the LLM).
        On success, invalidates the cache so that subsequent analyses are fresh.
        Operates directly on repositories (internal tool).
        """
        await self._verify_novel_ownership(novel_id, user_id)
        entry = await self._get_owned_entry(novel_id, entry_id)

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
