"""Tests for PromptContext.as_variables() — KB entry formatting edge-cases.

Covers context.py line 154, 173-178 (kb entries with data) and
line 174 (empty entries guard in _format_kb_entries).
"""

from __future__ import annotations

from narrare_core.prompts.context import KBContextEntry, PromptContext


class TestPromptContextKbEntries:
    """Cover _format_kb_entries path in as_variables()."""

    def test_as_variables_with_kb_entries_formats_readable_block(self) -> None:
        entries = [
            KBContextEntry(entity_type="character", name="Alice", content="A brave warrior."),
            KBContextEntry(entity_type="location", name="Dark Forest", content="Spooky woods."),
        ]
        ctx = PromptContext(language="en", kb_context_entries=entries)

        variables = ctx.as_variables()

        assert "### Character: Alice" in variables["kb_context_entries"]
        assert "A brave warrior." in variables["kb_context_entries"]
        assert "### Location: Dark Forest" in variables["kb_context_entries"]
        assert "Spooky woods." in variables["kb_context_entries"]

    def test_as_variables_with_empty_kb_entries_returns_empty(self) -> None:
        ctx = PromptContext(language="en", kb_context_entries=[])
        variables = ctx.as_variables()
        # Empty list → not isinstance(KBContextEntry) → falls to join path
        assert variables["kb_context_entries"] == ""

    def test_format_kb_entries_static_method_with_empty_list(self) -> None:
        """Cover line 174 — the empty guard in _format_kb_entries."""
        result = PromptContext._format_kb_entries([])
        assert result == ""
