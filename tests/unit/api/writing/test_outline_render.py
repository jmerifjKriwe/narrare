"""Golden tests for the story-suggest ``chapter_outline`` renderer.

PLAN-001 T15 (ADR-096, spec §7): the ``chapter_outline`` slot renders
stage + numbered scene blocks (via Core's shared
:func:`render_scene_for_prompt`, spec §6.3) + notes. The legacy beat
outline section is replaced by per-scene blocks; the beat column is gone
(Alembic 0049).

See:
    docs/superpowers/specs/2026-10-09-plan001-scene-planning-design.md §6.3/§7
"""

from __future__ import annotations

import uuid

from narrare.planning.models import ChapterOutline
from narrare.writing._outline_render import render_chapter_outline
from tests.factories import make_scene_plan


def _outline(*, stage: str = "", notes: str = "") -> ChapterOutline:
    return ChapterOutline(
        id=uuid.uuid4(),
        chapter_id=uuid.uuid4(),
        stage_assignment=stage,
        outline_notes=notes,
    )


class TestRenderChapterOutlineScenes:
    def test_renders_stage_numbered_scene_blocks_and_notes(self) -> None:
        outline = _outline(stage="act-1", notes="Establish tension early.")
        scenes = [
            make_scene_plan(
                position=1,
                title="The Ambush at the Gate",
                pov_character_ref={"id": "p1", "name": "John Smith"},
                location_ref={"id": "l1", "name": "The Castle"},
                present_characters=[{"name": "Mara", "goal": "stop him"}],
                purpose="John must reach the gate before dawn.",
                beats=["John reaches the gate", "Mara confronts him"],
            ),
            make_scene_plan(
                position=2,
                title="The Horn Sounds",
                purpose="Reinforcements arrive too late.",
            ),
        ]

        rendered = render_chapter_outline(outline, scenes)

        lines = rendered.splitlines()
        assert lines[0] == "Stage: act-1"
        # Numbered scene blocks in list order (spec §6.3 block format).
        assert "Scene 1: The Ambush at the Gate" in lines
        assert "POV: John Smith" in lines
        assert "Location: The Castle" in lines
        assert "Characters: Mara (stop him)" in lines
        assert "Purpose: John must reach the gate before dawn." in lines
        assert "Beats:" in lines
        assert "  1. John reaches the gate" in lines
        assert "  2. Mara confronts him" in lines
        assert "Scene 2: The Horn Sounds" in lines
        assert "Purpose: Reinforcements arrive too late." in lines
        assert lines[-1] == "Notes: Establish tension early."

    def test_beat_json_is_no_longer_rendered(self) -> None:
        """The beats section is REPLACED by per-scene blocks (spec §7):
        only stage, scene blocks, and notes ever reach the prompt slot."""
        outline = _outline(stage="act-1", notes="Notes.")

        rendered = render_chapter_outline(outline, [])

        assert rendered == "Stage: act-1\nNotes: Notes."

    def test_empty_scenes_renders_stage_and_notes_only(self) -> None:
        rendered = render_chapter_outline(_outline(stage="act-2", notes="Keep it tight."), [])
        assert rendered == "Stage: act-2\nNotes: Keep it tight."

    def test_empty_sections_are_omitted(self) -> None:
        scene = make_scene_plan(title="Only a title")
        rendered = render_chapter_outline(_outline(), [scene])
        assert rendered == "Scene 1: Only a title"

    def test_no_content_at_all_renders_empty_string(self) -> None:
        assert render_chapter_outline(_outline(), []) == ""


class TestRenderChapterOutlineWithoutOutlineRow:
    """FU-f (T15 follow-up): scene plans persist independently of the
    outline row (ADR-096), so the renderer accepts ``outline=None`` and
    emits the scene blocks alone — stage/notes require the outline row."""

    def test_none_outline_renders_scene_blocks_only(self) -> None:
        scene = make_scene_plan(
            position=1,
            title="The Ambush at the Gate",
            purpose="Lyra must slip past the guard before dawn.",
        )

        rendered = render_chapter_outline(None, [scene])

        # Scene block renders in full (renderer shape, spec §6.3); the
        # outline-only sections cannot (no outline row).
        assert "Scene 1: The Ambush at the Gate" in rendered
        assert "Purpose: Lyra must slip past the guard before dawn." in rendered
        assert "Stage:" not in rendered
        assert "Notes:" not in rendered

    def test_none_outline_with_no_scenes_renders_empty_string(self) -> None:
        assert render_chapter_outline(None, []) == ""
