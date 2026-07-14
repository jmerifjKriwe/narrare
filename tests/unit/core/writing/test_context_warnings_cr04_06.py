"""CR-AUFG-04-06: Surface dangling KB reference warnings into the prompt.

The orphan-reference detection already exists and is wired into
``WritingContext.orphan_reference_warnings`` (see test_context_assembler_cr04.py),
but ``to_prompt_variables()`` never promoted those warnings into a prompt
variable, so the LLM never saw them — dangling frontmatter references were
silently dropped at the prompt surface.

These tests verify the new ``kb_context_warnings`` variable:
1. Is produced by ``WritingContextAssembler.assemble`` from
   ``orphan_reference_warnings`` (each line prefixed with the
   ``⚠️ Context warning: `` marker; empty string when there are no orphans).
2. Is exposed by ``WritingContext.to_prompt_variables()``.
3. Actually reaches a composed prompt (verified via ``substitute()`` on a real
   bundled template) — not just the variables dict.
4. Is registered in ``SYSTEM_VARS`` so templates referencing it resolve without
   ``PromptVariableError`` (Prompt Surface Contract gate).
"""

from __future__ import annotations

import pytest
import yaml

from narrare_core.prompts.variable_engine import (
    prepare_variables_for_template,
    substitute,
)
from narrare_core.prompts.variable_registry import SYSTEM_VARS
from narrare_core.writing.context_assembler import WritingContextAssembler
from narrare_core.writing.context_models import KBEntity
from narrare_core.writing.models import WritingContext


def _entity(
    entity_id: str = "ent-1",
    entity_type: str = "character",
    name: str = "Alice",
) -> KBEntity:
    """Build a KBEntity with sensible defaults."""
    return KBEntity(
        entity_id=entity_id,
        entity_type=entity_type,
        name=name,
        content="A brave warrior.",
        similarity_score=0.5,
        frequency_score=0.5,
        recency_score=0.5,
    )


def _frontmatter(**fields: object) -> str:
    yaml_str = yaml.dump(dict(fields), default_flow_style=False)
    return f"---\n{yaml_str}---\n"


@pytest.fixture()
def assembler() -> WritingContextAssembler:
    return WritingContextAssembler(total_budget=6000)


# ---------------------------------------------------------------------------
# Prompt variable exposure
# ---------------------------------------------------------------------------


class TestKbContextWarningsVariableExposure:
    """kb_context_warnings is exposed as a prompt variable."""

    def test_kb_context_warnings_in_prompt_variables(self) -> None:
        ctx = WritingContext(kb_context_warnings="⚠️ Context warning: oops")
        variables = ctx.to_prompt_variables()
        assert "kb_context_warnings" in variables
        assert variables["kb_context_warnings"] == "⚠️ Context warning: oops"

    def test_kb_context_warnings_defaults_empty(self) -> None:
        ctx = WritingContext()
        assert ctx.kb_context_warnings == ""
        assert ctx.to_prompt_variables()["kb_context_warnings"] == ""


# ---------------------------------------------------------------------------
# Assembler population
# ---------------------------------------------------------------------------


class TestKbContextWarningsAssembly:
    """assemble() promotes orphan_reference_warnings into kb_context_warnings."""

    @pytest.mark.asyncio
    async def test_empty_when_no_orphans(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """No orphan references → kb_context_warnings is the empty string."""
        entities = [
            _entity("char-1", "character", "Alice"),
            _entity("loc-1", "location", "Castle"),
        ]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=_frontmatter(
                pov_character="char-1",
                characters=["char-1"],
                location="loc-1",
            ),
            kb_entities=entities,
        )
        assert ctx.orphan_reference_warnings == []
        assert ctx.kb_context_warnings == ""

    @pytest.mark.asyncio
    async def test_orphans_promoted_with_marker(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Orphan references produce prefixed, marker-bearing warning lines."""
        entities = [_entity("char-1", "character", "Alice")]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=_frontmatter(
                pov_character="char-1",
                characters=["char-1", "char-99", "loc-404"],
            ),
            kb_entities=entities,
        )
        # Detection still works (regression guard).
        assert len(ctx.orphan_reference_warnings) >= 1
        # Promoted to the prompt variable, non-empty.
        assert ctx.kb_context_warnings != ""
        # Every line carries the visible marker.
        for line in ctx.kb_context_warnings.split("\n"):
            assert line.startswith("⚠️ Context warning: ")
        # The orphan ids appear in the surfaced text.
        assert "char-99" in ctx.kb_context_warnings
        assert "loc-404" in ctx.kb_context_warnings

    @pytest.mark.asyncio
    async def test_multiple_orphans_joined_with_newlines(
        self,
        assembler: WritingContextAssembler,
    ) -> None:
        """Multiple orphan references join into multiple marked lines."""
        entities = [_entity("char-1", "character", "Alice")]
        ctx = await assembler.assemble(
            chapter_content="Content.",
            chapter_frontmatter=_frontmatter(
                pov_character="char-1",
                characters=["char-1", "a", "b", "c"],
            ),
            kb_entities=entities,
        )
        lines = ctx.kb_context_warnings.split("\n")
        assert len(lines) == len(ctx.orphan_reference_warnings)
        assert all(line.startswith("⚠️ Context warning: ") for line in lines)


# ---------------------------------------------------------------------------
# End-to-end: the warning actually reaches a composed prompt
# ---------------------------------------------------------------------------


class TestKbContextWarningsReachesPrompt:
    """The warning is visible in a substituted bundled template."""

    @staticmethod
    def _new_chapter_template() -> str:
        from tests.unit.core._bundled import bundled_prompts_root

        return (bundled_prompts_root() / "writing" / "en" / "new_chapter" / "system.md").read_text()

    def test_warning_text_present_when_orphans(self) -> None:
        ctx = WritingContext(
            kb_context_warnings=(
                "⚠️ Context warning: Frontmatter references entity 'char-99' "
                "which is not in the knowledge base or was excluded (deprecated)"
            ),
        )
        # strict=False isolates the variable under test: other template
        # placeholders (e.g. {{culture_guidelines}}) are left as-is rather
        # than raising, so we prove kb_context_warnings itself substitutes.
        rendered = substitute(
            self._new_chapter_template(),
            ctx.to_prompt_variables(),
            strict=False,
        )
        # The warning text reaches the composed prompt verbatim.
        assert "char-99" in rendered
        assert "⚠️ Context warning:" in rendered

    def test_no_warning_marker_when_clean(self) -> None:
        ctx = WritingContext()  # empty kb_context_warnings
        rendered = substitute(
            self._new_chapter_template(),
            ctx.to_prompt_variables(),
            strict=False,
        )
        assert "⚠️ Context warning:" not in rendered


# ---------------------------------------------------------------------------
# Variable registration (Prompt Surface Contract gate)
# ---------------------------------------------------------------------------


class TestKbContextWarningsRegistration:
    """kb_context_warnings is a registered, governed variable."""

    def test_registered_in_system_vars(self) -> None:
        assert "kb_context_warnings" in SYSTEM_VARS

    def test_template_reference_resolves_without_error(self) -> None:
        """A template referencing {{kb_context_warnings}} must not raise
        PromptVariableError during strict preflight."""
        template = "Notes:\n{{kb_context_warnings}}\nEnd."
        # Empty string is the canonical "no warnings" value and must pass.
        prepared = prepare_variables_for_template(
            template,
            {"kb_context_warnings": ""},
            prompt_id="test:new_chapter",
        )
        assert prepared["kb_context_warnings"] == ""
