"""Slice 1 — scene_by_scene word-target label-in-value render tests.

Defect (same class as the review-route Item F fix, commit ``73aca18c``):
the ``writing/en/scene_by_scene`` template carried a static label line
``Word target per scene: {{word_target}}`` — an empty supplier value
rendered a dangling ``Word target per scene: `` label into the scene
system prompt.

Fix design (Tier-5 / ADR-050 P1-D ``optional_block`` precedent,
label-in-value): the label moves into the VALUE. The template appends
``{{word_target_line}}`` to the previous Instructions line (null new
template lines → byte-identical empty renders) and the supplier
(``WritingPipeline._build_prompt_context``, scene_by_scene mode-branch)
builds the full line via ``narrare_core.writing._helpers.word_target_line``
— ``""`` when no target is set, ``"\\nWord target per scene: N"`` when
populated (pipeline wiring covered in
``test_tier5_injection_scene_wiring.py``).

All renders compose through the REAL ``PromptComposer`` + ``PromptRegistry``
(no composer mocks), mirroring ``test_tier5_injection_scene.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from narrare_core.llm import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.shared.frontmatter import parse_frontmatter
from narrare_core.writing._helpers import word_target_line

_SCENE_TEMPLATE_PATH = (
    Path(__file__).parents[4]
    / "packages"
    / "core"
    / "narrare_core"
    / "prompts"
    / "_bundled"
    / "writing"
    / "en"
    / "scene_by_scene"
    / "system.md"
)

_SCENE_LABEL = "Word target per scene: "


def _scene_context(word_target_line_value: str) -> PromptContext:
    """WRITE/scene_by_scene context mirroring the pipeline's scene extras.

    Mirrors ``WritingPipeline._build_prompt_context`` as invoked by
    ``stream_scene_by_scene`` (see ``test_tier5_injection_scene.py``),
    with the slice-1 mode-branch: ``word_target_line`` (label-in-value)
    instead of the bare ``word_target`` number the static template label
    consumed.
    """
    return PromptContext(
        language="en",
        writing_language="English",
        project_title="Test Novel",
        genre="fantasy",
        tone="balanced",
        mode="scene_by_scene",
        existing_content="",
        author_instructions="The bridge at night, rain on the river.",
        user_preferences="Concise prose.",
        avoidance_patterns="Cliches.",
        cross_session_context="",
        character_voice_profiles="Elena: formal, terse.",
        author_voice="Lyrical, close third person.",
        extra={
            "user_id": "00000000-0000-0000-0000-000000000001",
            "project_id": "00000000-0000-0000-0000-000000000002",
            "chapter_outline": "Bridge chapter in two scenes.",
            "kb_characters": "",
            "kb_locations": "",
            "recent_chapters": "",
            "character_voice_profiles": "Elena: formal, terse.",
            "author_voice": "Lyrical, close third person.",
            "series_history": "",
            "word_target_line": word_target_line_value,
            # TONE_INSTRUCTIONS["balanced"] == "" (faithful to the default path)
            "tone_instructions": "",
            "writing_language": "English",
            "scene_number": "1",
            "total_scenes": "2",
        },
    )


class TestWordTargetLineHelper:
    """The promoted label-in-value helper (supplier-side formatting SSOT)."""

    def test_empty_value_renders_empty_string(self) -> None:
        assert word_target_line(None, label=_SCENE_LABEL) == ""

    def test_zero_value_renders_empty_string(self) -> None:
        """``0`` is falsy for target purposes ("doesn't use word targets")
        and must not render a ``0`` line."""
        assert word_target_line(0, label=_SCENE_LABEL) == ""

    def test_populated_value_renders_leading_newline_line(self) -> None:
        # Leading "\n" is the Tier-5 append-to-previous-line convention:
        # the placeholder sits at the end of the previous template line, so
        # an empty value renders byte-identically to a template without the
        # line at all (no blank line, no dangling label).
        assert word_target_line(1500, label=_SCENE_LABEL) == "\nWord target per scene: 1500"


class TestScenePromptWordTargetRender:
    """Empty target → no label anywhere; populated → exactly one full line."""

    async def test_empty_word_target_renders_no_label(self) -> None:
        """Regression (slice 1): an unset word target must not leave a
        dangling ``Word target per scene: `` label in the composed scene
        system prompt."""
        composer = PromptComposer(PromptRegistry())
        result = await composer.build(LLMIntent.WRITE, _scene_context(""))

        assert "Word target per scene" not in result.system, "dangling word-target label in render"
        assert "{{" not in result.system, "placeholder residue in render"

    async def test_populated_word_target_renders_label_line_once(self) -> None:
        """Populated render is byte-stable: the appended value reproduces the
        pre-migration line layout exactly (``Author instructions: …`` line,
        then the word-target line), exactly once."""
        composer = PromptComposer(PromptRegistry())
        result = await composer.build(
            LLMIntent.WRITE,
            _scene_context(word_target_line(1500, label=_SCENE_LABEL)),
        )

        assert result.system.count("Word target per scene: 1500") == 1
        assert "</user_instructions>\nWord target per scene: 1500\nTone: " in result.system


@pytest.mark.mutation_inert
class TestSceneTemplateSurface:
    """Template-level guards against regressing to a static label line."""

    def test_template_has_no_static_word_target_label(self) -> None:
        template = _SCENE_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Word target per scene: {{" not in template, (
            "static label line reintroduced — label belongs in the supplier value"
        )

    def test_template_references_word_target_line_variable(self) -> None:
        template = _SCENE_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "{{word_target_line}}" in template

    def test_prompt_version_bumped_to_1_7_0(self) -> None:
        """Slice 1 (word-target label-in-value) bumps 1.6.0 → 1.7.0."""
        parsed = parse_frontmatter(_SCENE_TEMPLATE_PATH.read_text(encoding="utf-8"))
        assert parsed.metadata.get("prompt_version") == "1.7.0"
