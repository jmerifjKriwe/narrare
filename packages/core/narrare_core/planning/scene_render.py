"""Scene prompt renderer — compact scene blocks for LLM run prompts.

One pure renderer shared by scene refine (planning) and the scene-by-scene
writing pipeline (spec §6.3) — one format, no drift. This serializes
category-3 runtime data, not prompt-template content; callers XML-wrap the
output at the service call-site (RULE-22 §6, the ``_outline_render``
precedent).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from narrare_core.planning.models import ScenePlanData


def render_scene_for_prompt(scene: ScenePlanData, number: int | None = None) -> str:
    """Render *scene* as a compact block; empty sections are omitted.

    Header is ``Scene {number}: {title}``; the ``Scene {number}: `` prefix
    is omitted when *number* is ``None``. Lines are joined with ``"\\n"``;
    beats render as ``Beats:`` plus ``  1. …`` items.
    """
    lines: list[str] = [f"Scene {number}: {scene.title}" if number is not None else scene.title]
    if scene.pov_character_name:
        lines.append(f"POV: {scene.pov_character_name}")
    if scene.location_name:
        lines.append(f"Location: {scene.location_name}")
    if scene.present_characters:
        presences = "; ".join(
            f"{p.name} ({p.goal})" if p.goal else p.name for p in scene.present_characters
        )
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
