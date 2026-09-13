"""Scene numbering — item-3 render tests for the scene_by_scene template.

Split from ``test_tier5_injection_scene.py`` (RULE-04): that file holds the
Tier-5 empty-tiers golden baseline; appending the item-3 numbering tests
pushed it past the 400-line hard limit — same separate-file precedent as the
T1d/T1e/T1f slices documented there.

Invariant under test
--------------------
The WRITE/scene_by_scene template (prompt_version 1.5.0) renders the scene
numbering line ``Scene {{scene_number}} of {{total_scenes}}.`` from the
scene-position extras that ``stream_scene_by_scene`` (pipeline_scene.py)
supplies via ``extra_overrides``. Before item-3 both values were silently
dropped — the template had no placeholders and the vars were unregistered
(SYSTEM_VARS since item-3).
"""

from __future__ import annotations

from narrare_core.llm import LLMIntent
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.context import PromptContext
from narrare_core.prompts.registry import PromptRegistry


class TestSceneNumberingLine:
    """The numbering line renders the supplied scene position."""

    async def test_numbering_line_renders_supplied_position(self) -> None:
        """A 3-of-7 compose renders 'Scene 3 of 7.' after the task statement."""
        composer = PromptComposer(PromptRegistry())
        result = await composer.build(
            LLMIntent.WRITE,
            PromptContext(
                language="en",
                mode="scene_by_scene",
                extra={
                    "chapter_outline": "Bridge chapter in two scenes.",
                    # Route-required registered variables that are not in the
                    # WRITE route's optional set — "" mirrors the KB-empty
                    # compose the golden helper performs. Slice-1 word_target
                    # migration: the template renders {{word_target_line}}
                    # (label-in-value), not the bare {{word_target}} number.
                    "kb_characters": "",
                    "kb_locations": "",
                    "word_target_line": "",
                    "scene_number": "3",
                    "total_scenes": "7",
                },
            ),
        )

        assert "Scene 3 of 7." in result.system
        assert "{{scene_" not in result.system
        # Placement: the numbering sits between the task statement paragraph
        # and the culture-guidelines block (where the task is established).
        task_end = result.system.index("before continuing.")
        numbering = result.system.index("Scene 3 of 7.")
        assert task_end < numbering
        assert numbering < result.system.index("### Context")
