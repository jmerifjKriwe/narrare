"""Author-voice-drift response assembly helper.

This module maps the precomputed trend + jumps + the agent's
:class:`VoiceDriftResult` into the API :class:`AuthorVoiceDriftResult`
schema. It is pure mapping logic: no I/O, no prompt resolution, no profile
access, no LLM. The overall match score + band are derived deterministically
from the trend (ADR-021 — the aggregate is a mean of the per-chapter
subscores, banded via the same ``band_for_score`` thresholds as WRITE-010 +
Phase 1, ADR-073 D4).

RULE-22 (no duplication): the overall-score mean is a 3-line computation and
the band mapping reuses the public ``band_for_score`` (identical thresholds to
WRITE-010 + Phase 1). Only the enum→label name pairs are local (the Core
mapping is private) — mirroring :mod:`voice_drift_results` verbatim.

See:
    :mod:`narrare.analysis.voice_drift_results` — Phase 1 (per-character
        parallel; this is its singular author-voice mirror).
    ADR-074 — Author Voice Storage Contract.
    ADR-073 — Character Voice Drift (Decision 4 band thresholds).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.analysis.schemas_author_voice_drift import AuthorVoiceDriftResult

if TYPE_CHECKING:
    from uuid import UUID

    from narrare_core.agents.character_voice_drift_types import VoiceDriftResult
    from narrare_core.analysis.voice_drift_scoring_types import (
        JumpPoint,
        TrendPoint,
    )


def _overall_score(trend: list[TrendPoint]) -> float | None:
    """Mean of the per-chapter ``match_subscore`` values, or None if empty."""
    if not trend:
        return None
    return sum(point.match_subscore for point in trend) / len(trend)


# Drift-facing band labels for the WRITE-010 VoiceCheckBand enum (ADR-073 D4).
# The thresholds themselves come from the reused public ``band_for_score``
# (identical to WRITE-010 + Phase 1 — no threshold duplication); only the 4
# enum→label name pairs are local because the Core mapping is private.
# Mirrors ``voice_drift_results._BAND_TO_DRIFT_LABEL`` verbatim (RULE-22).
_BAND_TO_DRIFT_LABEL: dict[str, str] = {
    "green": "stable",
    "yellow": "minor",
    "fair": "moderate",
    "red": "major",
}


def _overall_band(score: float | None) -> str | None:
    """Map the overall score to the drift-facing band label (ADR-073 D4).

    Reuses the public ``band_for_score`` (identical thresholds to WRITE-010 +
    Phase 1) and maps the resulting enum to the drift label.
    """
    if score is None:
        return None
    from narrare_core.analysis.voice_check_scoring import band_for_score

    return _BAND_TO_DRIFT_LABEL[band_for_score(score).value]


def assemble_author_voice_drift_result(
    *,
    novel_id: UUID,
    trend: list[TrendPoint],
    jumps: list[JumpPoint],
    drift: VoiceDriftResult,
) -> AuthorVoiceDriftResult:
    """Assemble the narrator drift result event payload.

    Args:
        novel_id: The novel id analysed (carried onto the result as str).
        trend: The precomputed per-chapter match trend (signal i).
        jumps: The precomputed adjacent-chapter jump points (signal iii).
        drift: The agent's qualitative :class:`VoiceDriftResult`.

    Returns:
        The API :class:`AuthorVoiceDriftResult` with the deterministic trend
        + jumps + the derived overall score/band + the agent classification.
    """
    overall = _overall_score(trend)
    return AuthorVoiceDriftResult(
        novel_id=str(novel_id),
        trend=list(trend),
        jumps=list(jumps),
        overall_match_score=overall,
        overall_band=_overall_band(overall),
        drift=drift,
    )
