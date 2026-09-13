"""Slice 2 / final-prune split — revise-path word-target label-in-value tests.

Split out of ``test_revise_prompt_kb_enrichment.py`` (RULE-04): the
``TestRevisePromptWordTargetNone`` class moved here byte-identical; the
KB goldens and builders stay single-sourced in the KB module and are
imported (no golden duplication).

Slice 2 (2026-09-13): the revise path supplies the word target as the
full label-in-value line (``word_target_line``, shared
``writing._helpers.word_target_line`` helper) instead of the bare
``word_target`` number the new_chapter template's former static label
line demanded.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from narrare_core.agents.writing_graph_prompts import get_revise_prompt
from narrare_core.prompts.composer import ComposedPrompt, PromptComposer
from narrare_core.prompts.registry import PromptRegistry
from tests.unit.core.agents.test_revise_prompt_kb_enrichment import (
    _GOLDEN_KB_EMPTY_SYSTEM,
    _GOLDEN_KB_EMPTY_USER,
    _make_deps,
    _make_state,
)


class TestRevisePromptWordTargetNone:
    """Slice 2: word_target=None renders no word-target line at all.

    FO-3 supplied the bare key unconditionally on this REWRITE →
    new_chapter context-mode override (None → empty value under the
    STATIC label). Slice 2 moves the label into the value
    (``{{word_target_line}}`` via ``writing._helpers.word_target_line``):
    None → ``""`` → NO label line; populated reproduces the former
    static-label layout byte-for-byte.
    """

    async def test_revise_without_word_target_composes_rendering_no_label(self) -> None:
        """Real composer: None → no raise; the whole label line is absent."""
        composer = PromptComposer(PromptRegistry())
        system, user = await get_revise_prompt(
            composer, _make_deps(composer, word_target=None), _make_state()
        )
        # Explicit pin: the KB-empty golden family with the whole
        # "Word target: 1500" line removed (label-in-value renders ""
        # → no dangling label, no blank line).
        assert system == _GOLDEN_KB_EMPTY_SYSTEM.replace("\nWord target: 1500\n", "\n")
        assert "Word target" not in system
        assert user == _GOLDEN_KB_EMPTY_USER

    async def test_revise_without_word_target_supplies_empty_line(self) -> None:
        """Wiring: None → extra["word_target_line"] == ""; bare key gone."""
        composer = AsyncMock()
        composer.build = AsyncMock(return_value=ComposedPrompt(system="s", user="u"))
        await get_revise_prompt(composer, _make_deps(composer, word_target=None), _make_state())
        captured = composer.build.call_args.args[1]
        assert captured.extra["word_target_line"] == ""
        assert "word_target" not in captured.extra
