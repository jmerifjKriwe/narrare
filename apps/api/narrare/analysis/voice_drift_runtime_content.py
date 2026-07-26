"""Voice-drift runtime-content formatters (user channel, RULE-02a category 3).

Extracted from ``voice_drift_service.py`` for RULE-04 compliance
(service < 300 lines). Owns the formatting of the runtime-content blocks
that flow to the :class:`CharacterVoiceDriftAgent` run prompt (user
channel): the stored *descriptive* voice profile, the precomputed per-chapter
match trend (signal i), the adjacent-chapter jump points (signal iii), and
the chapter metadata.

These are category-3 runtime data (RULE-02a) — never feature-task framing.
No system/task instructions are assembled here (RULE-02 / RULE-02b). The
trend + jumps are computed by
:mod:`narrare_core.analysis.voice_drift_scoring` (deterministic, ADR-021);
this module only renders them for the model — the agent interprets them,
never recomputes them (ADR-021/ADR-073 Decision 2).

See:
    ADR-073 — Character Voice Drift (Decision 2 comparison model).
    ADR-021 — Deterministic analysis strategy.
    RULE-04 — Modularise, never compress.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.agents.character_voice_drift_types import (
        ChapterMeta,
        JumpPoint,
        TrendPoint,
    )


def format_trend(trend: list[TrendPoint]) -> str:
    """Format the per-chapter match trend (signal i) for the agent run prompt.

    Renders one line per :class:`TrendPoint` with the chapter id, the match
    sub-score, and the band. The agent interprets these — it never recomputes
    them (ADR-021).
    """
    if not trend:
        return "(no trend data — the character did not speak in any selected chapter)"
    lines: list[str] = []
    for point in trend:
        lines.append(
            f"Chapter {point.chapter_id}: match {point.match_subscore:.1f}/100 ({point.band})"
        )
    return "\n".join(lines)


def format_jumps(jumps: list[JumpPoint]) -> str:
    """Format the adjacent-chapter jump points (signal iii) for the run prompt.

    Renders one line per :class:`JumpPoint` with the chapter pair, the jumped
    metric names, and the magnitude. Empty when no metric shifted beyond the
    threshold (a stable voice — the agent may classify as ``evolution`` with
    low confidence).
    """
    if not jumps:
        return "(no adjacent-chapter jumps detected)"
    lines: list[str] = []
    for jump in jumps:
        metrics = ", ".join(jump.jumped_metrics)
        lines.append(
            f"Chapter {jump.from_chapter_id} -> {jump.to_chapter_id}: "
            f"{metrics} shifted (magnitude {jump.magnitude:.2f})"
        )
    return "\n".join(lines)


def format_chapter_meta(chapter_meta: list[ChapterMeta]) -> str:
    """Format the per-chapter metadata for the run prompt.

    Grounds the agent's ``per_chapter_notes`` and ``suggested_attention`` in
    real chapter ids + titles. Only chapters in the trend are included (the
    caller guarantees this by construction).
    """
    if not chapter_meta:
        return "(no chapter metadata)"
    lines: list[str] = []
    for meta in chapter_meta:
        title = meta.title.strip()
        label = f"Chapter {meta.chapter_id}"
        if title:
            label += f" — {title}"
        if meta.summary:
            label += f" ({meta.summary})"
        lines.append(label)
    return "\n".join(lines)


def build_run_prompt(
    character_name: str,
    descriptive_profile: str,
    trend: list[TrendPoint],
    jumps: list[JumpPoint],
    chapter_meta: list[ChapterMeta],
) -> str:
    """Build the agent run prompt (user channel) from runtime content.

    The character name + stored descriptive profile + precomputed trend +
    jumps + chapter metadata are category-3 runtime content (RULE-02a) —
    never feature-task framing. The governed ``voice_drift`` system prompt
    (resolved Mode 1 by the service) carries the task framing.
    """
    parts = [f"Character: {character_name}"]
    if descriptive_profile.strip():
        parts.append(f"\nStored voice profile:\n{descriptive_profile}")
    parts.append(
        f"\nPer-chapter match trend (deterministic; 100 = matches profile):\n{format_trend(trend)}"
    )
    parts.append(f"\nAdjacent-chapter jumps (deterministic):\n{format_jumps(jumps)}")
    parts.append(f"\nChapters:\n{format_chapter_meta(chapter_meta)}")
    return "\n".join(parts)
