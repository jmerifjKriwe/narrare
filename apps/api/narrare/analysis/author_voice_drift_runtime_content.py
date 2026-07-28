"""Author-voice-drift runtime-content formatters (user channel, RULE-02a
category 3).

Extracted from ``author_voice_drift_service.py`` for RULE-04 compliance
(service < 300 lines). Owns the formatting of the runtime-content blocks that
flow to the :class:`AuthorVoiceDriftAgent` run prompt (user channel): the
stored *descriptive* author-voice profile, the precomputed per-chapter match
trend (signal i, author-metric deltas merged), the adjacent-chapter jump
points (signal iii), and the chapter metadata.

These are category-3 runtime data (RULE-02a) — never feature-task framing.
No system/task instructions are assembled here (RULE-02 / RULE-02b). The
trend + jumps are computed by
:mod:`narrare_core.analysis.author_voice_drift_scoring` (deterministic,
ADR-021); this module only renders them for the model — the agent interprets
them, never recomputes them (ADR-021/ADR-073 Decision 2).

RULE-22 (no duplication): the per-block formatters
(:func:`format_trend`, :func:`format_jumps`, :func:`format_chapter_meta`) are
REUSED from Phase 1's :mod:`voice_drift_runtime_content` — they operate on
the shared :class:`TrendPoint` / :class:`JumpPoint` / :class:`ChapterMeta`
types this module also uses. Only the author-specific prompt assembly (the
rendered descriptive profile in place of a character name) is new.

See:
    ADR-074 — Author Voice Storage Contract.
    ADR-073 — Character Voice Drift (Decision 2 comparison model).
    RULE-04 — Modularise, never compress.
    RULE-22 — Reuse shared types/formatters (no duplication).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# REUSE (RULE-22): the per-block formatters operate on the shared
# TrendPoint/JumpPoint/ChapterMeta types and are identical for the author
# trend — no point duplicating them. noqa: TC001 — used at runtime below.
from narrare.analysis.voice_drift_runtime_content import (
    format_chapter_meta,
    format_jumps,
    format_trend,
)

if TYPE_CHECKING:
    from narrare_core.agents.character_voice_drift_types import (
        ChapterMeta,
        JumpPoint,
        TrendPoint,
    )


def build_author_voice_drift_run_prompt(
    descriptive_profile: str,
    trend: list[TrendPoint],
    jumps: list[JumpPoint],
    chapter_meta: list[ChapterMeta],
) -> str:
    """Build the agent run prompt (user channel) from runtime content.

    The stored descriptive profile + precomputed trend + jumps + chapter
    metadata are category-3 runtime content (RULE-02a) — never feature-task
    framing. The governed ``author_voice_drift`` system prompt (resolved Mode
    1 by the service) carries the task framing. Differs from Phase 1's
    :func:`build_run_prompt` only in substituting the rendered narrator
    descriptive profile for the per-character name (the trend is narrator-
    scoped, not per-character).

    Args:
        descriptive_profile: The rendered descriptive author-voice profile
            (from
            :func:`narrare_core.profiles.author_voice.render_author_voice_for_generation`).
        trend: The precomputed per-chapter match trend (signal i).
        jumps: The precomputed adjacent-chapter jump points (signal iii).
        chapter_meta: Per-chapter metadata for the chapters in the trend.

    Returns:
        The assembled user-channel run prompt.
    """
    parts: list[str] = []
    if descriptive_profile.strip():
        parts.append(f"Stored author voice profile:\n{descriptive_profile}")
    parts.append(
        f"\nPer-chapter match trend (deterministic; 100 = matches profile):\n{format_trend(trend)}"
    )
    parts.append(f"\nAdjacent-chapter jumps (deterministic):\n{format_jumps(jumps)}")
    parts.append(f"\nChapters:\n{format_chapter_meta(chapter_meta)}")
    return "\n".join(parts)
