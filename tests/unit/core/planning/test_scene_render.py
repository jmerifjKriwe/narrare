"""Unit tests for the scene prompt renderer (PLAN-001, spec §6.3 golden format)."""

from __future__ import annotations

from uuid import uuid4

from narrare_core.planning.models import ScenePlanData, ScenePresence
from narrare_core.planning.scene_render import render_scene_for_prompt
from narrare_core.writing.requests import SceneSpec

GOLDEN_FULL = "\n".join(
    [
        "Scene 2: The Ambush at the Gate",
        "POV: John Smith",
        "Location: The Castle",
        "Characters: John Smith (wants to warn the guard); Mara (wants to stop him)",
        "Purpose: John must reach the gate before dawn.",
        "Conflict: Mara blocks the path; loyalty vs duty.",
        "Resolution: John talks his way past but at a cost.",
        "Beats:",
        "  1. John reaches the gate",
        "  2. Mara confronts him",
        "  3. The horn sounds",
    ]
)


def _full_scene() -> ScenePlanData:
    return ScenePlanData(
        id=uuid4(),
        position=2,
        title="The Ambush at the Gate",
        pov_character_name="John Smith",
        location_name="The Castle",
        present_characters=(
            ScenePresence(name="John Smith", goal="wants to warn the guard"),
            ScenePresence(name="Mara", goal="wants to stop him"),
        ),
        purpose="John must reach the gate before dawn.",
        conflict="Mara blocks the path; loyalty vs duty.",
        resolution="John talks his way past but at a cost.",
        beats=("John reaches the gate", "Mara confronts him", "The horn sounds"),
    )


class TestRenderSceneForPrompt:
    def test_full_scene_renders_spec_golden_block(self) -> None:
        assert render_scene_for_prompt(_full_scene(), number=2) == GOLDEN_FULL

    def test_empty_sections_are_omitted(self) -> None:
        scene = ScenePlanData(id=uuid4(), position=1, title="Only a title")
        assert render_scene_for_prompt(scene, number=1) == "Scene 1: Only a title"

    def test_partial_scene_omits_only_empty_sections(self) -> None:
        scene = ScenePlanData(
            id=uuid4(),
            position=3,
            title="The Quiet Field",
            location_name="The Meadow",
            purpose="A moment of rest.",
        )
        assert (
            render_scene_for_prompt(scene, number=3)
            == "Scene 3: The Quiet Field\nLocation: The Meadow\nPurpose: A moment of rest."
        )

    def test_empty_beats_omit_beats_header(self) -> None:
        scene = ScenePlanData(id=uuid4(), position=1, title="No beats", purpose="p", beats=())
        assert render_scene_for_prompt(scene, number=1) == ("Scene 1: No beats\nPurpose: p")

    def test_number_none_omits_scene_prefix(self) -> None:
        scene = ScenePlanData(id=uuid4(), position=7, title="Untitled header")
        assert render_scene_for_prompt(scene) == "Untitled header"

    def test_number_none_keeps_remaining_sections(self) -> None:
        scene = ScenePlanData(id=uuid4(), position=7, title="Headerless", pov_character_name="Mara")
        assert render_scene_for_prompt(scene) == "Headerless\nPOV: Mara"

    def test_presences_render_goal_only_with_goal(self) -> None:
        scene = ScenePlanData(
            id=uuid4(),
            position=1,
            title="T",
            present_characters=(ScenePresence(name="Mara"),),
        )
        assert render_scene_for_prompt(scene, number=1) == ("Scene 1: T\nCharacters: Mara")

    def test_presences_mix_goal_and_no_goal(self) -> None:
        scene = ScenePlanData(
            id=uuid4(),
            position=1,
            title="T",
            present_characters=(
                ScenePresence(name="Mara", goal="wants to stop him"),
                ScenePresence(name="John Smith"),
            ),
        )
        assert render_scene_for_prompt(scene, number=1) == (
            "Scene 1: T\nCharacters: Mara (wants to stop him); John Smith"
        )


class TestRenderSceneForPromptSpecInput:
    """The renderer accepts writing's SceneSpec (pair presences) structurally."""

    def test_spec_renders_identical_golden_block(self) -> None:
        spec = SceneSpec(
            title="The Ambush at the Gate",
            pov_character_name="John Smith",
            location_name="The Castle",
            present_characters=(
                ("John Smith", "wants to warn the guard"),
                ("Mara", "wants to stop him"),
            ),
            purpose="John must reach the gate before dawn.",
            conflict="Mara blocks the path; loyalty vs duty.",
            resolution="John talks his way past but at a cost.",
            beats=("John reaches the gate", "Mara confronts him", "The horn sounds"),
        )
        assert render_scene_for_prompt(spec, number=2) == GOLDEN_FULL

    def test_spec_presences_as_pairs_goal_and_no_goal(self) -> None:
        spec = SceneSpec(
            title="T",
            present_characters=(("Mara", "wants to stop him"), ("John Smith", "")),
        )
        assert render_scene_for_prompt(spec, number=1) == (
            "Scene 1: T\nCharacters: Mara (wants to stop him); John Smith"
        )

    def test_spec_empty_sections_omitted_and_number_none(self) -> None:
        spec = SceneSpec(title="Only a title", purpose="p")
        assert render_scene_for_prompt(spec) == "Only a title\nPurpose: p"

    def test_spec_and_plan_data_render_byte_identical(self) -> None:
        plan = _full_scene()
        spec = SceneSpec(
            title=plan.title,
            pov_character_name=plan.pov_character_name,
            location_name=plan.location_name,
            present_characters=tuple((p.name, p.goal) for p in plan.present_characters),
            purpose=plan.purpose,
            conflict=plan.conflict,
            resolution=plan.resolution,
            beats=plan.beats,
        )
        assert render_scene_for_prompt(spec, number=5) == render_scene_for_prompt(plan, number=5)
