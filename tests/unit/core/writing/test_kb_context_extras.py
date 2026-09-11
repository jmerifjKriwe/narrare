"""Tests for _helpers.kb_context_extras — KB prompt variable extraction.

Covers:
1. Empty context returns all ten KB keys with "" values
2. Populated context carries each field's value under its key
3. Key-set exactness — exactly the ten KB variables, no more, no fewer
4. None-valued field coalesces to ""
"""

from __future__ import annotations

from narrare_core.writing._helpers import kb_context_extras
from narrare_core.writing.models import WritingContext

_KB_EXTRA_KEYS: frozenset[str] = frozenset(
    {
        "kb_characters",
        "kb_locations",
        "kb_factions",
        "kb_other",
        "kb_relationships",
        "kb_suggested",
        "kb_systems",
        "kb_timelines",
        "kb_pinned",
        "kb_context_warnings",
    }
)


class TestKBContextExtras:
    """kb_context_extras coverage."""

    def test_empty_context_returns_all_ten_keys_as_empty_strings(self) -> None:
        result = kb_context_extras(WritingContext())
        assert set(result) == _KB_EXTRA_KEYS
        assert all(value == "" for value in result.values())

    def test_populated_context_carries_each_field_value(self) -> None:
        context = WritingContext(
            kb_characters="### Character: Anna",
            kb_locations="### Location: Harbor",
            kb_factions="### Faction: Guild",
            kb_other="### Item: Compass",
            kb_relationships="Anna → Bernd",
            kb_suggested="### Character: Bernd",
            kb_systems="Magic costs 10 mana",
            kb_timelines="Day 5: Storm",
            kb_pinned="### Pinned: Rule",
            kb_context_warnings="Orphan reference: char-9",
        )
        result = kb_context_extras(context)
        assert result["kb_characters"] == "### Character: Anna"
        assert result["kb_locations"] == "### Location: Harbor"
        assert result["kb_factions"] == "### Faction: Guild"
        assert result["kb_other"] == "### Item: Compass"
        assert result["kb_relationships"] == "Anna → Bernd"
        assert result["kb_suggested"] == "### Character: Bernd"
        assert result["kb_systems"] == "Magic costs 10 mana"
        assert result["kb_timelines"] == "Day 5: Storm"
        assert result["kb_pinned"] == "### Pinned: Rule"
        assert result["kb_context_warnings"] == "Orphan reference: char-9"

    def test_key_set_is_exactly_the_ten_kb_variables(self) -> None:
        result = kb_context_extras(WritingContext())
        assert set(result.keys()) == _KB_EXTRA_KEYS

    def test_none_valued_field_coalesces_to_empty_string(self) -> None:
        context = WritingContext(kb_characters="kept")
        # Dynamic name: typed assignment ``context.kb_relationships = None``
        # is not type-valid for a ``str`` field; setattr simulates a
        # None-valued field the way external builders could produce it.
        field = "kb_relationships"
        setattr(context, field, None)
        result = kb_context_extras(context)
        assert result["kb_relationships"] == ""
        assert result["kb_characters"] == "kept"
