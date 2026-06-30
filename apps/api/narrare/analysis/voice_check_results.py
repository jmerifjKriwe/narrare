"""Voice-check response assembly helpers.

This module maps Core checker output plus deterministic scoring into the API
``VoiceCheckResult`` schema. It is pure mapping logic: no I/O, no prompt
resolution, no KB access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.analysis.schemas_voice_check import FlaggedLineResponse, VoiceCheckResult
from narrare_core.analysis.voice_check_scoring import VoiceCheckScorer
from narrare_core.kb.schemas.character import VoiceMetrics

if TYPE_CHECKING:
    from collections.abc import Mapping

    from narrare_core.agents.character_voice_checker_types import CharacterVoiceCheckerEntry
    from narrare_core.profiles.models import CharacterVoiceProfile


def assemble_voice_check_result(
    *,
    name: str,
    profile: CharacterVoiceProfile | None,
    entry: CharacterVoiceCheckerEntry | None,
    current_metrics: Mapping[str, VoiceMetrics],
    scorer: VoiceCheckScorer | None = None,
) -> VoiceCheckResult:
    """Assemble one per-character result event payload.

    Args:
        name: Speaking character name.
        profile: Stored profile from ``assemble_for_checking()``, if present.
        entry: Qualitative checker-agent output for this character, if present.
        current_metrics: Current deterministic metrics by character.
        scorer: Optional scorer override for tests/evaluation.

    Returns:
        API result schema with graceful ``has_profile=False`` when no stored
        profile exists.
    """
    if profile is None:
        return VoiceCheckResult(character_name=name, has_profile=False)

    stored_metrics = profile.voice_metrics or VoiceMetrics()
    qualitative = entry.qualitative_sub_score if entry is not None else None
    resolved_scorer = scorer or VoiceCheckScorer()
    score = resolved_scorer.score(stored_metrics, current_metrics.get(name), qualitative)
    flagged_lines = [
        FlaggedLineResponse(quote=line.quote, reason=line.reason)
        for line in (entry.flagged_lines if entry is not None else [])
    ]

    return VoiceCheckResult(
        character_name=name,
        match_score=score.match_score,
        band=score.band.value if score.band is not None else None,
        match_judgment=entry.match_judgment if entry is not None else None,
        qualitative_sub_score=qualitative,
        metric_delta_subscore=score.metric_delta_subscore,
        flagged_lines=flagged_lines,
        has_profile=True,
        n_comparable_metrics=score.n_comparable_metrics,
    )
