"""Compact chapter-outline rendering for prompt context (RULE-06 helper).

The story-suggest service renders the targeted chapter's outline (stage
assignment, planned scenes, free-form notes) into the ``chapter_outline``
prompt slot so suggestions stay grounded in the established plan. Keeping
that rendering out of the service keeps the service focused on orchestration
(RULE-06) and under its size limit (RULE-04).

The :class:`ChapterOutline`/:class:`ScenePlan` models live in the planning
domain; this module only reads their fields — it performs no persistence
or business logic.

PLAN-001 T15 (ADR-096, spec §7): scene plans replaced the beat outline —
the slot renders stage + numbered scene blocks (via Core's shared
:func:`render_scene_for_prompt`, spec §6.3 — one format, no drift with the
writing pipeline) + notes. The legacy beats column is gone (Alembic 0049).

See:
    docs/_shared/CONSTRAINTS.md (RULE-04, RULE-06, RULE-11)
    .opencode/context/narrare-dev/standards/architectural-discipline.md §7
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from narrare_core.planning.scene_render import render_scene_for_prompt
from narrare_core.writing.requests import SceneSpec

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare.planning.models import ChapterOutline, ScenePlan


def _ref_name(ref: object) -> str:
    """Hybrid ``{id, name}`` JSONB ref → display name ('' when absent).

    Refs are user content of arbitrary runtime shape; only a dict carrying
    a string name resolves (same tolerance as planning's ``_ref_name``).
    """
    if isinstance(ref, dict):
        name = cast("dict[object, object]", ref).get("name", "")
        if isinstance(name, str):
            return name
    return ""


def _scene_spec(row: ScenePlan) -> SceneSpec:
    """ORM scene row → Core ``SceneSpec`` view for the shared renderer.

    Names are resolved from the hybrid KB refs at the render boundary;
    ``present_characters`` JSONB is runtime-shaped, so each entry is
    narrowed before reading ``name``/``goal`` (backfill tolerance).
    """
    presences: list[tuple[str, str]] = []
    raw_presences: Sequence[object] = cast("Sequence[object]", row.present_characters or [])
    for presence in raw_presences:
        if not isinstance(presence, dict):
            continue
        presence_mapping = cast("dict[object, object]", presence)
        name = presence_mapping.get("name", "")
        goal = presence_mapping.get("goal", "")
        if isinstance(name, str):
            presences.append((name, goal if isinstance(goal, str) else ""))
    return SceneSpec(
        title=row.title,
        pov_character_name=_ref_name(row.pov_character_ref),
        location_name=_ref_name(row.location_ref),
        present_characters=tuple(presences),
        purpose=row.purpose,
        conflict=row.conflict,
        resolution=row.resolution,
        beats=tuple(row.beats or ()),
        status=str(row.status),
    )


def render_chapter_outline(outline: ChapterOutline | None, scenes: Sequence[ScenePlan] = ()) -> str:
    """Render a chapter outline into a compact, model-readable text block.

    Carries the stage assignment, one compact block per planned scene
    (numbered in list order via the Core renderer — spec §6.3/§7), and
    free-form notes — omitting any section that is empty so the block
    stays compact. ``outline=None`` (chapter has scene plans but no
    outline row — FU-f: scene plans persist independently of the outline
    row, ADR-096) renders the scene blocks alone; stage and notes
    require the outline row.

    Args:
        outline: The chapter outline to render, or ``None`` when no
            outline row exists (stage/notes are then omitted).
        scenes: The chapter's scene plans (position-ordered, as returned
            by ``ScenePlanRepository.list_by_chapter``).

    Returns:
        A compact multi-line string, or ``""`` when neither the outline
        nor the scenes carry content (RULE-11) so the caller can degrade
        cleanly.
    """
    parts: list[str] = []

    if outline is not None:
        stage = (outline.stage_assignment or "").strip()
        if stage:
            parts.append(f"Stage: {stage}")

    scene_blocks = [
        render_scene_for_prompt(_scene_spec(scene), number=position)
        for position, scene in enumerate(scenes, start=1)
    ]
    if scene_blocks:
        parts.append("\n\n".join(scene_blocks))

    if outline is not None:
        notes = (outline.outline_notes or "").strip()
        if notes:
            parts.append(f"Notes: {notes}")

    return "\n".join(parts)
