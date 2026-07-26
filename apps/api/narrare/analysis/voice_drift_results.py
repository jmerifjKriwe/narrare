"""Voice-drift response assembly helpers.

This module maps the precomputed trend + jumps + the agent's
:class:`VoiceDriftResult` into the API :class:`VoiceDriftCharacterResult`
schema. It is pure mapping logic: no I/O, no prompt resolution, no KB access,
no LLM. The overall match score + band are derived deterministically from
the trend (ADR-021 — the aggregate is a mean of the per-chapter subscores,
banded via the same ``band_for_score`` thresholds as WRITE-010, ADR-073 D4).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.analysis.schemas_voice_drift import VoiceDriftCharacterResult

if TYPE_CHECKING:
    from narrare_core.agents.character_voice_drift_types import (
        VoiceDriftResult,
    )
    from narrare_core.analysis.voice_drift_scoring_types import (
        JumpPoint,
        TrendPoint,
    )
    from narrare_core.profiles.models import CharacterVoiceProfile


def _overall_score(trend: list[TrendPoint]) -> float | None:
    """Mean of the per-chapter ``match_subscore`` values, or None if empty."""
    if not trend:
        return None
    return sum(point.match_subscore for point in trend) / len(trend)


# Drift-facing band labels for the WRITE-010 VoiceCheckBand enum (ADR-073 D4).
# The thresholds themselves come from the reused public ``band_for_score``
# (identical to WRITE-010 — no threshold duplication); only the 4 enum→label
# name pairs are local because the Core mapping is private. Mirrors
# ``voice_drift_scoring._VOICE_CHECK_BAND_TO_DRIFT_LABEL`` verbatim.
_BAND_TO_DRIFT_LABEL: dict[str, str] = {
    "green": "stable",
    "yellow": "minor",
    "fair": "moderate",
    "red": "major",
}


def _overall_band(score: float | None) -> str | None:
    """Map the overall score to the drift-facing band label (ADR-073 D4).

    Reuses the public ``band_for_score`` (identical thresholds to WRITE-010)
    and maps the resulting enum to the drift label.
    """
    if score is None:
        return None
    from narrare_core.analysis.voice_check_scoring import band_for_score

    return _BAND_TO_DRIFT_LABEL[band_for_score(score).value]


def assemble_voice_drift_result(
    *,
    profile: CharacterVoiceProfile,
    trend: list[TrendPoint],
    jumps: list[JumpPoint],
    drift: VoiceDriftResult,
) -> VoiceDriftCharacterResult:
    """Assemble one per-character drift result event payload.

    Args:
        profile: The stored profile (carries ``character_id`` + ``name``).
        trend: The precomputed per-chapter match trend (signal i).
        jumps: The precomputed adjacent-chapter jump points (signal iii).
        drift: The agent's qualitative :class:`VoiceDriftResult`.

    Returns:
        The API :class:`VoiceDriftCharacterResult` with the deterministic
        trend + jumps + the derived overall score/band + the agent
        classification.
    """
    overall = _overall_score(trend)
    return VoiceDriftCharacterResult(
        character_id=profile.character_id,
        character_name=profile.name,
        trend=list(trend),
        jumps=list(jumps),
        overall_match_score=overall,
        overall_band=_overall_band(overall),
        drift=drift,
    )
