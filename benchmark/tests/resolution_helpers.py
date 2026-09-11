"""Fixture builders for the resolution-scorer tests (ADR-085 P6).

Synthetic duplicate/distractor corpus (spec §8 evidence base): "Anna" +
"Anna Meyer" are ONE reference claim group (alias "Anna"); the
distractor "Anna Meier" is its OWN reference. Split from the test
module per RULE-04 (predecessor pattern: ``scoring_helpers.py``) —
plain builders, no fixtures, no network.
"""

from __future__ import annotations

from benchmark.artifacts_records import CapabilityAnswer
from benchmark.corpus_loader import Corpus
from benchmark.drivers.base import CapabilityStatus
from benchmark.drivers.in_records import (
    BandStats,
    MergeResult,
    ResolutionRecord,
    ResolutionSuggestion,
)
from benchmark.drivers.out_records import EntrySummary
from benchmark.runner_scoring import ScoredKb
from benchmark.scoring.resolution_match import ClaimEntry
from benchmark.tests.scoring_helpers import detail, make_reference, ref_entity

E_ANNA = "e-anna"
E_ANNA_MEYER = "e-anna-meyer"
E_ANNA_MEIER = "e-anna-meier"
E_OTHER = "e-other"

ANNA_GROUP_REFS = (
    ref_entity("p-anna", "Anna Meyer", aliases=("Anna",)),
    ref_entity("p-meier", "Anna Meier"),
)


def claim_entry(entry_id: str, name: str, *, slug: str | None = None) -> ClaimEntry:
    """One pre-merge KB entry with the derived slug (or an explicit one)."""
    return ClaimEntry(
        id=entry_id, name=name, slug=slug if slug is not None else name.lower().replace(" ", "-")
    )


def duplicate_suggestion(
    *,
    band: str = "REVIEW",
    auto_merge_eligible: bool = False,
) -> ResolutionSuggestion:
    """The true duplicate pair, pre-merge ids."""
    return ResolutionSuggestion(
        suggestion_id="s-dup",
        entry_a_id=E_ANNA,
        entry_b_id=E_ANNA_MEYER,
        name_a="Anna",
        name_b="Anna Meyer",
        confidence=0.9,
        band=band,
        auto_merge_eligible=auto_merge_eligible,
    )


def cross_suggestion() -> ResolutionSuggestion:
    """The distractor trap: Anna Meyer entry vs Anna Meier entry."""
    return ResolutionSuggestion(
        suggestion_id="s-cross",
        entry_a_id=E_ANNA_MEYER,
        entry_b_id=E_ANNA_MEIER,
        name_a="Anna Meyer",
        name_b="Anna Meier",
        confidence=0.5,
        band="REVIEW",
        auto_merge_eligible=False,
    )


def duplicate_merge() -> MergeResult:
    """The executed duplicate merge: survivor Anna Meyer, loser Anna."""
    return MergeResult(
        survivor_id=E_ANNA_MEYER,
        loser_id=E_ANNA,
        merged_fact_keys=("age",),
        repointed_relationships=2,
        skipped_relationships=0,
    )


def post_merge_kb() -> ScoredKb:
    """Post-endorse scored-KB state: the loser is deprecated-hidden."""
    return ScoredKb(
        entries=(
            _summary(E_ANNA_MEYER, "Anna Meyer"),
            _summary(E_ANNA_MEIER, "Anna Meier"),
            _summary(E_OTHER, "Ben Neumann"),
        ),
        details=(
            detail(E_ANNA_MEYER, name="Anna Meyer"),
            detail(E_ANNA_MEIER, name="Anna Meier"),
            detail(E_OTHER, name="Ben Neumann"),
        ),
    )


def resolution_answer() -> CapabilityAnswer:
    """The driven CAP-IN-10 OK answer: one suggestion, one merge."""
    record = ResolutionRecord(
        suggestions=(duplicate_suggestion(),),
        stats=BandStats(review=1, auto_eligible=0, suppressed=0),
        cache_hit=False,
        merges=(duplicate_merge(),),
    )
    return CapabilityAnswer(
        cap_id="CAP-IN-10", status=CapabilityStatus.OK, elapsed_seconds=0.1, parsed=record
    )


def synthetic_corpus() -> Corpus:
    """Clean-only corpus whose reference carries the duplicate/distractor."""
    return Corpus(
        stems=(),
        clean=(),
        variants=(),
        reference=make_reference(persons=ANNA_GROUP_REFS),
        warnings=(),
        version=1,
    )


def _summary(entry_id: str, name: str) -> EntrySummary:
    return EntrySummary(
        id=entry_id,
        name=name,
        entity_type="character",
        slug=name.lower().replace(" ", "-"),
        status="approved",
        review_status="approved",
    )
