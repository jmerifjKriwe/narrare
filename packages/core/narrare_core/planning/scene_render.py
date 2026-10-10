"""Scene prompt renderer — compact scene blocks for LLM run prompts.

One pure renderer shared by scene refine (planning) and the scene-by-scene
writing pipeline (spec §6.3) — one format, no drift. This serializes
category-3 runtime data, not prompt-template content; callers XML-wrap the
output at the service call-site (RULE-22 §6, the ``_outline_render``
precedent).

Accepts both scene shapes structurally (PLAN-001 T9): planning's
:class:`~narrare_core.planning.models.ScenePlanData` (presences as
``ScenePresence`` objects) and writing's
:class:`~narrare_core.writing.requests.SceneSpec` (presences as
``(name, goal)`` pairs). Both share the attribute names the renderer
reads, so no runtime class check is needed — only the presence entries
are normalized per element. Type-only imports keep the ``planning`` and
``writing`` packages free of a runtime import cycle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

    from narrare_core.planning.models import ScenePlanData, ScenePresence
    from narrare_core.writing.requests import SceneSpec


def _presence_pairs(
    present: Sequence[ScenePresence | tuple[str, str]],
) -> tuple[tuple[str, str], ...]:
    """Normalize presence entries (``ScenePresence`` or ``(name, goal)``) to pairs."""
    pairs: list[tuple[str, str]] = []
    for entry in present:
        if isinstance(entry, tuple):
            pairs.append(entry)
        else:
            pairs.append((entry.name, entry.goal))
    return tuple(pairs)


def render_scene_for_prompt(scene: ScenePlanData | SceneSpec, number: int | None = None) -> str:
    """Render *scene* as a compact block; empty sections are omitted.

    Header is ``Scene {number}: {title}``; the ``Scene {number}: `` prefix
    is omitted when *number* is ``None``. Lines are joined with ``"\\n"``;
    beats render as ``Beats:`` plus ``  1. …`` items. Works on both
    ``ScenePlanData`` and ``SceneSpec`` inputs (identical output).
    """
    lines: list[str] = [f"Scene {number}: {scene.title}" if number is not None else scene.title]
    if scene.pov_character_name:
        lines.append(f"POV: {scene.pov_character_name}")
    if scene.location_name:
        lines.append(f"Location: {scene.location_name}")
    pairs = _presence_pairs(scene.present_characters)
    if pairs:
        presences = "; ".join(f"{name} ({goal})" if goal else name for name, goal in pairs)
        lines.append(f"Characters: {presences}")
    if scene.purpose:
        lines.append(f"Purpose: {scene.purpose}")
    if scene.conflict:
        lines.append(f"Conflict: {scene.conflict}")
    if scene.resolution:
        lines.append(f"Resolution: {scene.resolution}")
    if scene.beats:
        lines.append("Beats:")
        lines.extend(f"  {i}. {beat}" for i, beat in enumerate(scene.beats, start=1))
    return "\n".join(lines)


__all__ = ["render_scene_for_prompt"]
