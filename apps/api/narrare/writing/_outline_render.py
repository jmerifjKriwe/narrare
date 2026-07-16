"""Compact chapter-outline rendering for prompt context (RULE-06 helper).

The story-suggest service renders the targeted chapter's outline (stage
assignment, planned beats, free-form notes) into the ``chapter_outline``
prompt slot so suggestions stay grounded in the established plan. Keeping
that rendering out of the service keeps the service focused on orchestration
(RULE-06) and under its size limit (RULE-04).

The :class:`ChapterOutline` model lives in the planning domain; this module
only reads its fields — it performs no persistence or business logic.

See:
    docs/_shared/CONSTRAINTS.md (RULE-04, RULE-06, RULE-11)
    .opencode/context/narrare-dev/standards/architectural-discipline.md §7
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from narrare.planning.models import ChapterOutline

# Beat dict keys tried in order when extracting beat text. The planned_beats
# JSONB shape is not locked down across all creators, so the renderer tolerates
# the common variants and falls back to a minimal stringification.
_BEAT_TEXT_KEYS: tuple[str, ...] = ("text", "description", "title", "label", "summary")


def _extract_beat_text(beat: object) -> str:
    """Extract a human-readable line from a single planned-beat entry.

    ``planned_beats`` is JSONB whose entry shape varies across creators, so
    this tolerates the common dict variants and falls back to a minimal
    stringification for anything else.

    Args:
        beat: One beat entry (typically a dict, but JSONB permits anything).

    Returns:
        The extracted/trimmed text (possibly empty).
    """
    if isinstance(beat, dict):
        beat_dict = cast("dict[str, object]", beat)
        for key in _BEAT_TEXT_KEYS:
            candidate = str(beat_dict.get(key, "") or "").strip()
            if candidate:
                return candidate
        return str(beat_dict).strip()
    return str(beat).strip()


def render_chapter_outline(outline: ChapterOutline) -> str:
    """Render a chapter outline into a compact, model-readable text block.

    Carries the stage assignment, planned beats (numbered), and free-form
    notes — omitting any section that is empty so the block stays compact.

    Args:
        outline: The chapter outline to render.

    Returns:
        A compact multi-line string, or ``""`` when the outline carries no
        content (RULE-11) so the caller can degrade cleanly.
    """
    parts: list[str] = []

    stage = (outline.stage_assignment or "").strip()
    if stage:
        parts.append(f"Stage: {stage}")

    beats = outline.planned_beats or []
    if beats:
        beat_lines: list[str] = []
        for index, beat in enumerate(beats, start=1):
            text = _extract_beat_text(beat)
            if text:
                beat_lines.append(f"  {index}. {text}")
        if beat_lines:
            parts.append("Beats:\n" + "\n".join(beat_lines))

    notes = (outline.outline_notes or "").strip()
    if notes:
        parts.append(f"Notes: {notes}")

    return "\n".join(parts)
