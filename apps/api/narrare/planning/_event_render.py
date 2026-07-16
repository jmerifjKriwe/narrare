"""Compact timeline-event rendering for prompt context (RULE-04 shared helper).

Both the timeline analysis service (``entity_events`` slot) and the
character-arc service (``existing_plot_points`` slot) render a novel's
confirmed :class:`TimelineEvent` rows into a compact text block for the
governed prompt templates. Duplicating that rendering in each service would
violate RULE-04 (DRY) and push the services toward their size limit, so the
pure rendering lives here and a thin async assembler fetches + renders in a
single call.

Kept OUT of the KB context provider: timeline events are a separate concern
from KB entity context (characters/locations/factions/relationships), so they
get their own focused module (RULE-06). The repository query itself stays in
:class:`TimelineEventRepository`; this module only invokes it — no SQL/ORM
lives here.

See:
    docs/_shared/CONSTRAINTS.md (RULE-04, RULE-06, RULE-11)
    .opencode/context/narrare-dev/standards/architectural-discipline.md §7
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import uuid
    from collections.abc import Sequence

    from narrare.planning.models import TimelineEvent
    from narrare.planning.timeline_repository import TimelineEventRepository


def render_compact_events(events: Sequence[TimelineEvent]) -> str:
    """Render timeline events into a compact, model-readable text block.

    Each event becomes a numbered entry carrying its name, type, raw
    timestamp, description, and character/location references — but only the
    fields that are actually present, so the block stays compact.

    Args:
        events: Timeline events to render (the caller selects the subset,
            e.g. all confirmed events or only ``plot_point`` events).

    Returns:
        A compact multi-line string, or ``""`` for an empty sequence so
        callers degrade cleanly (RULE-11) — the template renders the slot
        empty rather than crashing the variable engine.
    """
    if not events:
        return ""

    blocks: list[str] = []
    for index, event in enumerate(events, start=1):
        header = f"{event.event_name} [{event.event_type or 'event'}]"
        timestamp = (event.timestamp_raw or "").strip()
        if timestamp:
            header = f"{header} ({timestamp})"
        lines = [f"{index}. {header}"]

        description = (event.description or "").strip()
        if description:
            lines.append(f"   {description}")

        ref_segments: list[str] = []
        character_names = [
            str(ref.get("name", "")).strip()
            for ref in (event.character_refs or [])
            if str(ref.get("name", "")).strip()
        ]
        if character_names:
            ref_segments.append("Characters: " + ", ".join(character_names))
        location = event.location_ref
        location_name = str(location.get("name", "")).strip() if isinstance(location, dict) else ""
        if location_name:
            ref_segments.append("At: " + location_name)
        if ref_segments:
            lines.append("   " + " | ".join(ref_segments))

        blocks.append("\n".join(lines))

    return "\n".join(blocks)


async def render_confirmed_events(
    event_repo: TimelineEventRepository | None,
    novel_id: uuid.UUID,
    *,
    event_type: str | None = None,
) -> str:
    """Fetch a novel's confirmed events and render them into compact text.

    Combines the repository fetch with :func:`render_compact_events` so the
    two consuming services share a single call site. Degrades to an empty
    string (RULE-11) when no repository is wired or the novel has no
    confirmed events — the template renders the slot empty, never crashes.

    Args:
        event_repo: Timeline-event repository, or ``None`` (degrade to "").
        novel_id: Novel whose confirmed events are rendered.
        event_type: Optional type filter. ``None`` renders every confirmed
            event (the timeline ``entity_events`` slot); ``"plot_point"``
            renders only plot-point events (the character-arc
            ``existing_plot_points`` slot).

    Returns:
        Compact event text, or ``""`` when there is no repo or no events.
    """
    if event_repo is None:
        return ""

    events = await event_repo.list_by_novel(
        novel_id,
        is_confirmed=True,
        event_type=event_type,
    )
    return render_compact_events(events)
