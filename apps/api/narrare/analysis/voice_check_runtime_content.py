"""Voice-check runtime-content formatters (user channel, RULE-02a category 3).

Extracted from ``voice_check_service.py`` for RULE-04 compliance
(service < 300 lines). Owns the formatting of the three runtime-content
blocks that flow to the :class:`CharacterVoiceCheckerAgent` run prompt
(user channel): the attributed chapter dialogue, the stored *descriptive*
voice profiles per character, and the deterministic metric-delta summary
per character.

These are category-3 runtime data (RULE-02a) — never feature-task framing.
No system/task instructions are assembled here (RULE-02 / RULE-02b). The
metric-delta is computed by
:mod:`narrare_core.analysis.voice_check_scoring` (Layer 2a); this module
only renders it for the model — the agent interprets it, never recomputes
it (ADR-021).

See:
    ADR-057 — Voice-check checking-path contract (Decision 2 scoring).
    ADR-021 — Deterministic analysis strategy.
    RULE-04 — Modularise, never compress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from narrare_core.analysis.voice_types import AttributedUtterance
    from narrare_core.kb.schemas.character import VoiceMetrics
    from narrare_core.profiles.models import CharacterVoiceProfile


def format_attributed_dialogue(utterances: Sequence[AttributedUtterance]) -> str:
    """Format attributed utterances as speaker-tagged dialogue text.

    Utterances with no deterministic speaker (``speaker=None``) are tagged
    ``"?"`` (mirrors the ANAL-008 profiler formatter — the agent resolves
    residual ambiguity inline, ADR-055 Decision 3 / ADR-057 Risk #4).
    """
    lines: list[str] = []
    for utt in utterances:
        speaker = utt.speaker or "?"
        lines.append(f'{speaker}: "{utt.text}"')
    return "\n".join(lines)


def format_descriptive_profiles(profiles: Sequence[CharacterVoiceProfile]) -> str:
    """Format the stored *descriptive* voice profiles per character.

    This is the descriptive ``speech_summary`` (the profile the agent checks
    against). Raw deterministic ``voice_metrics`` are NEVER rendered here —
    they reach the model only via the metric-delta summary
    (:func:`format_metric_delta_summary`), preserving the ADR-055
    "metrics never reach generation verbatim" boundary (the checker is the
    checking consumer; it sees deltas, not raw stored metrics).
    """
    lines: list[str] = []
    for profile in profiles:
        summary = profile.speech_summary.strip()
        if summary:
            lines.append(f"{profile.name}: {summary}")
    return "\n".join(lines)


def format_metric_delta_summary(
    stored_metrics_by_name: Mapping[str, VoiceMetrics],
    current_metrics_by_name: Mapping[str, VoiceMetrics],
    character_names: Sequence[str],
) -> str:
    """Format the deterministic metric-delta per checkable character.

    Renders the normalized [0, 1] per-metric distance (from
    :func:`narrare_core.analysis.voice_check_scoring.voice_metric_distances`)
    plus the aggregate metric-delta sub-score (from
    :func:`metric_delta_subscore`) for each character. The agent interprets
    these — it never recomputes them (ADR-021).

    Args:
        stored_metrics_by_name: Stored (profiled) metrics per character.
        current_metrics_by_name: Current-chapter metrics per character.
        character_names: The characters being checked (the delta is rendered
            only for these).

    Returns:
        A newline-joined summary, or an empty string when no character has
        a metric delta to render (RULE-11 graceful).
    """
    from narrare_core.analysis.voice_check_scoring import (
        metric_delta_subscore,
        voice_metric_distances,
    )

    lines: list[str] = []
    for name in character_names:
        stored = stored_metrics_by_name.get(name)
        current = current_metrics_by_name.get(name)
        if stored is None or current is None:
            continue
        distances = voice_metric_distances(stored, current)
        if not distances:
            continue
        delta_parts = [f"{metric} d={distance:.2f}" for metric, distance in distances.items()]
        aggregate = metric_delta_subscore(stored, current)
        agg_str = f"{aggregate:.1f}" if aggregate is not None else "n/a"
        lines.append(f"{name}: {'; '.join(delta_parts)} (delta sub-score: {agg_str})")
    return "\n".join(lines)


def build_run_prompt(
    attributed_dialogue: str,
    descriptive_profiles: str,
    metric_delta_summary: str,
) -> str:
    """Build the agent run prompt (user channel) from runtime content.

    The attributed dialogue + stored descriptive profiles + metric-delta are
    category-3 runtime content (RULE-02a) — never feature-task framing.
    """
    parts = [f"Dialogue:\n{attributed_dialogue}"]
    if descriptive_profiles:
        parts.append(f"\nStored voice profiles:\n{descriptive_profiles}")
    if metric_delta_summary:
        parts.append(f"\nMetric deltas (deterministic; lower is closer):\n{metric_delta_summary}")
    return "\n".join(parts)
