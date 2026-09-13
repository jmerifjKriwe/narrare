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

Review-dangles fix (2026-09-13): the same label-in-value pattern covers the
LEADING Context bullets — the template's ``{{project_title}}`` /
``{{genre}}`` placeholders start a line, so the supplier builds the full
bullet (``"- Genre: Fantasy\\n"``) or ``""`` when unset; the former static
``- Project: `` / ``- Genre: `` labels dangled whenever the graph supplied
empty values (``_base_context`` hardcodes ``project_title=""`` and
``deps.genre`` defaults to ``""``). The dead ``word_count`` extra
(supplied-but-unrendered — no template placeholder) is removed together
with its parameter.

All renders compose through the REAL ``PromptComposer`` + ``PromptRegistry``
(no composer mocks), mirroring test_writing_graph_prompt_real_compose.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

from narrare_core.agents.writing_graph_prompts import get_review_prompt
from narrare_core.agents.writing_graph_types import WritingDeps, WritingState
from narrare_core.prompts.composer import PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.writing._helpers import word_target_line
from narrare_core.writing.models import WritingContext

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


class TestWordTargetLineHelper:
    """The shared label-in-value helper (supplier-side formatting SSOT).

    Slice 2 dedup: the review path's private ``_word_target_line`` twin
    was removed from ``writing_graph_prompts`` — all suppliers
    (pipeline / draft / revise / review) build the line through
    ``narrare_core.writing._helpers.word_target_line``.
    """

    def test_empty_value_renders_empty_string(self) -> None:
        assert word_target_line(None, label=_REVIEW_LABEL) == ""

    def test_populated_value_renders_leading_newline_line(self) -> None:
        # Leading "\n" is the Tier-5 append-to-previous-line convention:
        # the placeholder sits at the end of the previous template line, so
        # an empty value renders byte-identically to a template without the
        # line at all (no blank line, no dangling label).
        assert word_target_line(1500, label=_REVIEW_LABEL) == "\n- Word target: 1500"


class TestReviewPromptWordTargetRender:
    """Empty target → no label anywhere; populated → exactly one full line."""

    async def test_empty_word_target_renders_no_label(self) -> None:
        """Regression (Item F): None word_target must not leave a dangling
        ``- Word target: `` bullet in the composed review system prompt."""
        system, _, _ = await get_review_prompt(
            composer=_real_composer(),
            deps=_deps(word_target=None),
            state=_state(),
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
        )
        assert "Word target" not in system


class TestReviewContextBulletsRender:
    """Leading Context bullets are label-in-value — empty values cannot dangle.

    The graph's ``_base_context`` hardcodes ``project_title=""`` (no
    WritingDeps/state field carries a title) and ``deps.genre`` defaults to
    ``""`` — against the former static template labels both rendered
    dangling ``- Project: `` / ``- Genre: `` bullets. The supplier now
    builds the full bullet; an unset value renders the line away entirely.
    """

    async def test_empty_values_render_no_dangling_context_labels(self) -> None:
        """No assembler (title unreachable) + empty genre → neither Context
        bullet label appears; the Language bullet survives intact."""
        system, _, _ = await get_review_prompt(
            composer=_real_composer(),
            deps=_deps(genre="", word_target=None),
            state=_state(),
        )
        assert "- Project" not in system, "dangling project label in render"
        assert "- Genre" not in system, "dangling genre label in render"
        assert "- Language: English\n" in system
        assert "{{" not in system, "placeholder residue in render"

    async def test_populated_genre_renders_bullet_once(self) -> None:
        """Populated genre renders the full bullet exactly once, in the
        former layout position (before the Language bullet)."""
        system, _, _ = await get_review_prompt(
            composer=_real_composer(),
            deps=_deps(genre="Fantasy"),
            state=_state(),
        )
        assert system.count("- Genre: Fantasy") == 1
        assert "- Genre: Fantasy\n- Language: English" in system

    async def test_assembled_project_title_reaches_render_once(self) -> None:
        """Best-effort title source: the assembled WritingContext metadata
        tier's ``project_title`` (empty until the assembler populates it)
        renders as the full Project bullet exactly once."""
        writing_ctx = WritingContext(project_title="The Thornwall Echoes")
        assembler = AsyncMock()
        assembler.assemble = AsyncMock(return_value=writing_ctx)
        system, _, _ = await get_review_prompt(
            composer=_real_composer(),
            deps=_deps(context_assembler=assembler),
            state=_state(chapter_id=_CH_ID, novel_id=_NOVEL_ID),
        )
        assert system.count("- Project: The Thornwall Echoes") == 1
        assert "- Project: The Thornwall Echoes\n- Genre: Fantasy" in system


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

    def test_template_has_no_static_project_or_genre_labels(self) -> None:
        template = _REVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "- Project: {{" not in template, (
            "static Project label reintroduced — label belongs in the supplier value"
        )
        assert "- Genre: {{" not in template, (
            "static Genre label reintroduced — label belongs in the supplier value"
        )

    def test_template_references_project_and_genre_variables(self) -> None:
        template = _REVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "{{project_title}}" in template
        assert "{{genre}}" in template
