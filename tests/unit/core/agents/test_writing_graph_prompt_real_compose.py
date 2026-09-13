"""Real-composer regression tests for the FO-8 / FO-10 latent compose raises.

Defect class: every WritingGraph prompt-builder test mocked
``PromptComposer``, so route-governance and route-variable mismatches were
invisible (masked-by-mocks). Both seams raised at real compose time in
production:

- FO-8: ``get_review_prompt`` composed ``LLMIntent.BETA_READ`` with
  ``mode="review"`` — BETA_READ allows only ``beta_reader`` /
  ``beta_reader_deepdive`` (route_table.py), so every real compose raised
  ``PromptRouteNotConfiguredError``. The governed route for the
  ``analysis/en/review`` template is ``ANALYSE`` + mode ``review``.
  Additionally the ANALYSE route declares no optional variables, so the
  KB-blind case (assembly yields None) needs the draft/revise convention:
  an empty ``WritingContext`` supplies every ``kb_*`` key as ``""``.
- FO-10: ``get_outline_prompt`` supplied none of the planning/outline
  template's demands — ``variant_count`` (route-required per
  MODE_REQUIRED_VARS) and ``kb_characters`` / ``kb_locations`` (PLAN
  declares no optional variables) — so every real compose raised
  ``PromptVariableError('variant_count')``.

The fixes under test: FO-8 routes ANALYSE with the KB-blind fallback; FO-10
supplies ``variant_count=1`` (the graph plans a single outline — the
template's documented default) plus the kb set via
``assemble_writing_context`` / ``enrich_prompt_context_with_kb``.

All tests in this module compose through the REAL ``PromptComposer`` +
``PromptRegistry`` — no composer mocks.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from narrare_core.agents.writing_graph_prompts import (
    get_outline_prompt,
    get_review_prompt,
)
from narrare_core.agents.writing_graph_types import WritingDeps, WritingState
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.writing.models import WritingContext

# Distinctive markers of the two candidate templates on the review path.
_REVIEW_TEMPLATE_MARKER = "professional writing critic and editor"
_BETA_READER_TEMPLATE_MARKER = "experienced beta reader"

_CH_ID = "550e8400-e29b-41d4-a716-446655440000"
_NOVEL_ID = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"


def _real_composer() -> PromptComposer:
    return PromptComposer(PromptRegistry())


def _deps(**overrides: Any) -> WritingDeps:
    defaults: dict[str, Any] = {
        "registry": AsyncMock(),
        "composer": _real_composer(),
        "genre": "Fantasy",
        "tone": "epic",
        "word_target": 2000,
        "writing_language": "English",
    }
    defaults.update(overrides)
    return WritingDeps(**defaults)


def _state(**overrides: Any) -> WritingState:
    defaults: dict[str, Any] = {"draft": "Elena crossed the flooded bridge at dawn."}
    defaults.update(overrides)
    return WritingState(**defaults)


def _assembler_returning(context: WritingContext) -> AsyncMock:
    assembler = AsyncMock()
    assembler.assemble = AsyncMock(return_value=context)
    return assembler


class TestReviewPromptRealCompose:
    """FO-8: get_review_prompt composes on the governed ANALYSE/review route."""

    async def test_review_prompt_composes_on_analyse_route_without_assembler(
        self,
    ) -> None:
        """Regression FO-8: real compose must not raise.

        Pre-fix this raised ``PromptRouteNotConfiguredError`` (BETA_READ
        forbids mode="review"); the routed template is now the governed
        analysis/en/review one — not the beta_reader template.
        """
        system, _, writing_ctx = await get_review_prompt(
            composer=_deps().composer,
            deps=_deps(),
            state=_state(),
        )
        assert writing_ctx is None
        assert _REVIEW_TEMPLATE_MARKER in system, "governed review template not routed"
        assert _BETA_READER_TEMPLATE_MARKER not in system, "BETA_READ template leaked"
        assert "{{" not in system, "placeholder residue in render"

    async def test_review_prompt_kb_blind_fallback_renders_kb_section(self) -> None:
        """ANALYSE declares no optionals: with no assembler the empty
        WritingContext fallback supplies every kb_* key so the Knowledge
        Base section renders empty instead of raising PromptVariableError."""
        system, _, _ = await get_review_prompt(
            composer=_deps().composer,
            deps=_deps(),
            state=_state(),
        )
        assert "### Knowledge Base" in system
        assert "{{kb_" not in system

    async def test_review_prompt_enriched_kb_reaches_render(self) -> None:
        """With a wired assembler the KB data flows into the render and the
        assembled context is returned for ReviewDeps."""
        writing_ctx = WritingContext(
            kb_characters="### Character: Elena\nWarrior queen",
            kb_relationships="- Elena <-> Mara: sisters",
        )
        deps = _deps(
            context_assembler=_assembler_returning(writing_ctx),
        )
        state = _state(chapter_id=_CH_ID, novel_id=_NOVEL_ID)
        system, _, returned_ctx = await get_review_prompt(
            composer=deps.composer,
            deps=deps,
            state=state,
        )
        assert returned_ctx is writing_ctx
        assert "### Character: Elena" in system
        assert "- Elena <-> Mara: sisters" in system
        assert "{{" not in system

    async def test_review_prompt_composes_when_assembler_fails(self) -> None:
        """Assembly failure degrades gracefully: warn + KB-blind compose."""
        assembler = AsyncMock()
        assembler.assemble = AsyncMock(side_effect=RuntimeError("DB lost"))
        deps = _deps(context_assembler=assembler)
        state = _state(chapter_id=_CH_ID, novel_id=_NOVEL_ID)
        system, _, writing_ctx = await get_review_prompt(
            composer=deps.composer,
            deps=deps,
            state=state,
        )
        assert writing_ctx is None
        assert _REVIEW_TEMPLATE_MARKER in system
        assert "{{" not in system


class TestOutlinePromptRealCompose:
    """FO-10: get_outline_prompt supplies variant_count + the kb set."""

    async def test_outline_prompt_composes_with_variant_count_without_assembler(
        self,
    ) -> None:
        """Regression FO-10: real compose must not raise.

        Pre-fix this raised ``PromptVariableError('variant_count')``; the
        single-outline default renders as ``Variant count: 1``.
        """
        system, _ = await get_outline_prompt(
            composer=_deps().composer,
            deps=_deps(),
            state=_state(),
        )
        assert "story outlining specialist" in system
        assert "Variant count: 1" in system, "variant_count default not rendered"
        assert "{{" not in system, "placeholder residue in render"

    async def test_outline_prompt_enriched_kb_reaches_render(self) -> None:
        """With a wired assembler the kb_characters demand renders curated
        KB data instead of an empty placeholder."""
        deps = _deps(
            context_assembler=_assembler_returning(
                WritingContext(kb_characters="### Character: Elena\nWarrior queen"),
            ),
        )
        state = _state(chapter_id=_CH_ID, novel_id=_NOVEL_ID)
        system, _ = await get_outline_prompt(
            composer=deps.composer,
            deps=deps,
            state=state,
        )
        assert "### Character: Elena" in system
        assert "Variant count: 1" in system
        assert "{{" not in system

    async def test_outline_prompt_composes_when_assembler_fails(self) -> None:
        """Assembly failure degrades gracefully: warn + KB-blind compose."""
        assembler = AsyncMock()
        assembler.assemble = AsyncMock(side_effect=RuntimeError("DB lost"))
        deps = _deps(context_assembler=assembler)
        state = _state(chapter_id=_CH_ID, novel_id=_NOVEL_ID)
        system, _ = await get_outline_prompt(
            composer=deps.composer,
            deps=deps,
            state=state,
        )
        assert "Variant count: 1" in system
        assert "{{" not in system
