"""Endorse/reject service for the KB entity resolution layer (ADR-085 P4).

Turns a stateless suggestion identity into a merge (endorse) or a
dismissal (reject), per spec §7. One responsibility: the adjudication
lifecycle — detection stays in ``analysis_service.py``, merge semantics
in ``merge_executor.py`` (RULE-06).

Endorse re-validation is stateless (binding note / ADR-085 Implementation
Notes): a 16-char suggestion id cannot be parsed back into its entry
pair, so the service re-runs the detection scoring fresh
(``analyze(refresh=True)`` — never a cache read) and finds the
suggestion whose id matches. A missing id covers every non-endorseable
state at once — stale (entries changed), rejected (the dismissal ledger
filters the served analysis), or below the REVIEW band (suppressed pairs
are never surfaced) — and yields ``409 Conflict`` with that reason.

When the endorse body omits ``survivor_id``, the §6.1 deterministic pick
runs here: both entries are loaded (novel-scope validated,
anti-enumeration), relationship counts are resolved, and
``select_survivor`` receives the pair in ``(min_id, max_id)`` order so
the outcome is caller-independent. The re-scored pair confidence is
carried into the ``MergePlan`` (executor audit block). Executor
``ValueError`` maps to ``ValidationError`` (→ 422 at the HTTP seam) and
``NotFoundError`` propagates (→ 404 via the global handler). A
successful merge invalidates the analysis cache so the next analysis
never serves a pre-merge result.

Reject persists the dismissal via the injected
``DismissedSuggestionStoreProtocol`` (existing fingerprint pattern,
``resolution:`` namespace) and leaves the analysis cache untouched —
rejected pairs are filtered from served lists at the analysis read seam.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.kb.entity_resolution.merge_executor import select_survivor
from narrare.kb.entity_resolution.schemas_resolution import MergePlan
from narrare_core.shared.errors import ConflictError, NotFoundError, ValidationError

if TYPE_CHECKING:
    from uuid import UUID

    from narrare.kb.contracts import KBRepositoryProtocol, RelationshipRepositoryProtocol
    from narrare.kb.entity_resolution.contracts import (
        DismissedSuggestionStoreProtocol,
        MergeExecutorProtocol,
        ResolutionAnalyzerProtocol,
    )
    from narrare.kb.entity_resolution.schemas_resolution import (
        MergeExecutionResult,
        SuggestionResponse,
    )
    from narrare.kb.models import KBEntry

logger = structlog.get_logger(__name__)


class ResolutionEndorseService:
    """Adjudication lifecycle: endorse (merge) or reject (dismiss) a pair.

    Dependencies are injected (RULE-19): the analysis service (fresh
    re-validation + cache invalidation), the merge executor, the KB and
    relationship repositories (survivor-selection inputs), and the
    dismissal ledger.
    """

    def __init__(
        self,
        analyzer: ResolutionAnalyzerProtocol,
        executor: MergeExecutorProtocol,
        kb_repo: KBRepositoryProtocol,
        rel_repo: RelationshipRepositoryProtocol,
        dismissals: DismissedSuggestionStoreProtocol,
    ) -> None:
        self._analyzer = analyzer
        self._executor = executor
        self._kb_repo = kb_repo
        self._rel_repo = rel_repo
        self._dismissals = dismissals

    async def endorse(
        self,
        novel_id: UUID,
        user_id: UUID,
        suggestion_id: str,
        *,
        survivor_id: UUID | None = None,
    ) -> MergeExecutionResult:
        """Re-validate the suggestion, execute the merge, invalidate the cache.

        Args:
            novel_id: Novel scope of both entries.
            user_id: Authenticated user endorsing (audit log).
            suggestion_id: Stateless suggestion identity (spec §7).
            survivor_id: Optional §6.1 override; must name one of the two
                suggested entries.

        Returns:
            The merge outcome (or the idempotent replay, §6.6).

        Raises:
            ConflictError: The suggestion is absent from the fresh
                re-score — stale, rejected, or below the REVIEW band.
            ValidationError: Override outside the suggested pair, or a
                degenerate plan rejected by the executor (→ 422).
            NotFoundError: A pair entry is missing or out of scope (→ 404).
        """
        analysis = await self._analyzer.analyze(novel_id, user_id, refresh=True)
        suggestion = next(
            (s for s in analysis.suggestions if s.suggestion_id == suggestion_id), None
        )
        if suggestion is None:
            raise ConflictError(
                f"Suggestion {suggestion_id} failed re-validation: stale, rejected, "
                "or below the review band — re-run the analysis"
            )
        if survivor_id is not None and survivor_id not in (
            suggestion.entry_a_id,
            suggestion.entry_b_id,
        ):
            raise ValidationError("survivor_id override is not part of the suggested pair")
        if survivor_id is None:
            survivor_id = await self._auto_survivor(novel_id, suggestion)
        loser_id = (
            suggestion.entry_b_id if survivor_id == suggestion.entry_a_id else suggestion.entry_a_id
        )
        plan = MergePlan(
            survivor_id=survivor_id,
            loser_id=loser_id,
            suggestion_id=suggestion_id,
            confidence=suggestion.confidence,
        )
        try:
            result = await self._executor.execute(novel_id, user_id, plan)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        await self._analyzer.invalidate(novel_id)
        logger.info(
            "resolution_suggestion_endorsed",
            novel_id=str(novel_id),
            user_id=str(user_id),
            suggestion_id=suggestion_id,
            survivor_id=str(survivor_id),
            loser_id=str(loser_id),
        )
        return result

    async def reject(self, novel_id: UUID, user_id: UUID, suggestion_id: str) -> None:
        """Persist the dismissal (existing pattern); the analysis cache stays.

        Idempotent: re-rejecting the same pair refreshes the ledger row.
        Rejected pairs disappear from served suggestion lists at the
        analysis read seam and can no longer be endorsed (re-validation
        runs over the filtered analysis).
        """
        await self._dismissals.dismiss(novel_id, suggestion_id)
        logger.info(
            "resolution_suggestion_rejected",
            novel_id=str(novel_id),
            user_id=str(user_id),
            suggestion_id=suggestion_id,
        )

    async def _auto_survivor(self, novel_id: UUID, suggestion: SuggestionResponse) -> UUID:
        """Resolve the §6.1 deterministic survivor for the suggested pair.

        ``select_survivor`` receives the pair in suggestion order —
        ``entry_a``/``entry_b`` are min/max by UUID — so a total rank tie
        resolves caller-independently to the min id.
        """
        entry_a = await self._load_scoped(novel_id, suggestion.entry_a_id)
        entry_b = await self._load_scoped(novel_id, suggestion.entry_b_id)
        counts = {
            entry_a.id: len(await self._rel_repo.list_for_entry(entry_a.id)),
            entry_b.id: len(await self._rel_repo.list_for_entry(entry_b.id)),
        }
        return select_survivor(entry_a, entry_b, counts)

    async def _load_scoped(self, novel_id: UUID, entry_id: UUID) -> KBEntry:
        """Fetch an entry that must exist inside ``novel_id`` (anti-enumeration).

        Mirrors the executor's scoped load: foreign-novel or missing
        entries are not-found, never a scope leak.
        """
        entry = await self._kb_repo.get_by_id(entry_id)
        if entry is None or entry.novel_id != novel_id:
            raise NotFoundError("KBEntry", identifier=str(entry_id))
        return entry
