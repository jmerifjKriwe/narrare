"""Resolution analysis service for the KB entity resolution layer (ADR-085 P3).

Orchestrates the detection pass (spec §7): snapshots (via the injected
builder) are fed through the pure ``ResolutionEngine`` and mapped to
banded suggestions with per-signal evidence. ``SUPPRESSED`` pairs are
counted and info-logged (RULE-11 — never silently dropped) but never
surfaced. Suggestion identity is stateless (``sha256(min ‖ max)[:16]``
over the entry-id strings) so endorsements can be re-validated later
without a suggestion table.

Rejection ledger (P4, spec §7): an optional injected
``DismissedSuggestionStoreProtocol`` filters REJECTED suggestions from
every SERVED analysis (``analyze`` and ``get_cached``) and recounts the
review/auto-eligible stats. The cache payload stays unfiltered — the
ledger applies at read time, so a rejection also covers results cached
before it. A missing ledger (``dismissed=None``, e.g. in unit fakes) is
a passthrough.

Uncertain-band annotation (P5, spec §2/D7): an optional injected
``UncertainBandAdjudicatorProtocol`` annotates REVIEW-band suggestions
with LLM verdict notes before the payload is cached. Only the uncertain
band reaches the adjudicator — AUTO_ELIGIBLE and SUPPRESSED pairs never
do (spec §8: detection stays LLM-free) — and a cache hit serves the
stored notes without re-invoking it. A missing adjudicator
(``adjudicator=None``) keeps the analysis fully deterministic.

Caching mirrors the ``kb/consistency_cache.py`` pattern — injected
``SessionCacheProtocol`` backend, 10-minute TTL, novel-scoped key,
tolerant reads; the cache and the entries-hash derivation live in the
sibling ``analysis_cache`` module (RULE-04 splits: the dismissal filter
landed in P4, the hash followed the envelope in P5).
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

import structlog

from narrare.kb.entity_resolution.adjudicator import annotate_review_band
from narrare.kb.entity_resolution.analysis_cache import compute_entries_hash
from narrare.kb.entity_resolution.schemas_resolution import (
    BandStats,
    ResolutionAnalysisResponse,
    SignalEvidence,
    SuggestionResponse,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from uuid import UUID

    from narrare.kb.entity_resolution.analysis_cache import ResolutionAnalysisCache
    from narrare.kb.entity_resolution.contracts import (
        DismissedSuggestionStoreProtocol,
        SnapshotBuilderProtocol,
        UncertainBandAdjudicatorProtocol,
    )
    from narrare.kb.entity_resolution.schemas_resolution import SuggestionBand
    from narrare_core.kb.resolution.models import PairScore
    from narrare_core.kb.resolution.scoring import ResolutionEngine

logger = structlog.get_logger(__name__)


class ResolutionAnalysisService:
    """Detection pass: snapshots → engine → banded suggestions (+ cache).

    Implements :class:`~narrare.kb.entity_resolution.contracts.ResolutionAnalyzerProtocol`.
    Dependencies are injected (RULE-19): the snapshot builder, the pure
    scoring engine, the analysis cache, the optional rejection ledger, and
    the optional uncertain-band adjudicator. Stateless w.r.t. suggestion
    identity — the same entry pair always yields the same suggestion id.
    """

    def __init__(
        self,
        builder: SnapshotBuilderProtocol,
        engine: ResolutionEngine,
        cache: ResolutionAnalysisCache,
        dismissed: DismissedSuggestionStoreProtocol | None = None,
        adjudicator: UncertainBandAdjudicatorProtocol | None = None,
    ) -> None:
        self._builder = builder
        self._engine = engine
        self._cache = cache
        self._dismissed = dismissed
        self._adjudicator = adjudicator

    async def analyze(
        self,
        novel_id: UUID,
        user_id: UUID,
        *,
        refresh: bool = False,
    ) -> ResolutionAnalysisResponse:
        """Run (or fetch) the duplicate detection analysis for one novel.

        Args:
            novel_id: The novel scope to analyze.
            user_id: Authenticated user triggering the analysis (audit log).
            refresh: Skip the cache read and force a recompute.

        Returns:
            The surfaced suggestions (minus rejected ones, REVIEW pairs
            annotated when an adjudicator is wired), per-band stats
            recounted over the kept suggestions, and cache status.
        """
        novel_str = str(novel_id)
        snapshots = await self._builder.build(novel_id)
        entries_hash = compute_entries_hash(snapshots)

        if not refresh:
            cached = await self._cache.get(novel_str, entries_hash)
            if cached is not None:
                response = ResolutionAnalysisResponse.model_validate_json(cached)
                return await self._apply_dismissals(
                    response.model_copy(update={"cache_hit": True}), novel_id
                )

        names: Mapping[UUID, str] = {s.entry_id: s.name for s in snapshots}
        suggestions: list[SuggestionResponse] = []
        review = auto_eligible = suppressed = 0
        for a, b in self._engine.find_candidates(snapshots):
            score = self._engine.score_pair(a, b)
            band = score.band
            if band == "SUPPRESSED":
                suppressed += 1
                logger.info(
                    "resolution_pair_suppressed",
                    novel_id=novel_str,
                    entry_a_id=str(score.entry_a_id),
                    entry_b_id=str(score.entry_b_id),
                    confidence=score.confidence,
                    vetoes=list(score.vetoes),
                )
                continue
            suggestions.append(self._to_suggestion(score, names, band))
            if band == "AUTO_ELIGIBLE":
                auto_eligible += 1
            else:
                review += 1

        # Uncertain-band annotation (P5, spec §2): only REVIEW pairs reach
        # the adjudicator; AUTO/SUPPRESSED stay deterministic (spec §8).
        # Notes are part of the cached payload, so cache hits never
        # re-invoke the LLM.
        if self._adjudicator is not None:
            suggestions = await annotate_review_band(
                suggestions,
                adjudicator=self._adjudicator,
                novel_id=novel_id,
                user_id=user_id,
                entity_types={s.entry_id: s.entity_type for s in snapshots},
            )

        response = ResolutionAnalysisResponse(
            suggestions=suggestions,
            stats=BandStats(review=review, auto_eligible=auto_eligible, suppressed=suppressed),
            cache_hit=False,
        )
        await self._cache.set(novel_str, response.model_dump_json(), entries_hash)
        logger.info(
            "resolution_analysis_complete",
            novel_id=novel_str,
            user_id=str(user_id),
            suggestions=len(suggestions),
            review=review,
            auto_eligible=auto_eligible,
            suppressed=suppressed,
        )
        return await self._apply_dismissals(response, novel_id)

    async def get_cached(self, novel_id: UUID) -> ResolutionAnalysisResponse:
        """Return the cached analysis WITHOUT recomputing (spec §7 GET suggestions).

        The cache payload is validated against the current entries hash, so
        reading it requires building snapshots — a read-only KB fetch, not a
        detection recompute (the engine never runs here). A miss (never
        analyzed, invalidated, or stale after a KB mutation) yields the empty
        response with ``cache_hit=False`` — the endpoint is 404-free (§7).
        """
        snapshots = await self._builder.build(novel_id)
        cached = await self._cache.get(str(novel_id), compute_entries_hash(snapshots))
        if cached is None:
            return ResolutionAnalysisResponse(
                suggestions=[],
                stats=BandStats(review=0, auto_eligible=0, suppressed=0),
                cache_hit=False,
            )
        response = ResolutionAnalysisResponse.model_validate_json(cached)
        return await self._apply_dismissals(
            response.model_copy(update={"cache_hit": True}), novel_id
        )

    async def _apply_dismissals(
        self,
        response: ResolutionAnalysisResponse,
        novel_id: UUID,
    ) -> ResolutionAnalysisResponse:
        """Drop rejected suggestions from a SERVED analysis (spec §7 reject).

        The cache payload stays unfiltered (rejections apply retroactively
        to results cached before them); ``review``/``auto_eligible`` are
        recounted over the kept suggestions while ``suppressed`` stays
        detection-truth. A missing ledger (``dismissed=None``) and an
        empty ledger are passthroughs.
        """
        if self._dismissed is None:
            return response
        rejected = await self._dismissed.rejected_ids(novel_id)
        if not rejected:
            return response
        kept = [s for s in response.suggestions if s.suggestion_id not in rejected]
        if len(kept) == len(response.suggestions):
            return response
        logger.info(
            "resolution_suggestions_dismissal_filtered",
            novel_id=str(novel_id),
            dropped=len(response.suggestions) - len(kept),
        )
        return response.model_copy(
            update={
                "suggestions": kept,
                "stats": BandStats(
                    review=sum(1 for s in kept if s.band == "REVIEW"),
                    auto_eligible=sum(1 for s in kept if s.band == "AUTO_ELIGIBLE"),
                    suppressed=response.stats.suppressed,
                ),
            }
        )

    async def invalidate(self, novel_id: UUID) -> None:
        """Drop the cached analysis for a novel.

        KB-mutation flows call this in later tasks so the next analysis
        never serves a pre-mutation result (spec §7 invalidation clause).
        """
        await self._cache.delete_all(str(novel_id))

    @staticmethod
    def _to_suggestion(
        score: PairScore,
        names: Mapping[UUID, str],
        band: SuggestionBand,
    ) -> SuggestionResponse:
        """Map one non-suppressed ``PairScore`` to its response schema.

        ``band`` is passed pre-narrowed (``SUPPRESSED`` never reaches this
        mapper — the caller filters and counts those pairs first).
        """
        id_a, id_b = str(score.entry_a_id), str(score.entry_b_id)
        lo, hi = min(id_a, id_b), max(id_a, id_b)
        return SuggestionResponse(
            suggestion_id=hashlib.sha256(f"{lo}{hi}".encode()).hexdigest()[:16],
            entry_a_id=score.entry_a_id,
            entry_b_id=score.entry_b_id,
            name_a=names[score.entry_a_id],
            name_b=names[score.entry_b_id],
            confidence=score.confidence,
            band=band,
            auto_merge_eligible=band == "AUTO_ELIGIBLE",
            signals=[
                SignalEvidence(signal=s.signal, value=s.value, veto=s.veto, detail=s.detail)
                for s in score.signals
            ],
        )
