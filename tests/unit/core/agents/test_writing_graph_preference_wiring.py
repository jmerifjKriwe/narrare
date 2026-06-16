"""Tests for preference identity wiring in WritingDeps and _base_context().

CR-04 coherence fix: WritingDeps.user_id flows into PromptContext.extra
so that PromptComposer can auto-inject user preferences.

Test strategy:
- Pure unit tests — no I/O, no LLM, no DB.
- Tests verify _base_context populates extra["user_id"] and extra["project_id"]
  for preference auto-injection via PromptComposer.
- Coverage target: _base_context() in writing_graph_prompts.py > 95%.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from narrare_core.agents.writing_graph_prompts import _base_context
from narrare_core.agents.writing_graph_types import WritingDeps, WritingState

# CR-AUFG-02-07: WritingDeps.composer is required. These tests exercise
# _base_context only, so a placeholder mock is sufficient.
_COMPOSER: Any = AsyncMock()


def _deps(**overrides: Any) -> WritingDeps:
    """Build WritingDeps with a placeholder composer for _base_context tests."""
    return WritingDeps(registry=None, composer=_COMPOSER, **overrides)


class TestBaseContextPreferenceWiring:
    """Verify _base_context populates user_id and project_id in extra."""

    def test_no_user_id_empty_extra(self) -> None:
        """When user_id is not set, extra should not contain user_id."""
        deps = _deps()
        state = WritingState()
        ctx = _base_context(deps, state)
        assert "user_id" not in ctx.extra
        assert "project_id" not in ctx.extra

    def test_user_id_populated_in_extra(self) -> None:
        """When user_id is set, extra should contain it."""
        deps = _deps(user_id="user-123")
        state = WritingState()
        ctx = _base_context(deps, state)
        assert ctx.extra["user_id"] == "user-123"

    def test_novel_id_populated_in_extra(self) -> None:
        """When novel_id is in state, extra should contain project_id."""
        deps = _deps()
        state = WritingState(novel_id="novel-456")
        ctx = _base_context(deps, state)
        assert ctx.extra["project_id"] == "novel-456"

    def test_both_ids_populated(self) -> None:
        """Both user_id and project_id should appear when available."""
        deps = _deps(user_id="user-abc")
        state = WritingState(novel_id="novel-xyz")
        ctx = _base_context(deps, state)
        assert ctx.extra["user_id"] == "user-abc"
        assert ctx.extra["project_id"] == "novel-xyz"

    def test_empty_user_id_not_in_extra(self) -> None:
        """Empty string user_id should not be in extra (falsy check)."""
        deps = _deps(user_id="")
        state = WritingState(novel_id="novel-123")
        ctx = _base_context(deps, state)
        assert "user_id" not in ctx.extra
        assert ctx.extra["project_id"] == "novel-123"

    def test_other_fields_unchanged(self) -> None:
        """Adding user_id/project_id should not affect other context fields."""
        deps = _deps(
            user_id="u1",
            language="de",
            genre="Fantasy",
            tone="dark",
        )
        state = WritingState(novel_id="n1", outline="Test outline for checking")
        ctx = _base_context(deps, state)
        assert ctx.language == "de"
        assert ctx.genre == "Fantasy"
        assert ctx.tone == "dark"
        assert ctx.chapter_title == "Test outline for checking"
        assert ctx.extra["user_id"] == "u1"
        assert ctx.extra["project_id"] == "n1"
