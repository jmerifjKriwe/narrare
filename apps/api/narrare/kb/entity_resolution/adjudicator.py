"""Uncertain-band adjudicator — LLM annotation over KBMergeService (ADR-085 P5).

Two cooperating halves of the uncertain-band feature (spec §2/D7):

- :class:`UncertainBandAdjudicator` implements
  :class:`~narrare.kb.entity_resolution.contracts.UncertainBandAdjudicatorProtocol`
  as an adapter over the EXISTING ``KBMergeService``: uncertain-band pairs
  are converted to ``MergeRequest`` candidate pairs, adjudicated through
  the Mode-1 governed merge prompt (ADR-054; RULE-02b — NO new prompt
  surface), and mapped back to per-pair verdicts. The merge service —
  including per-user model-routing resolution — is built lazily via an
  injected factory, so callers stay config-free until a pair actually
  needs adjudication (ADR-085 inert by default).
- :func:`annotate_review_band` applies the verdicts to a detection
  result: REVIEW-band suggestions are converted to candidates, submitted,
  and their notes written back. AUTO_ELIGIBLE and SUPPRESSED pairs never
  reach the adjudicator (spec §8 — detection metrics stay LLM-free).

Failure policy (RULE-11): per-pair agent failures — and factory
failures — are logged and degrade to ``supports_merge=False`` with a
failure note; the analysis never crashes. Invocation evidence rides the
existing pipeline (RULE-22): ``KBMergeService`` already composes through
``compose_invocation``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from narrare.kb.entity_resolution.schemas_adjudication import Adjudication, PairCandidate
from narrare.kb.schemas_merge import MergeRequest

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence
    from uuid import UUID

    from narrare.kb.entity_resolution.contracts import UncertainBandAdjudicatorProtocol
    from narrare.kb.entity_resolution.schemas_resolution import SuggestionResponse
    from narrare.kb.merge_contracts import KBMergeServiceProtocol

logger = structlog.get_logger(__name__)

type MergeServiceFactory = Callable[[UUID, UUID], Awaitable[KBMergeServiceProtocol]]
"""Lazy per-request ``KBMergeService`` source: ``(novel_id, user_id) → service``.

A factory — not a service instance — keeps model-routing resolution (and
everything it costs) off requests that never adjudicate.
"""


class UncertainBandAdjudicator:
    """Adapts the resolution layer's uncertain band to ``KBMergeService``.

    Dependency is injected (RULE-19): an async factory producing the
    existing merge service per request. One governed merge call runs per
    pair — failure isolation (one broken pair degrades alone, RULE-11)
    and independence from the agent echoing pair ids back.
    """

    def __init__(self, merge_service_factory: MergeServiceFactory) -> None:
        self._merge_service_factory = merge_service_factory

    async def adjudicate(
        self,
        novel_id: UUID,
        user_id: UUID,
        pairs: Sequence[PairCandidate],
    ) -> Sequence[Adjudication]:
        """Adjudicate each pair through the governed merge analysis.

        An empty pair list never builds the merge service (no factory
        call, no routing resolution, no LLM).
        """
        if not pairs:
            return []
        try:
            merge_service = await self._merge_service_factory(novel_id, user_id)
        except Exception as exc:
            logger.warning(
                "resolution_adjudication_failed",
                novel_id=str(novel_id),
                pair_count=len(pairs),
                error=str(exc),
            )
            return [
                Adjudication(
                    pair_key=pair.pair_key,
                    supports_merge=False,
                    note=f"Adjudication unavailable: {exc}",
                )
                for pair in pairs
            ]
        return [
            await self._adjudicate_one(merge_service, novel_id, user_id, pair) for pair in pairs
        ]

    async def _adjudicate_one(
        self,
        merge_service: KBMergeServiceProtocol,
        novel_id: UUID,
        user_id: UUID,
        pair: PairCandidate,
    ) -> Adjudication:
        """Run one governed merge analysis and map its decision to a verdict."""
        request = MergeRequest(
            entity_type=pair.entity_type,
            candidate_pairs=[{"entity_1": pair.name_a, "entity_2": pair.name_b}],
        )
        try:
            response = await merge_service.analyze_merge_candidates(novel_id, user_id, request)
        except Exception as exc:
            logger.warning(
                "resolution_adjudication_failed",
                novel_id=str(novel_id),
                pair_key=pair.pair_key,
                error=str(exc),
            )
            return Adjudication(
                pair_key=pair.pair_key,
                supports_merge=False,
                note=f"Adjudication unavailable: {exc}",
            )
        decision = response.merge_decisions[0] if response.merge_decisions else None
        if decision is None:
            logger.warning(
                "resolution_adjudication_empty",
                novel_id=str(novel_id),
                pair_key=pair.pair_key,
            )
            return Adjudication(
                pair_key=pair.pair_key,
                supports_merge=False,
                note="Adjudication returned no decision.",
            )
        supports = decision.decision.strip().lower() == "merge"
        note = (
            f"LLM adjudication — {decision.decision} "
            f"(confidence {decision.confidence:.2f}): {decision.reasoning}"
        )
        return Adjudication(pair_key=pair.pair_key, supports_merge=supports, note=note)


async def annotate_review_band(
    suggestions: list[SuggestionResponse],
    *,
    adjudicator: UncertainBandAdjudicatorProtocol,
    novel_id: UUID,
    user_id: UUID,
    entity_types: Mapping[UUID, str],
) -> list[SuggestionResponse]:
    """Return ``suggestions`` with REVIEW-band adjudication notes applied.

    A no-op (same list, no adjudicator call) when no REVIEW-band
    suggestion is present — the LLM runs only for the uncertain band
    (spec §2/§8). Adjudications whose ``pair_key`` matches no REVIEW
    suggestion are ignored.
    """
    review = [s for s in suggestions if s.band == "REVIEW"]
    if not review:
        return suggestions
    candidates = [
        PairCandidate(
            pair_key=s.suggestion_id,
            entity_type=entity_types[s.entry_a_id],
            name_a=s.name_a,
            name_b=s.name_b,
        )
        for s in review
    ]
    adjudications = await adjudicator.adjudicate(novel_id, user_id, candidates)
    notes = {a.pair_key: a.note for a in adjudications}
    return [
        s.model_copy(update={"adjudication_note": notes[s.suggestion_id]})
        if s.band == "REVIEW" and s.suggestion_id in notes
        else s
        for s in suggestions
    ]


__all__ = ["UncertainBandAdjudicator", "annotate_review_band"]
