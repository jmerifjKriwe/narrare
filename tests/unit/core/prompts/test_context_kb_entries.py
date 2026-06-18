"""Tests for PromptContext.as_variables() — KB entry formatting edge-cases.

Covers context.py line 154, 173-178 (kb entries with data) and
line 174 (empty entries guard in _format_kb_entries).

C2a migration (ADR-050 P1-A — CR-AUFG-04-01): ``_format_kb_entries``
now returns :class:`RenderedKBContext` with provenance accounting.
These tests verify:

1. **Return type**: result is ``RenderedKBContext``.
2. **No prompt regression**: the wire-format text is byte-for-byte
   identical to the pre-C2a output.
3. **Provenance accounting**: all available provenance fields are
   explicitly omitted with a documented ``OmissionReason`` (the
   compact immediate-context format carries none of them).
4. **No metadata leak**: the variables dict carries only text —
   ``preserved_fields`` / ``omitted_fields`` never reach the prompt.
5. **Edge cases**: empty entries, full-provenance entries.
"""

from __future__ import annotations

from narrare_core.context._kb_envelope import (
    OmissionReason,
    ProvenanceField,
    RenderedKBContext,
)
from narrare_core.prompts.context import KBContextEntry, PromptContext

# Regression baseline — mirrors the EXACT pre-C2a wire format.
# If any assertion against this string fails, the prompt-visible text
# changed (a regression). Do NOT "fix" this string; fix the renderer.
_EXPECTED_STANDARD_TEXT = (
    "### Character: Alice\nA brave warrior.\n\n### Location: Dark Forest\nSpooky woods."
)


class TestPromptContextKbEntries:
    """Cover _format_kb_entries path in as_variables()."""

    def test_as_variables_with_kb_entries_formats_readable_block(self) -> None:
        """REGRESSION: the prompt-visible text must not change (C2a)."""
        entries = [
            KBContextEntry(entity_type="character", name="Alice", content="A brave warrior."),
            KBContextEntry(entity_type="location", name="Dark Forest", content="Spooky woods."),
        ]
        ctx = PromptContext(language="en", kb_context_entries=entries)

        variables = ctx.as_variables()

        # The variable value is the rendered text — provenance accounting
        # is metadata on RenderedKBContext and MUST NOT leak into the prompt.
        assert variables["kb_context_entries"] == _EXPECTED_STANDARD_TEXT

    def test_as_variables_with_empty_kb_entries_returns_empty(self) -> None:
        ctx = PromptContext(language="en", kb_context_entries=[])
        variables = ctx.as_variables()
        # Empty list → not isinstance(KBContextEntry) → falls to join path
        assert variables["kb_context_entries"] == ""

    def test_format_kb_entries_static_method_with_empty_list(self) -> None:
        """Empty input → RenderedKBContext with empty text, zero entries."""
        result = PromptContext._format_kb_entries([])
        assert isinstance(result, RenderedKBContext)
        assert result.text == ""
        assert result.entry_count == 0


class TestFormatKbEntriesReturnsRenderedKBContext:
    """C2a: _format_kb_entries returns RenderedKBContext (ADR-050 P1-A)."""

    def test_returns_rendered_kb_context_type(self) -> None:
        entries = [KBContextEntry(entity_type="character", name="Alice", content="Brave.")]
        result = PromptContext._format_kb_entries(entries)
        assert isinstance(result, RenderedKBContext)

    def test_text_matches_pre_c2a_wire_format_single_entry(self) -> None:
        """REGRESSION: single-entry text is exactly the pre-C2a format."""
        entry = KBContextEntry(entity_type="character", name="Alice", content="A brave warrior.")
        result = PromptContext._format_kb_entries([entry])
        assert result.text == "### Character: Alice\nA brave warrior."

    def test_text_matches_pre_c2a_wire_format_multiple_entries(self) -> None:
        """REGRESSION: multi-entry text is exactly the pre-C2a format."""
        entries = [
            KBContextEntry(entity_type="character", name="Alice", content="A brave warrior."),
            KBContextEntry(entity_type="location", name="Dark Forest", content="Spooky woods."),
        ]
        result = PromptContext._format_kb_entries(entries)
        assert result.text == _EXPECTED_STANDARD_TEXT

    def test_entry_count_reflects_input_length(self) -> None:
        entries = [
            KBContextEntry(entity_type="character", name="Alice", content="Brave."),
            KBContextEntry(entity_type="character", name="Bob", content="Calm."),
            KBContextEntry(entity_type="character", name="Cara", content="Wise."),
        ]
        result = PromptContext._format_kb_entries(entries)
        assert result.entry_count == 3

    def test_render_path_identifies_the_renderer(self) -> None:
        entries = [KBContextEntry(entity_type="character", name="Alice", content="Brave.")]
        result = PromptContext._format_kb_entries(entries)
        assert result.render_path == "narrare_core.prompts.context.PromptContext._format_kb_entries"


class TestFormatKbEntriesProvenanceAccounting:
    """C2a: provenance accounting per ADR-050 P1-A.

    The compact immediate-context wire format (``### Type: Name\\nContent``)
    preserves NO provenance. All available provenance fields must be
    explicitly omitted with a documented ``OmissionReason`` (RULE-22).
    Without this accounting the metadata was silently dropped at the
    render boundary — the exact gap ADR-050 P1-A closes.
    """

    def test_preserved_fields_empty_for_standard_wire_format(self) -> None:
        """The compact format carries no provenance → none preserved."""
        entries = [KBContextEntry(entity_type="character", name="Alice", content="Brave.")]
        result = PromptContext._format_kb_entries(entries)
        assert result.preserved_fields == frozenset()

    def test_omits_all_available_provenance_fields(self) -> None:
        """KBContextEntry carries source/evidence/confidence/review_status/freshness.

        These map to ProvenanceField literals:
          source + confidence → "provenance" (combined source marker)
          evidence            → "evidence"
          review_status       → "review_state"
          freshness           → "freshness"

        priority / kb_lifecycle are NOT carried by KBContextEntry and
        therefore cannot be lost — they are not listed.
        """
        entries = [KBContextEntry(entity_type="character", name="Alice", content="Brave.")]
        result = PromptContext._format_kb_entries(entries)

        omitted_fields: set[ProvenanceField] = {field for field, _reason in result.omitted_fields}
        assert omitted_fields == frozenset({"provenance", "evidence", "review_state", "freshness"})

    def test_every_omission_has_valid_reason(self) -> None:
        entries = [KBContextEntry(entity_type="character", name="Alice", content="Brave.")]
        result = PromptContext._format_kb_entries(entries)
        valid_reasons: set[OmissionReason] = {
            "token_budget_exhausted",
            "tier_does_not_require",
            "consumer_cannot_act",
            "explicitly_suppressed_for_run",
        }
        for _field, reason in result.omitted_fields:
            assert reason in valid_reasons

    def test_omission_reason_is_tier_does_not_require(self) -> None:
        """The compact format is immediate/suggested-context tier where
        provenance is not required (per KBContextEnvelope docstring)."""
        entries = [KBContextEntry(entity_type="character", name="Alice", content="Brave.")]
        result = PromptContext._format_kb_entries(entries)
        for _field, reason in result.omitted_fields:
            assert reason == "tier_does_not_require"


class TestFormatKbEntriesEdgeCases:
    """Edge cases: empty entries, full-provenance entries."""

    def test_empty_entries_returns_empty_rendered_context(self) -> None:
        result = PromptContext._format_kb_entries([])
        assert result.text == ""
        assert result.entry_count == 0
        assert result.preserved_fields == frozenset()
        # No entries → no provenance to account for.
        assert result.omitted_fields == ()

    def test_full_provenance_entry_still_omits_in_wire_format(self) -> None:
        """Even when an entry carries full provenance, the compact wire
        format does not render it. All fields are still omitted — but
        the accounting now DOCUMENTS that loss instead of silently
        dropping it (the whole point of ADR-050 P1-A)."""
        entry = KBContextEntry(
            entity_type="character",
            name="Alice",
            content="A brave warrior.",
            source="auto_extraction",
            evidence="Mentioned in chapter 1",
            confidence=0.85,
            review_status="pending",
            freshness="stale",
        )
        result = PromptContext._format_kb_entries([entry])
        # Wire format unchanged — provenance not in text.
        assert result.text == "### Character: Alice\nA brave warrior."
        assert result.preserved_fields == frozenset()
        assert {f for f, _ in result.omitted_fields} == frozenset(
            {"provenance", "evidence", "review_state", "freshness"}
        )

    def test_as_variables_does_not_leak_accounting_metadata(self) -> None:
        """The variables dict carries only text — accounting metadata
        stays on RenderedKBContext and never reaches the prompt template."""
        entry = KBContextEntry(
            entity_type="character",
            name="Alice",
            content="Brave.",
            source="auto_extraction",
            confidence=0.5,
            review_status="pending",
        )
        ctx = PromptContext(kb_context_entries=[entry])
        variables = ctx.as_variables()
        value = variables["kb_context_entries"]
        # No provenance markers leak into the prompt variable.
        assert "auto_extraction" not in value
        assert "pending" not in value
        assert "0.5" not in value
        assert "render_path" not in value
        assert "omitted_fields" not in value
