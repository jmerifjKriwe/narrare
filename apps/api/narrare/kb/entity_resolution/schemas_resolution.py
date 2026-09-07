"""KB entity resolution response schemas (ADR-085 P3, spec §2/§7).

Pydantic models for the detection-analysis surface. ``ResolutionAnalysis``
in ``contracts.py`` is discharged by ``ResolutionAnalysisResponse`` — the
analyzer protocol's result type is the concrete response shape defined here.
Field names ``suggestions``/``stats``/``cache_hit`` are spec §7 contract.
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


class BandStats(BaseModel):
    """Per-band pair counts for one analysis run."""

    review: int
    """Pairs in the REVIEW band (surfaced)."""

    auto_eligible: int
    """Pairs in the AUTO_ELIGIBLE band (surfaced, flagged)."""

    suppressed: int
    """Pairs below the REVIEW threshold (never surfaced; logged, RULE-11)."""


class ResolutionAnalysisResponse(BaseModel):
    """Detection result for one novel scope (spec §7 analyze response)."""

    suggestions: list[SuggestionResponse]
    """Surfaced suggestions (REVIEW or AUTO_ELIGIBLE bands only)."""

    stats: BandStats
    """Per-band counts including suppressed pairs."""

    cache_hit: bool
    """Whether this response came from the analysis cache."""
