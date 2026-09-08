"""KB entity resolution request/response schemas (ADR-085 P3-P5, spec §2/§6/§7).

Pydantic models for the detection-analysis surface and the merge executor.
``ResolutionAnalysis`` in ``contracts.py`` is discharged by
``ResolutionAnalysisResponse`` — the analyzer protocol's result type is the
concrete response shape defined here. ``MergePlan``/``MergeExecutionResult``
discharge the merge aliases in ``contracts.py`` (spec §6); the uncertain-band
``PairCandidate``/``Adjudication`` shapes live in ``schemas_adjudication.py``
(spec §2, P5). Field names ``suggestions``/``stats``/``cache_hit`` are spec
§7 contract.
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID  # noqa: TC003 — needed at runtime for Pydantic model resolution

from pydantic import BaseModel

# Bands that may appear in the suggestion list; SUPPRESSED pairs are counted
# in stats only (spec §4 — never surfaced).
SuggestionBand = Literal["REVIEW", "AUTO_ELIGIBLE"]


class SignalEvidence(BaseModel):
    """Per-signal evidence attached to one suggestion (evidence transparency)."""

    signal: str
    """Signal id, e.g. ``name_tier`` or ``temporal``."""

    value: float
    """Normalized signal value in ``[-1, 1]`` (+ corroborate, - contradict)."""

    veto: bool
    """Whether this signal vetoed the pair (caps confidence, blocks AUTO)."""

    detail: str
    """Human-readable evidence string surfaced in the UI."""


class SuggestionResponse(BaseModel):
    """One surfaced merge suggestion (band REVIEW or AUTO_ELIGIBLE)."""

    suggestion_id: str
    """Stateless identity: ``sha256(min(idA,idB) ‖ max(idA,idB))[:16]`` over
    the UUID strings; re-validated at endorse time (spec §7)."""

    entry_a_id: UUID
    """First entry id (min by UUID ordering)."""

    entry_b_id: UUID
    """Second entry id (max by UUID ordering)."""

    name_a: str
    """KB name of ``entry_a_id`` at analysis time."""

    name_b: str
    """KB name of ``entry_b_id`` at analysis time."""

    confidence: float
    """Calibrated pair confidence in ``[0, 1]`` (spec §4 formula)."""

    band: SuggestionBand
    """Resolution band; ``AUTO_ELIGIBLE`` never auto-executes in v1."""

    auto_merge_eligible: bool
    """``True`` iff band == AUTO_ELIGIBLE — benchmark/policy input only."""

    signals: list[SignalEvidence]
    """All five signal results in canonical S1..S5 order."""

    adjudication_note: str | None = None
    """LLM adjudicator note for REVIEW-band pairs (ADR-085 P5). ``None``
    when no adjudicator is wired, the band is deterministic, or the pair
    was never annotated; a failure note records LLM unavailability
    (RULE-11) instead of crashing the analysis."""


class BandStats(BaseModel):
    """Per-band pair counts for one analysis run."""

    review: int
    """Pairs in the REVIEW band (surfaced)."""

    auto_eligible: int
    """Pairs in the AUTO_ELIGIBLE band (surfaced, flagged)."""

    suppressed: int
    """Pairs below the REVIEW threshold (never surfaced; logged, RULE-11)."""


class ResolutionAnalyzeRequest(BaseModel):
    """Request body for the analyze endpoint (spec §7).

    Prefixed ``Resolution…`` so the generated OpenAPI schema name cannot
    collide with the unrelated memory-domain ``AnalyzeRequest`` (fix
    round 1 — a collision forced FastAPI to rename the memory schema).
    """

    refresh: bool = False
    """Skip the cache read and force a detection recompute."""


class ResolutionAnalysisResponse(BaseModel):
    """Detection result for one novel scope (spec §7 analyze response)."""

    suggestions: list[SuggestionResponse]
    """Surfaced suggestions (REVIEW or AUTO_ELIGIBLE bands only)."""

    stats: BandStats
    """Per-band counts including suppressed pairs."""

    cache_hit: bool
    """Whether this response came from the analysis cache."""


class ResolutionEndorseRequest(BaseModel):
    """Optional endorse body (spec §7): ``{survivor_id?}``.

    When omitted (or ``None``), the survivor is picked by the §6.1
    deterministic total order; when present it must name one of the two
    suggested entries.
    """

    survivor_id: UUID | None = None
    """Endorsement override: the suggested entry that keeps its row."""


# --- Merge executor (ADR-085 P4, spec §6) ----------------------------------------


class MergeConflict(BaseModel):
    """One scalar metadata conflict resolved in the survivor's favor (§6.2).

    Recorded in the survivor's ``metadata["resolution"]["conflicts"]`` and
    in :attr:`MergeExecutionResult.conflicts` — merge-not-clobber, the
    loser's value is preserved here and in the deprecated loser row (never
    silently lost).
    """

    key: str
    """Dotted metadata path of the conflict, e.g. ``gender`` or ``address.city``."""

    survivor_value: object
    """Value kept (the survivor's)."""

    loser_value: object
    """Value overridden (the loser's) — preserved in this record, not lost."""


class MergePlan(BaseModel):
    """Endorsed merge order (spec §6 input)."""

    survivor_id: UUID
    """Entry that keeps its row and absorbs the loser."""

    loser_id: UUID
    """Entry deprecated by the merge — never deleted (§6.4)."""

    suggestion_id: str
    """Stateless suggestion identity this plan was endorsed from (§7)."""

    confidence: float | None = None
    """Re-scored pair confidence at endorse time; recorded in the loser's
    ``resolution`` block. ``None`` only for executor-level callers that did
    not re-validate (the endorse endpoint always supplies it)."""

    result_name: str | None = None
    """Optional canonical name. Per PO ruling OQ-5 this is accepted ONLY
    when it exactly equals the ``decide_rename`` auto-result for the pair;
    explicit custom names are rejected (422 at the HTTP seam)."""


class MergeExecutionResult(BaseModel):
    """Outcome of one executed merge (spec §6)."""

    survivor_id: UUID
    """Entry that absorbed the loser."""

    loser_id: UUID
    """Entry deprecated by the merge."""

    merged_fact_keys: list[str]
    """Top-level loser metadata keys incorporated without conflict (added,
    recursively merged, list-unioned, or already equal)."""

    repointed_relationships: int
    """Edges re-pointed from the loser to the survivor (§6.3)."""

    skipped_relationships: int
    """Edges left untouched: ``uq_kb_relationships_unique`` collisions and
    would-be self-references (logged per RULE-11, never deleted)."""

    conflicts: list[MergeConflict]
    """Scalar conflicts resolved in the survivor's favor (§6.2)."""
