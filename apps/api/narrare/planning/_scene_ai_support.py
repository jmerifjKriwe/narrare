"""Scene AI support — run-prompt assembly + output mapping (PLAN-001 T8).

Extracted from ``scene_ai_service.py`` to respect the 300-line service
limit (RULE-04) — the ``_story_suggest_support.py`` precedent. Pure
functions, no I/O:

- Run-prompt assembly (category-3 runtime data, RULE-22 §6): the caller
  XML-wraps user-authored chapter/scene context; task framing never
  passes through here — it lives in the governed T7 templates
  (``scene_plan_draft`` / ``scene_plan_refine``).
- Output mapping: Core ``SceneProposal`` → wire ``SceneProposalSchema``
  (field names map 1:1; hybrid refs are name-only — the AI cannot know
  KB ids, resolution happens when the client saves via the aggregate
  PUT). Proposals carry NO id: the client assigns UUIDs on insert
  (spec §5.2).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from narrare.planning.schemas_scenes import (
    ScenePresenceSchema,
    SceneProposalSchema,
    SceneRefSchema,
)
from narrare_core.planning import ScenePlanData, ScenePresence, SceneStatus, render_scene_for_prompt

if TYPE_CHECKING:
    from narrare.planning.schemas_scenes import (
        SceneDraftRequest,
        SceneRefineRequest,
        SceneSchema,
    )
    from narrare_core.agents.scene_plan_types import ScenePresenceModel, SceneProposal


def _labeled(label: str, value: str) -> str | None:
    """One ``label: value`` line, omitted when the value is empty."""
    return f"{label}: {value}" if value else None


def _xml_block(tag: str, lines: list[str | None]) -> str:
    """Wrap the non-empty labeled lines in one XML data block (RULE-22 §6)."""
    body = "\n".join(line for line in lines if line)
    return f"<{tag}>\n{body}\n</{tag}>"


def build_draft_run_prompt(request: SceneDraftRequest) -> str:
    """XML-wrapped chapter context + instruction (spec §6.3 draft shape)."""
    context_lines: list[str | None] = [
        _labeled("Structure type", request.structure_type),
        _labeled("Outline notes", request.outline_notes),
        _labeled("Chapter summary", request.chapter_summary),
        _labeled("Neighbor summaries", request.neighbor_summaries),
    ]
    if request.scene_count > 0:
        # Spec-gap resolution: §5.2 carries scene_count on the wire
        # ("0 = model chooses") — the model can only honor it as
        # run-prompt data, so it rides the chapter-context block.
        context_lines.append(_labeled("Scene count", str(request.scene_count)))
    return (
        f"{_xml_block('chapter_context', context_lines)}\n"
        f"{_xml_block('instruction', [request.instruction])}"
    )


def scene_data_from_schema(scene: SceneSchema) -> ScenePlanData:
    """Wire ``SceneSchema`` → Core ``ScenePlanData`` view (renderer input).

    Hybrid KB refs resolve to their display names — rendering needs
    names, not KB linkage (spec §3.2 resolution rule).
    """
    return ScenePlanData(
        id=scene.id,
        position=scene.position,
        title=scene.title,
        pov_character_name=scene.pov_character_ref.name if scene.pov_character_ref else "",
        location_name=scene.location_ref.name if scene.location_ref else "",
        present_characters=tuple(
            ScenePresence(name=presence.name, goal=presence.goal)
            for presence in scene.present_characters
        ),
        purpose=scene.purpose,
        conflict=scene.conflict,
        resolution=scene.resolution,
        beats=tuple(scene.beats),
        status=SceneStatus(scene.status),
    )


def build_refine_run_prompt(request: SceneRefineRequest) -> str:
    """XML-wrapped rendered scene + neighbor context + instruction."""
    context_lines: list[str | None] = [
        _labeled("Previous scene summary", request.prev_scene_summary),
        _labeled("Next scene summary", request.next_scene_summary),
        _labeled("Chapter summary", request.chapter_summary),
    ]
    rendered = render_scene_for_prompt(
        scene_data_from_schema(request.scene), request.scene.position
    )
    return (
        f"{_xml_block('scene_plan', [rendered])}\n"
        f"{_xml_block('chapter_context', context_lines)}\n"
        f"{_xml_block('instruction', [request.instruction])}"
    )


def _name_ref(name: str) -> SceneRefSchema | None:
    """Name-only hybrid ref — AI proposals carry no KB ids (resolved at save)."""
    return SceneRefSchema(id=None, name=name) if name else None


def _presence_schema(presence: ScenePresenceModel) -> ScenePresenceSchema:
    """Core presence → wire presence (``id=None``: no KB linkage)."""
    return ScenePresenceSchema(id=None, name=presence.name, goal=presence.goal)


def proposal_to_schema(proposal: SceneProposal) -> SceneProposalSchema:
    """Core ``SceneProposal`` → wire schema (names map 1:1; NO id)."""
    return SceneProposalSchema(
        title=proposal.title,
        pov_character_ref=_name_ref(proposal.pov_character_name),
        location_ref=_name_ref(proposal.location_name),
        present_characters=[_presence_schema(p) for p in proposal.present_characters],
        purpose=proposal.purpose,
        conflict=proposal.conflict,
        resolution=proposal.resolution,
        beats=list(proposal.beats),
    )
