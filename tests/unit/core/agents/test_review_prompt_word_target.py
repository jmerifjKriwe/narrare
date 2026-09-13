"""Item F — review-path word-target label-in-value render tests.

Defect: the analysis/en/review template carried a static label bullet
``- Word target: {{word_target}}`` — an empty supplier value rendered a
dangling ``- Word target: `` label into the review system prompt.

Fix design (established root-cause pattern, Tier-5 / ADR-050 P1-D
``optional_block`` precedent): the label moves into the VALUE. The template
appends ``{{word_target_line}}`` to the previous Context bullet (null new
template lines → byte-identical empty renders) and the supplier
(``get_review_prompt``) builds the full line — ``""`` when no target is set,
``"\\n- Word target: N"`` when populated.

All renders compose through the REAL ``PromptComposer`` + ``PromptRegistry``
(no composer mocks), mirroring test_writing_graph_prompt_real_compose.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from narrare_core.agents.writing_graph_prompts import (
    _word_target_line,
    get_review_prompt,
)
from narrare_core.agents.writing_graph_types import WritingDeps, WritingState
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry

_REVIEW_TEMPLATE_PATH = (
    Path(__file__).parents[4]
    / "packages"
    / "core"
    / "narrare_core"
    / "prompts"
    / "_bundled"
    / "analysis"
    / "en"
    / "review"
    / "system.md"
)

_REVIEW_LABEL = "- Word target: "


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


class TestWordTargetLineHelper:
    """The tiny label-in-value helper (supplier-side formatting SSOT)."""

    def test_empty_value_renders_empty_string(self) -> None:
        assert _word_target_line(None, label=_REVIEW_LABEL) == ""

    def test_populated_value_renders_leading_newline_line(self) -> None:
        # Leading "\n" is the Tier-5 append-to-previous-line convention:
        # the placeholder sits at the end of the previous template line, so
        # an empty value renders byte-identically to a template without the
        # line at all (no blank line, no dangling label).
        assert _word_target_line(1500, label=_REVIEW_LABEL) == "\n- Word target: 1500"


class TestReviewPromptWordTargetRender:
    """Empty target → no label anywhere; populated → exactly one full line."""

    async def test_empty_word_target_renders_no_label(self) -> None:
        """Regression (Item F): None word_target must not leave a dangling
        ``- Word target: `` bullet in the composed review system prompt."""
        system, _, _ = await get_review_prompt(
            composer=_real_composer(),
            deps=_deps(word_target=None),
            state=_state(),
            word_count=6,
        )
        assert "Word target" not in system, "dangling word-target label in render"
        assert "{{" not in system, "placeholder residue in render"

    async def test_populated_word_target_renders_label_line_once(self) -> None:
        """Populated render is byte-stable: the appended value reproduces the
        pre-fix bullet layout exactly (``- Language: …`` then the word-target
        bullet), exactly once."""
        system, _, _ = await get_review_prompt(
            composer=_real_composer(),
            deps=_deps(word_target=1500),
            state=_state(),
            word_count=6,
        )
        assert system.count("- Word target: 1500") == 1
        assert "- Language: English\n- Word target: 1500\n" in system

    async def test_zero_word_target_renders_no_label(self) -> None:
        """``0`` is falsy for target purposes (co-author/rewrite convention:
        "doesn't use word targets") and must not render a ``0`` bullet."""
        system, _, _ = await get_review_prompt(
            composer=_real_composer(),
            deps=_deps(word_target=0),
            state=_state(),
            word_count=6,
        )
        assert "Word target" not in system


@pytest.mark.mutation_inert
class TestReviewTemplateSurface:
    """Template-level guards against regressing to a static label line."""

    def test_template_has_no_static_word_target_label(self) -> None:
        template = _REVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Word target: {{" not in template, (
            "static label line reintroduced — label belongs in the supplier value"
        )

    def test_template_references_word_target_line_variable(self) -> None:
        template = _REVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "{{word_target_line}}" in template
